#!/usr/bin/env python3
"""R5 aspect-ratio labels and Fn badges; offline resource components only.

Accepts the exact stock R5 resource identities recorded in inputs.json. The
4.55 layout recipe changes no image/string inode content, as checked separately
by inventory.py. No AP, CP, partition image or camera is modified here.
"""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import struct
import reference_style

HERE = Path(__file__).resolve().parent
RATIOS = ('1.618:1', '2.39:1', '5:4', '1.85:1')
TEXT_IDS = tuple(range(0x0200AB4C, 0x0200AB50))
IMAGE_IDS = tuple(range(0x02001E90, 0x02001E98))
PLAYBACK_IDS = tuple(range(0x02001E9C, 0x02001E9F))
MEGAPIXEL_IDS = tuple(range(0x02001E8D, 0x02001E90))
MENU_IMAGE_IDS = tuple(range(0x02001E80, 0x02001E84))
ALL_IMAGE_IDS = IMAGE_IDS + PLAYBACK_IDS + MEGAPIXEL_IDS + MENU_IMAGE_IDS
LENGTHS = tuple(range(3, 17)) + (32, 64)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def align4(n):
    return (n + 3) & ~3


def string_layout(b):
    require(b[:4] == b'uxc\x07', 'Not a string UXC')
    count, rem = divmod(struct.unpack_from('<I', b, 12)[0], 0x1001)
    require(not rem and 0 < count <= 8192, 'Invalid string count')
    return count, 0x1E000000 + (struct.unpack_from('<H', b, 10)[0] << 13), align4(16 + 2 * count)


def string_records(b):
    count, low, db = string_layout(b)
    result = {}
    for i in range(count):
        word = struct.unpack_from('<H', b, 16 + i * 2)[0]
        if word == 0xFFFF:
            continue
        at = db + word * 4
        require(at + 4 <= len(b), 'String index outside resource')
        rid = struct.unpack_from('<I', b, at)[0]
        require(rid == low + i, 'String index/key mismatch')
        end = b.index(0, at + 4)
        result[rid - 0x1C000000] = b[at + 4:end].decode('utf8')
    return result


def patch_strings(source):
    count, low, db = string_layout(source)
    before = string_records(source)
    out = bytearray(source)
    updates = dict(zip(TEXT_IDS, RATIOS))
    for runtime, label in updates.items():
        stored = runtime + 0x1C000000
        index = stored - low
        require(0 <= index < count, 'Aspect label outside string bank')
        require(struct.unpack_from('<H', out, 16 + index * 2)[0] == 0xFFFF,
                'Aspect label slot is already occupied')
        out.extend(bytes(-len(out) % 4))
        word = (len(out) - db) // 4
        require(word < 0xFFFF, 'String index exceeds 16-bit word range')
        struct.pack_into('<H', out, 16 + index * 2, word)
        out.extend(struct.pack('<I', stored) + label.encode('ascii') + b'\0')
        out.extend(bytes(-len(out) % 4))
    actual = string_records(bytes(out))
    require(actual == before | updates, 'Old labels changed or new labels missing')
    allowed = {16 + (rid + 0x1C000000 - low) * 2 + j for rid in TEXT_IDS for j in (0, 1)}
    require(all(a == b or i in allowed for i, (a, b) in enumerate(zip(source, out))),
            'Unexpected existing string byte changed')
    return bytes(out), dict(original_records=len(before), labels_added={hex(k): v for k, v in updates.items()},
                           existing_records_preserved=True, existing_bytes_except_four_index_words_preserved=True)


def image_records(b):
    require(b[:4] == b'uxd\x07', 'Not an image UXC')
    count = struct.unpack_from('<I', b, 12)[0] & 0x1FFF
    bank = struct.unpack_from('<H', b, 10)[0]
    require(struct.unpack_from('<I', b, 12)[0] >> 13 == (count + 1) // 2,
            'Invalid image count encoding')
    db = align4(16 + count * 2)
    result = {}
    for i in range(count):
        word = struct.unpack_from('<H', b, 16 + i * 2)[0]
        if word == 0xFFFF:
            continue
        at = db + 4 * word
        key, flags = struct.unpack_from('<II', b, at)
        require(key == 0x1A000000 + bank * 8192 + i, 'Image index/key mismatch')
        require(flags in (0xC0000000, 0x40000000, 0xC8000000, 0x48000000), 'Unsupported image flags')
        nine = bool(flags & 0x08000000)
        length_at, relative_at = (at + 32, at + 36) if nine else (at + 12, at + 16)
        length, rel = struct.unpack_from('<II', b, length_at)
        start = at + 4 + rel
        require(start + length <= len(b), 'Image payload outside bank')
        result[key - 0x18000000] = dict(at=at, flags=flags, descriptor_size=40 if nine else 20,
            relative_at=relative_at, payload_at=start, length=length,
            descriptor=b[at:at + (40 if nine else 20)], payload=b[start:start + length])
    return count, bank, db, result


