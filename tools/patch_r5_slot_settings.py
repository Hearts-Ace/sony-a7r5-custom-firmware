"""Offline, byte-scoped patch of the two R5 fixed-slot settings in both BK4 files."""
if __name__ == '__main__':
    raise SystemExit('Historical reference/helper only; standalone execution is disabled. See PUBLICATION.md.')

import argparse
import hashlib
import json
import struct
from pathlib import Path

from build_r5_partition1 import FatImage, require
from sony_bk4 import find_banks

SIZE = 20971520
START_SECTOR = 0xC000
TARGETS = {0x02CF0B69: 10, 0x02CF0B6F: 11}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def changed_sectors(before, after):
    require(len(before) == len(after) == SIZE, 'Wrong settings image size')
    return [i for i in range(SIZE // 512) if before[i*512:(i+1)*512] != after[i*512:(i+1)*512]]


def apply_sparse(before, patch):
    require(len(before) == SIZE and len(patch) >= 28, 'Invalid sparse input size')
    magic, major, minor, header, chunk_header, block_size, blocks, count, checksum = struct.unpack_from('<I4H4I', patch)
    require((magic, major, minor, header, chunk_header, block_size, blocks, checksum) ==
            (0xED26FF3A, 1, 0, 28, 12, 512, SIZE // 512, 0), 'Unexpected sparse header')
    out = bytearray(before)
    pos, block = 28, 0
    written = []
    for _ in range(count):
        require(pos + 12 <= len(patch), 'Truncated sparse chunk')
        kind, reserved, n, total = struct.unpack_from('<2H2I', patch, pos)
        require(reserved == 0 and n > 0 and block+n <= blocks, 'Invalid sparse extent')
        require(pos + total <= len(patch), 'Sparse payload outside file')
        if kind == 0xCAC1:
            require(total == 12+n*512, 'Invalid RAW length')
            out[block*512:(block+n)*512] = patch[pos+12:pos+total]
            written.extend(range(block, block+n))
        else:
            require(kind == 0xCAC3 and total == 12, 'Unsupported sparse chunk')
        block += n
        pos += total
    require(pos == len(patch) and block == blocks, 'Sparse EOF/total block mismatch')
    return bytes(out), written


def make_sparse(before, after):
    changes = set(changed_sectors(before, after))
    chunks = []
    pos = 0
    while pos < SIZE // 512:
        start, flag = pos, pos in changes
        while pos < SIZE // 512 and (pos in changes) == flag:
            pos += 1
        n = pos-start
        chunks.append(struct.pack('<2H2I', 0xCAC1 if flag else 0xCAC3, 0, n,
                                  12+n*512 if flag else 12) + (after[start*512:pos*512] if flag else b''))
    patch = struct.pack('<I4H4I', 0xED26FF3A, 1, 0, 28, 12, 512, SIZE//512, len(chunks), 0) + b''.join(chunks)
    rebuilt, written = apply_sparse(before, patch)
    require(rebuilt == after and written == sorted(changes), 'Sparse overlay mismatch')
    require(len(patch) <= 524288, 'Sparse download too large')
    return patch


def patch_image(before):
    require(len(before) == SIZE, 'Not a complete R5 settings partition')
    fs = FatImage(before)
    require(fs.read('/updater/dat4') == b'\x02\x04', 'Expected installed version 4.02')
    after = bytearray(before)
    reports = {}
    allowed_partition_offsets = set()
    for name in ('/backup.bin', '/backup.bak'):
        old = fs.read(name)
        banks = find_banks(old)
        require([b.offset for b in banks] == [0, 0xEF000], 'Invalid/missing BK4 banks')
        require(len(old) == 2372469, 'Unexpected backup length')
        new = bytearray(old)
        allowed_file_offsets = set(range(0x20, 0x24))
        items = {}
        for pid, value in TARGETS.items():
            prop = banks[0].property(pid)
            require(prop.attributes == 0x60 and prop.capacity == 1 and len(prop.data) == 1,
                    'Unexpected target metadata')
            require(prop.data in (b'\x00', bytes([value])), 'Unexpected target old value')
            new[prop.file_offset] = value
            allowed_file_offsets.add(prop.file_offset)
            items[hex(pid)] = dict(old=prop.data.hex(), new=f'{value:02x}', file_offset=prop.file_offset)
        checksum = sum(new[:0x20]) + sum(new[0x24:banks[0].size])
        struct.pack_into('<I', new, 0x20, checksum)
        new = bytes(new)
        new_banks = find_banks(new)
        require([b.offset for b in new_banks] == [0, 0xEF000], 'Patched bank validation failed')
        require(new_banks[1].data == banks[1].data, 'Unrelated bank changed')
        for pid, value in TARGETS.items():
            require(new_banks[0].property(pid).data == bytes([value]), 'Patched target mismatch')
        diff = [i for i,(a,b) in enumerate(zip(old,new)) if a != b]
        require(set(diff) <= allowed_file_offsets, 'Unauthorized backup byte changed')
        fs.patch(after, name, new)
        logical = 0
        for off, n in fs.entries[name]['extents']:
            for i in allowed_file_offsets:
                if logical <= i < logical+n:
                    allowed_partition_offsets.add(off+i-logical)
            logical += n
        reports[name] = dict(before_sha256=digest(old), after_sha256=digest(new),
                             targets=items, checksum_before=banks[0].checksum, checksum_after=checksum,
                             changed_file_offsets=diff)
    after = bytes(after)
    changed = [i for i,(a,b) in enumerate(zip(before,after)) if a != b]
    require(set(changed) <= allowed_partition_offsets, 'Unauthorized partition byte changed')
    new_fs = FatImage(after)
    require(new_fs.entries == fs.entries, 'Filesystem allocation or directory metadata changed')
    for path, entry in fs.entries.items():
        if not entry['is_directory'] and path not in reports:
            require(new_fs.read(path) == fs.read(path), 'Unrelated file changed: '+path)
    report = dict(scope='Two existing BK4 properties in each backup plus bank0 checksum only',
                  image_bytes=SIZE, absolute_first_sector=START_SECTOR,
                  before_sha256=digest(before), after_sha256=digest(after), backups=reports,
                  changed_partition_offsets=changed, changed_sectors=changed_sectors(before, after),
                  directory_and_allocation_metadata_unchanged=True, all_other_files_unchanged=True)
    return after, report


def build(source, output):
    before = source.read_bytes()
    after, report = patch_image(before)
    output.mkdir(mode=0o700, exist_ok=False)
    forward = make_sparse(before, after)
    reverse = make_sparse(after, before)
    artifacts = {'candidate.logical.img': after, 'patch.sparse.img': forward, 'restore.sparse.img': reverse}
    for name, data in artifacts.items():
        p = output / name
        p.write_bytes(data)
        p.chmod(0o600)
    report.update(source=str(source.resolve()), files={name: dict(bytes=len(data), sha256=digest(data))
                                                      for name,data in artifacts.items()},
                  forward_and_reverse_overlays_verified=True,
                  restore_scope='Only this acquisition before normal boot; re-read before any later restore')
    (output/'verification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    return report


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(build(args.source,args.output),indent=2,ensure_ascii=False))
