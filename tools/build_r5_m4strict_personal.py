#!/usr/bin/env python3
"""Build FL2/FL3 changes in a supplied R5 personal nflasha2 image, offline only.

Writes a new file; never opens a device. Does not modify a DAT, a default
template or nflasha6. Historical input produces a historical derivative,
not a current recovery image. Fresh acquisition and deployment are separate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / 'analysis/erlla_a7m4_comparison_20261015/upstream/Erlla-sony-a7m4-custom-firmware-086df3b'
for upstream_name, expected_hash in {
    'fl23.py': 'da06220bbf4a3064f189f102c0cef17783d3a5e75a4d4bc58e12ac6ce65732cf',
    'fat.py': '574d1aeee03f2b20fe2424591fe6caf25680610909a029b9da76fc4c608f873d',
    'common.py': 'a09cf0f404d31989cf2269a4ea9108efc6832e05408a4b888860ad1d6f5303bc',
    'offline.py': '60ff6f49d2ff72f40ab134e677750bb12408e8e790342ce393bfd52d52ce5320',
}.items():
    if hashlib.sha256((UPSTREAM / 'a7m4' / upstream_name).read_bytes()).hexdigest() != expected_hash:
        raise ValueError('Changed upstream dependency: ' + upstream_name)
sys.path.insert(0, str(UPSTREAM))
from a7m4.fat import Fat
from a7m4.fl23 import bk4_rows, color_records

DONOR = ROOT / 'unpacked/fx2/firmware/0110_backup/SYSIPSX-DSLR/DOC/CX96900_ALLLANG.bin'
DONOR_SHA = 'fdee302d240ec1534349e6c9a688a12c883c2cbb7be3ffd97376b419592dc331'
CC_OLD = '1fdae63d018d6f9d73de43273cb2694ef93d78dea8dff68779751956401b1f8a'
MAT_OLD = '4a4ec0273185a2f3f08c3206e09c0d6a12b48f71a84d38f98d1247ca57d8bf8e'
SLOTS = {0x02cf0b69: 10, 0x02cf0b6f: 11, 0x02cf0b93: 10,
         0x02cf0b95: 11, 0x02cf0b97: 10, 0x02cf0b99: 11}
KNOWN_HISTORICAL = {
    'bb4bcb2ee879e96bb519464d657975f8d4a7edeb143240d96eee7241b5e3c944': '4.00 backup, 2026-10-14, before incident',
    '4d45b372894894f7f3c728d23ed5dc92506dbabbbf85f1db3beb6d4a3f1a7267': '4.02 settings readback, 2026-10-15 02:15, before incident',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def unique(rows, key):
    found = [r['records'][key] for r in rows if key in r['records']]
    require(len(found) == 1, f'Expected one BK4 property {key:08x}')
    return found[0]


def read_record(data, rec):
    return data[rec['offset']:rec['offset'] + rec['size']]


def donors():
    data = DONOR.read_bytes()
    require(sha(data) == DONOR_SHA, 'Wrong FX2 donor')
    rows = bk4_rows(data)
    cc, matrix = [read_record(data, unique(rows, key)) for key in (0x02a40001, 0x02a4000d)]
    require(sha(cc) == 'c87f4dad18225b0b6a5a273bd27211fd93ad0ca0ab8ac2f1b65f680daec4d996', 'Wrong FX2 CC1')
    require(sha(matrix) == 'd783cf223304e67d6d671642c8b1102a0c663bc114a64c7f76a1d160d8a3feee', 'Wrong FX2 block13')
    return cc, matrix


def outside_equal(before, after, ranges):
    require(len(before) == len(after), 'Image size changed')
    cursor = 0
    for start, end in sorted(ranges):
        require(0 <= start <= end <= len(before), 'Allowed range exceeds image')
        if start > cursor:
            require(before[cursor:start] == after[cursor:start], f'Unexpected change outside allowlist at {cursor:x}')
        cursor = max(cursor, end)
    require(before[cursor:] == after[cursor:], 'Unexpected change outside final allowed range')


def color_updates(cc, matrix, donor_cc, donor_matrix):
    require(len(cc) == 0x2000 and len(matrix) == 0x7000 and cc[0xefe] == 0, 'Unsupported R5 color format')
    # Normalize only the author-targeted ranges, then bind all other color bytes
    # to the supported original R5 data. Each range admits either old or new.
    cc_ranges = [(0x1236, 4)] + [(0x1250 + i * 64, 48) for i in (22, 23, 24, 25)]
    mat_ranges = [(0x1cc, 4), (0x43e0, 0xc00)]
    old_cc, old_mat = bytearray(cc), bytearray(matrix)
    for start, size in cc_ranges:
        old_cc[start:start + size] = bytes(size)
    for start, size in mat_ranges:
        old_mat[start:start + size] = bytes(size)
    require(sha(old_cc) == CC_OLD and sha(old_mat) == MAT_OLD, 'Unknown R5 color baseline; no calibration guess is allowed')
    new_cc, new_mat = color_records(bytes(old_cc), bytes(old_mat), donor_cc, donor_matrix)
    for value, target, ranges in ((cc, new_cc, cc_ranges), (matrix, new_mat, mat_ranges)):
        for start, size in ranges:
            require(value[start:start + size] in (bytes(size), target[start:start + size]), 'Unrecognized old/new color fragment')
    return [(0x02a40001, new_cc, cc_ranges), (0x02a4000d, new_mat, mat_ranges)]


def patch_backup(source, donor_cc, donor_matrix):
    rows = bk4_rows(source)
    result = bytearray(source)
    cc, mat = [read_record(source, unique(rows, key)) for key in (0x02a40001, 0x02a4000d)]
    operations = color_updates(cc, mat, donor_cc, donor_matrix)
    for key, target in SLOTS.items():
        rec = unique(rows, key)
        require(rec['attrs'] == 0x60 and rec['size'] == 1, 'Unsupported look-slot metadata')
        require(read_record(source, rec) in (b'\0', bytes([target])), 'Unrecognized look-slot preimage')
        operations.append((key, bytes([target]), [(0, 1)]))
    allowed, report = [], []
    for key, target, ranges in operations:
        rec = unique(rows, key)
        require(rec['size'] == len(target), 'Record size would change')
        for relative, length in ranges:
            start = rec['offset'] + relative
            before, after = source[start:start + length], target[relative:relative + length]
            result[start:start + length] = after
            allowed.append((start, start + length))
            report.append({'property_id': f'{key:08x}', 'property_offset': relative, 'size': length,
                           'source_sha256': sha(before), 'target_sha256': sha(after), 'already_target': before == after})
    for row in rows:
        base, extent = row['base'], row['extent']
        checksum = sum(result[base:base + 0x20]) + sum(result[base + 0x24:base + extent])
        struct.pack_into('<I', result, base + 0x20, checksum)
        allowed.append((base + 0x20, base + 0x24))
    output = bytes(result)
    bk4_rows(output)
    outside_equal(source, output, allowed)
    return output, allowed, report


def build_image(source):
    require(len(source) == 20 * 1024 * 1024, 'Expected R5 20 MiB logical nflasha2 image')
    fs = Fat(source)
    donor_cc, donor_matrix = donors()
    ranges, records = [], {}
    for name in ('BACKUP.BIN', 'BACKUP.BAK'):
        before = fs.read(name)
        after, local_ranges, changes = patch_backup(before, donor_cc, donor_matrix)
        _, first, size, _ = fs.locate(name)
        require(size == len(after), 'Personal backup file must keep its exact size')
        chain = fs.chain(first)
        for lo, hi in local_ranges:
            while lo < hi:
                index, relative = divmod(lo, fs.cluster_size)
                count = min(hi - lo, fs.cluster_size - relative)
                start = fs.offset(chain[index]) + relative
                ranges.append((start, start + count))
                lo += count
        fs.replace(name, after)
        records[name] = {'source_sha256': sha(before), 'output_sha256': sha(after),
                         'size': len(after), 'changes': changes, 'bk4_checksums_valid': True}
    output = fs.bytes()
    outside_equal(source, output, ranges)
    require(output[:fs.data_start] == source[:fs.data_start], 'FAT allocation/directory metadata changed')
    # A separate BK4 parser also validates checksums and target values.
    from sony_bk4 import find_banks
    verify_fs = Fat(output)
    for name in records:
        banks = find_banks(verify_fs.read(name))
        require(len(banks) == 2, 'Independent parser did not find two banks')
        for key, target in SLOTS.items():
            found = []
            for bank in banks:
                try:
                    found.append(bank.property(key))
                except KeyError:
                    pass
            require(len(found) == 1 and found[0].data == bytes([target]), 'Independent slot verification failed')
    return output, {'source_sha256': sha(source), 'output_sha256': sha(output), 'size': len(output),
                    'files': records, 'only_author_color_ranges_six_slots_and_checksums_changed': True,
                    'all_other_personal_calibration_settings_and_fat_layout_unchanged': True,
                    'nflasha6_modified': False, 'camera_io': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nflasha2', type=Path, required=True, help='Explicit local logical image, never /dev/...')
    parser.add_argument('--output', type=Path, required=True, help='A new output directory')
    args = parser.parse_args()
    require(args.nflasha2.is_file() and not str(args.nflasha2.resolve()).startswith('/dev/'), 'Input must be a regular saved image')
    require(not args.output.exists(), 'Choose a new output directory')
    source = args.nflasha2.read_bytes()
    output, report = build_image(source)
    report.update(input_path=str(args.nflasha2.resolve()),
                  source_age=KNOWN_HISTORICAL.get(sha(source), 'Unverified acquisition time; freshness is not established'),
                  current_body_state_verified=False, deployable_recovery_image=False,
                  scope='Computer-side derivative only; not embedded in DAT and never automatically deployed',
                  nflasha6_reason='R5 verified App mounts nflasha6 at /usr/data/gridline; no proven M4 color-copy layout',
                  upstream_commit='086df3b1e33dfa0206553ac2bb003535c58ddb80')
    args.output.mkdir(parents=True)
    product = args.output / 'nflasha2.offline-derivative.img'
    product.write_bytes(output)
    require(sha(product.read_bytes()) == report['output_sha256'], 'Output file verification failed')
    (args.output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('source_sha256', 'output_sha256', 'source_age', 'current_body_state_verified', 'camera_io')}))


if __name__ == '__main__':
    main()