def inflate(src, capacity):
    """Bounded Sony F0 stream model; 4 KiB dictionaries reset per block."""
    out, pos, blocks = bytearray(), 0, []
    while pos < len(src):
        begin, first = pos, len(out)
        require(src[pos] == 0xF0, 'Expected compressed Sony F0 block')
        pos += 1
        finished = False
        while not finished:
            require(pos < len(src), 'Missing LZ flags')
            flags = src[pos]
            pos += 1
            for bit in range(8):
                if flags & (1 << bit):
                    require(pos + 2 <= len(src), 'Short LZ reference')
                    a, b = src[pos:pos + 2]
                    pos += 2
                    distance = (a & 15) * 256 + b
                    if distance == 0:
                        finished = True
                        break
                    length = LENGTHS[a >> 4]
                    require(distance <= len(out) - first, 'Reference crosses block dictionary')
                    require(len(out) + length <= capacity and len(out) + length - first <= 4096,
                            'LZ output exceeds block or total capacity')
                    for _ in range(length):
                        out.append(out[-distance])
                else:
                    require(pos < len(src) and len(out) < capacity and len(out) - first < 4096,
                            'Invalid LZ literal')
                    out.append(src[pos])
                    pos += 1
        blocks.append(dict(compressed_bytes=pos - begin, decoded_bytes=len(out) - first))
    require(len(out) == capacity, 'Decoded image length mismatch')
    return bytes(out), blocks


def deflate_block(raw):
    """Greedy exact matches with bounded recent candidates and overlap support."""
    require(0 < len(raw) <= 4096, 'One Sony output block is at most 4096 B')
    tokens, history, pos = [], collections.defaultdict(collections.deque), 0
    while pos < len(raw):
        best, distance = 0, 0
        if pos + 3 <= len(raw):
            key = raw[pos:pos + 3]
            candidates = history[key]
            while candidates and pos - candidates[0] > 4095:
                candidates.popleft()
            for at in reversed(candidates):
                d = pos - at
                maximum = min(64, len(raw) - pos)
                n = 0
                while n < maximum and raw[pos + n] == raw[pos + n - d]:
                    n += 1
                representable = next((v for v in reversed(LENGTHS) if v <= n), 0)
                if representable > best:
                    best, distance = representable, d
                    if best == 64:
                        break
        consume = best or 1
        if best:
            code = LENGTHS.index(best)
            tokens.append((True, bytes([(code << 4) | (distance >> 8), distance & 255])))
        else:
            tokens.append((False, raw[pos:pos + 1]))
        for i in range(pos, pos + consume):
            if i + 3 <= len(raw):
                bucket = history[raw[i:i + 3]]
                bucket.append(i)
                if len(bucket) > 96:
                    bucket.popleft()
        pos += consume
    tokens.append((True, b'\0\0'))
    out = bytearray(b'\xf0')
    for at in range(0, len(tokens), 8):
        group = tokens[at:at + 8]
        out.append(sum(int(flag) << i for i, (flag, _) in enumerate(group)))
        for _, blob in group:
            out.extend(blob)
    require(len(out) <= 4096, 'Compressed block exceeds the bank decoder input contract')
    return bytes(out)


def deflate(raw):
    result = b''.join(deflate_block(raw[i:i + 4096]) for i in range(0, len(raw), 4096))
    decoded, blocks = inflate(result, len(raw))
    require(decoded == raw, 'Independent LZ decode does not reproduce input')
    return result, blocks


def badge(label, selected, orientation='23'):
    return reference_style.icon_pixels(label, selected, str(orientation))


def image_specs(orientation):
    orientation=str(orientation)
    entries=[(rid, RATIOS[i%4], i>=4, 70, 60,
              badge(RATIOS[i%4], i>=4, "23")) for i,rid in enumerate(IMAGE_IDS)]
    entries += [(rid,label,None,47,32,reference_style.current_playback_pixels(label,"32" if label == "1.85:1" else "23"))
                for rid,label in zip(PLAYBACK_IDS,reference_style.CURRENT_PLAYBACK_LABELS)]
    entries += [(rid,label,None,48,32,reference_style.megapixel_pixels(label,orientation))
                for rid,label in zip(MEGAPIXEL_IDS,reference_style.MEGAPIXEL_LABELS)]
    entries += [(rid,label,None,76,40,reference_style.menu_pixels(label,"23"))
                for rid,label in zip(MENU_IMAGE_IDS,RATIOS)]
    return entries


