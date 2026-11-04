"""512-byte changed-sector sparse images; no device access."""
import hashlib
import struct
from filesystem import require
SIZE=20971520
START_SECTOR=0xc000

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
