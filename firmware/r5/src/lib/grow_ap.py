"""Extend only appFw.so in a derived ext2, retaining its inode and old blocks.

Allocation uses e2fsprogs; independent checks restrict byte changes, retain all
other inode/directory contents, inspect allocation accounting and run e2fsck.
This never accepts or edits an original input inode.
"""
from pathlib import Path
import json
import os
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ext2read import Ext2
from image_io import close_image, digest_file, require

DEBUGFS = Path('/opt/homebrew/opt/e2fsprogs/sbin/debugfs')
E2FSCK = DEBUGFS.with_name('e2fsck')
# Only the independently derived sound n15 layout is eligible for mutation.
EXPECTED_LAYOUT_SHA256 = '4a38037ace156b48368f30fc98acd89336a47508700af5b6061acc67b8f39285'


def inode_offset(e, ino):
    group, index = divmod(ino-1, e.inodes_per_group)
    return e.inode_table(group)*e.block_size + index*e.inode_size


def indirect_blocks(e, ino):
    roots = e.inode(ino)[2]
    found = set()
    def descend(block, depth):
        if not block:
            return
        require(block not in found, 'Repeated indirect block')
        found.add(block)
        if depth > 1:
            for p in struct.unpack_from('<%dI' % (e.block_size//4), e.mm,
                                        block*e.block_size):
                if p:
                    descend(p, depth-1)
    for depth, block in enumerate(roots[12:], 1):
        descend(block, depth)
    return found


def allocated(e, block):
    first = struct.unpack_from('<I', e.mm, 1024+20)[0]
    group, index = divmod(block-first, e.blocks_per_group)
    bitmap = struct.unpack_from('<I', e.mm, e.bgd_off+group*32)[0]
    return bool(e.mm[bitmap*e.block_size+index//8] & (1 << (index % 8)))


def replace(image, component, report_path):
    image, component, report_path = map(Path, (image, component, report_path))
    require(DEBUGFS.is_file() and E2FSCK.is_file(), 'e2fsprogs required')
    require(not image.is_symlink() and image.stat().st_nlink == 1,
            'AP extension requires a separate derived file, never a link')
    require(digest_file(image) == EXPECTED_LAYOUT_SHA256,
            'AP extension accepts only the reviewed derived sound layout')
    e = Ext2(image)
    ino = e.walk('/lib/appFw.so')
    mode, old_size, _ = e.inode(ino)
    new_size = component.stat().st_size
    require(old_size < new_size <= old_size + (1 << 20), 'Bounded AP extension required')
    bs = e.block_size
    old_blocks = e.inode_blocks(ino)
    old_indirect = indirect_blocks(e, ino)
    offset = inode_offset(e, ino)
    old_inode = bytes(e.mm[offset:offset+e.inode_size])
    before_sha = digest_file(image)
    before = bytes(e.mm)
    original_block_count = e.blocks_count
    close_image(e)
    commands = ['fallocate /lib/appFw.so %d %d' %
                (len(old_blocks), (new_size+bs-1)//bs-1),
                'set_inode_field /lib/appFw.so size %d' % new_size]
    script = report_path.with_suffix('.debugfs.txt')
    script.write_text('\n'.join(commands)+'\n')
    run = subprocess.run([str(DEBUGFS), '-w', '-f', str(script), str(image)],
                         capture_output=True, text=True)
    report_path.with_suffix('.debugfs.log').write_text(run.stdout+run.stderr)
    require(run.returncode == 0, 'AP extension allocation failed')
    e = Ext2(image)
    require(e.walk('/lib/appFw.so') == ino and e.blocks_count == original_block_count,
            'AP inode or filesystem geometry changed')
    require(e.inode(ino)[:2] == (mode, new_size), 'AP extension size/mode mismatch')
    blocks = e.inode_blocks(ino)
    indirect = indirect_blocks(e, ino)
    require(len(blocks) == (new_size+bs-1)//bs and all(blocks) and
            len(set(blocks)) == len(blocks) and blocks[:len(old_blocks)] == old_blocks,
            'AP original block chain changed or extension is sparse')
    new_alloc = (set(blocks) | indirect) - (set(old_blocks) | old_indirect)
    # Use the pre-edit bitmap through a read-only synthetic reader facade.
    class Original:
        mm = before
        block_size = bs
        blocks_per_group = e.blocks_per_group
        bgd_off = e.bgd_off
    require(all(not allocated(Original, b) and allocated(e, b) for b in new_alloc),
            'New AP blocks were previously allocated or remain free')
    current_inode = bytes(e.mm[offset:offset+e.inode_size])
    keep = bytearray(old_inode)
    for lo, hi in ((4, 8), (28, 32), (40, 100)):
        keep[lo:hi] = current_inode[lo:hi]
    require(current_inode[:4] == old_inode[:4], 'AP ownership/mode changed')
    close_image(e)
    with image.open('r+b') as f, component.open('rb') as src:
        f.seek(offset); f.write(keep)
        for b in blocks:
            data = src.read(bs)
            f.seek(b*bs); f.write(data + bytes(bs-len(data)))
        require(src.read(1) == b'', 'Incomplete AP component write')
        # debugfs writes a wall-clock stamp at close; preserve deterministic input.
        f.seek(1024+48); f.write(before[1024+48:1024+52])
        f.flush(); os.fsync(f.fileno())
    e = Ext2(image)
    require(e.read_inode(ino) == component.read_bytes(), 'Extended AP content mismatch')
    require(e.mm[offset:offset+e.inode_size] == keep, 'AP inode metadata mismatch')
    # Byte-level allowlist: AP contents/tree/inode and allocation counters/bitmaps.
    allowed = [(b*bs, (b+1)*bs) for b in set(blocks) | indirect]
    allowed += [(offset+lo, offset+hi) for lo, hi in ((4,8),(28,32),(40,100))]
    allowed += [(1024+12,1024+16)]  # s_free_blocks_count only
    for group in range(e.ngroups):
        gd = e.bgd_off+group*32
        bitmap = struct.unpack_from('<I', e.mm, gd)[0]
        allowed += [(bitmap*bs,(bitmap+1)*bs), (gd+12,gd+14)]
    by_block = {}
    for lo, hi in allowed:
        for block in range(lo//bs, (hi-1)//bs+1):
            by_block.setdefault(block, []).append((lo, hi))
    changed_blocks, changed_bytes = [], 0
    for off in range(0, len(before), bs):
        old, new = before[off:off+bs], e.mm[off:off+bs]
        if old == new:
            continue
        changed_blocks.append(off//bs)
        spans = by_block.get(off//bs, [])
        for i, (a, b) in enumerate(zip(old, new)):
            if a != b:
                require(any(lo <= off+i < hi for lo,hi in spans),
                        'Unexpected AP extension byte change: '+hex(off+i))
                changed_bytes += 1
    close_image(e)
    del before
    run = subprocess.run([str(E2FSCK), '-fn', str(image)], capture_output=True, text=True)
    report_path.with_suffix('.e2fsck.log').write_text(run.stdout+run.stderr)
    require(run.returncode == 0, 'Extended AP filesystem failed e2fsck')
    report = dict(passed=True, inode=ino, original_size=old_size, size=new_size,
                  growth_bytes=new_size-old_size, old_block_chain_retained=True,
                  new_allocated_blocks=sorted(new_alloc),
                  old_indirect_blocks=len(old_indirect), indirect_blocks=len(indirect),
                  changed_blocks=changed_blocks, changed_bytes=changed_bytes,
                  exact_change_allowlist_verified=True, e2fsck_readonly_passed=True,
                  before_sha256=before_sha, after_sha256=digest_file(image),
                  component_sha256=digest_file(component), camera_io=False)
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    return report