def patch_images(source, orientation):
    count, bank, db, original = image_records(source)
    require(bank == 0, 'Aspect images belong in bank zero')
    for rid in ALL_IMAGE_IDS:
        require(rid not in original and (rid & 8191) < count, 'Image slot occupied or outside index')
    # Preserve all existing descriptors/indexes and payload bytes. Insert the
    # fourteen descriptors before the first payload so u16 word indexes stay small.
    insertion = min(r['payload_at'] for r in original.values())
    descriptor_end = max(r['at'] + r['descriptor_size'] for r in original.values())
    require(insertion == descriptor_end and insertion % 4 == 0,
            'Unexpected gap/overlap at image descriptor/payload boundary')
    shift = len(ALL_IMAGE_IDS) * 20
    out = bytearray(source[:insertion] + bytes(shift) + source[insertion:])
    for record in original.values():
        rel = struct.unpack_from('<I', out, record['relative_at'])[0]
        struct.pack_into('<I', out, record['relative_at'], rel + shift)
    additions = []
    specs=image_specs(orientation)
    for i, (rid,label,selected,width,height,raw) in enumerate(specs):
        payload, blocks = deflate(raw)
        out.extend(bytes(-len(out) % 4))
        payload_at = len(out)
        out.extend(payload)
        at = insertion + i * 20
        word = (at - db) // 4
        require(word < 0xFFFF, 'New descriptor exceeds word index')
        struct.pack_into('<H', out, 16 + (rid & 8191) * 2, word)
        struct.pack_into('<IIHHII', out, at, rid + 0x18000000,
                         0xC0000000, width, height, len(payload), payload_at - at - 4)
        additions.append(dict(runtime_id=hex(rid), text=label, selected=selected,
            decoded_sha256=sha(raw), payload_sha256=sha(payload), blocks=blocks))
    _, _, _, actual = image_records(bytes(out))
    require(set(actual) == set(original) | set(ALL_IMAGE_IDS), 'Unexpected image records')
    for rid, before in original.items():
        after = actual[rid]
        desc = bytearray(after['descriptor'])
        at = after['relative_at'] - after['at']
        struct.pack_into('<I', desc, at, struct.unpack_from('<I', desc, at)[0] - shift)
        require(bytes(desc) == before['descriptor'] and after['payload'] == before['payload'],
                'Existing image descriptor or compressed pixels changed')
    for rid,label,selected,width,height,raw in specs:
        decoded, blocks = inflate(actual[rid]['payload'], len(raw))
        require(decoded == raw, 'New badge decode mismatch')
        require([b['decoded_bytes'] for b in blocks] == [min(4096,len(raw)-at) for at in range(0,len(raw),4096)], 'Wrong output chunking')
    return bytes(out), dict(original_records=len(original), descriptors_inserted_bytes=shift,
        original_payload_bytes_preserved=True, original_descriptors_preserved_except_payload_offsets=True,
        index_count_unchanged=True, additions=additions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root', type=Path, required=True, help='Exact stock /share/app directory')
    parser.add_argument('--output', type=Path, required=True, help='New component output directory')
    args = parser.parse_args()
    if not __debug__:
        parser.error('Do not run with -O')
    require(not args.output.exists(), 'Output must not exist')
    manifest = json.loads((HERE / 'inputs.json').read_text())
    blobs = {}
    for row in manifest['resource_files']:
        source = args.input_root / row['name']
        blob = source.read_bytes()
        require(len(blob) == row['bytes'] and sha(blob) == row['sha256'], 'Unsupported resource: ' + row['name'])
        blobs[row['name']] = blob
    args.output.mkdir(parents=True)
    rows = []
    for name, blob in blobs.items():
        patched, check = patch_images(blob,name.split('_')[2]) if name.startswith('image_') else patch_strings(blob)
        (args.output / name).write_bytes(patched)
        rows.append(dict(name=name, input_sha256=sha(blob), output_sha256=sha(patched),
                         input_bytes=len(blob), bytes=len(patched), checks=check))
    result = dict(schema='r5.aspect.resources.v1', passed=True, camera_io=False,
        installable=False, source_script_sha256=sha(Path(__file__).read_bytes()),
        input_manifest_sha256=sha((HERE / 'inputs.json').read_bytes()),
        reference_style_sha256=sha((HERE / 'reference_style.py').read_bytes()),
        text_runtime_ids=[hex(v) for v in TEXT_IDS], image_runtime_ids=[hex(v) for v in ALL_IMAGE_IDS],
        file_count=len(rows), files=rows,
        limits=['Components require AP/CP and partition integration before use.',
                'LZ decoding here is a host model; native resource selection is checked separately.',
                'No physical LCD or camera output is claimed.'])
    (args.output / 'manifest.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(dict(passed=True, files=len(rows), output=str(args.output))))


if __name__ == '__main__':
    main()
