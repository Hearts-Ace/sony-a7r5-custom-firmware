#!/usr/bin/env python3
"""Prepare same-size R5 SD generic-template replacements, offline only.

Adapt Erlla's SD colour preservation algorithm to all 12 R5 GL defaults.
Preserve current dynamic B/A1/A2 data and merge only approved R6 ST/AWB spans.
No personal settings image, camera access, AP hook, finalizer or reset is used.
"""
from dataclasses import dataclass
from pathlib import Path
import argparse
import binascii
import hashlib
import importlib.util
import json
import struct
import sys
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'lib'))
from sony_bk4 import find_banks

PREFIX = '0110_backup/SYSIPSX-DSLR/GL/'
SUM = '0111_backup_sum/backup.sum'
CC1, MATRIX, AWB = 0x02a40001, 0x02a4000d, 0x02a40000
STOCK_HASHES = {
    'CX89200_ALLLANG.bin': 'a3b036d3e1dbeeb7c6e2fc7f02d41e5fc2731b8ba8165c3ee9927d9b504a876c',
    'CX89200_E38.bin': 'e6909b4e0df661a1b53621873904ecfaa9af18f1b43f5a278d1d3dc450e42c65',
    'CX89200_J1.bin': 'b59bf5066f438263bed0c38a594209bc70494953e244cff063224f0333181826',
    'CX89200_KR2.bin': 'fdee34087520675bbfe705bfb8b37cfc871f1143202a73c01b9fbe6bc1d05748',
    'CX89200_UC2.bin': '0fa2005692fdc7ca76f5148696efca30559b7043f568412b9c1cec971753f335',
    'CX89201_AF1.bin': 'b9244f5ea4c48b04bf2ca8107900c9b7c168128b15df5858c6d4f0ff2ffb6370',
    'CX89201_ALLLANG.bin': '92697b50f6e3e25f5560a8c3eee357ea30b54e4e15cf29cd13bc30295759e3ce',
    'CX89201_AP2.bin': '0f072fc81a3148472bd22357af96af081502dc9721345ffc0d87d4f217ce54f1',
    'CX89201_CEC.bin': 'ce5110035e7429b88ef5261ed6b9d9895d29588b2072bdf7997e9516b6797bdc',
    'CX89201_CN2.bin': '84406c970097c6ceb46f2001528a08d3f1d5aad6cc926b0dbf5850e68a8901ec',
    'CX89201_IN5.bin': '124c4d7e6f6282675952db0b5a827d3123ba01f8aaf2f24376764ba5b7d1dc71',
    'CX89201_JE3.bin': 'b39366f9f5ae5704edc7f504afef485d526292a6619377a85e1243400b52e66b',
}
SIZES = {CC1: 0x2000, MATRIX: 0x7000, AWB: 0x1200}
SLOTS = (0x02cf0b69, 0x02cf0b6f, 0x02cf0b93, 0x02cf0b95, 0x02cf0b97, 0x02cf0b99)


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(4 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def relative(path):
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def property_map(payload, keys=(CC1, MATRIX, AWB)):
    banks = find_banks(payload)
    require(len(banks) == 2, 'Expected exactly two checksum-valid R5 BK4 banks')
    result = {}
    for key in keys:
        found = []
        for index, bank in enumerate(banks):
            try:
                found.append((index, bank.property(key)))
            except KeyError:
                pass
        require(len(found) == 1, f'Missing/ambiguous BK4 property {key:#x}')
        index, p = found[0]
        if key in SIZES:
            require(p.attributes == 8 and len(p.data) == SIZES[key], f'Unexpected colour property metadata {key:#x}')
        result[key] = (index, p)
    return banks, result


@dataclass(frozen=True)
class Field:
    key: int
    offset: int
    data: bytes
    purpose: str


def colour_fields(extra_updates=None):
    rows=json.loads((ROOT/'dependencies/colour_fields.json').read_text())
    fields=tuple(Field(r['key'],r['offset'],bytes.fromhex(r['hex']),r['purpose']) for r in rows)
    require(len(fields)==13 and sum(len(f.data) for f in fields)==2746,'Colour contract mismatch')
    return fields


def outside_equal(before, after, allowed):
    require(len(before) == len(after), 'Template length changed')
    cursor = 0
    for lo, hi in sorted(allowed):
        require(0 <= lo <= hi <= len(before), 'Bad allowlisted range')
        require(before[cursor:lo] == after[cursor:lo], f'Change outside approved ranges near {cursor:#x}')
        cursor = max(cursor, hi)
    require(before[cursor:] == after[cursor:], 'Change after approved ranges')


def patch_template(payload, stock, fields):
    banks, props = property_map(payload)
    stock_banks, stock_props = property_map(stock)
    require([(b.offset, b.size) for b in banks] == [(b.offset, b.size) for b in stock_banks], 'BK4 geometry drift')
    require(props[CC1][1].data[0xefe] == 0, 'Expected R5 difference encoding')
    output = bytearray(payload)
    allowed, affected, ledger = [], set(), []
    for f in fields:
        require(f.key in props and 0 <= f.offset <= len(props[f.key][1].data)-len(f.data), 'Field outside property')
        index, prop = props[f.key]
        sprop = stock_props[f.key][1]
        require((prop.file_offset, prop.attributes, len(prop.data)) ==
                (sprop.file_offset, sprop.attributes, len(sprop.data)), 'Property metadata drift')
        lo = prop.file_offset + f.offset
        hi = lo+len(f.data)
        require(all(hi <= a or lo >= b for a, b in allowed), 'Overlapping colour fields')
        before, original = payload[lo:hi], stock[lo:hi]
        require(before in (original, f.data), f'Unknown field preimage {f.key:#x}+{f.offset:#x}')
        output[lo:hi] = f.data
        allowed.append((lo, hi))
        affected.add(index)
        ledger.append({'property': f'0x{f.key:08X}', 'relative_offset': hex(f.offset), 'file_offset': lo,
                       'bytes': len(f.data), 'purpose': f.purpose,
                       'source_sha256': sha(before), 'target_sha256': sha(f.data)})
    for index in affected:
        b = banks[index]
        checksum = sum(output[b.offset:b.offset+32]) + sum(output[b.offset+36:b.offset+b.size])
        struct.pack_into('<I', output, b.offset+32, checksum)
        allowed.append((b.offset+32, b.offset+36))
    outside_equal(stock, payload, allowed)
    outside_equal(payload, output, allowed)
    _, final_props = property_map(bytes(output), tuple(props)+SLOTS)
    for key, spans in {CC1: [(0x1250+bank*64+48, 16) for bank in (0, 22, 23, 24, 25)],
                       MATRIX: [(0x1e0, 192), (0x360, 384)] + [(0x1e0+bank*768+576, 192) for bank in (22, 23, 24, 25)]}.items():
        for lo, size in spans:
            require(final_props[key][1].data[lo:lo+size] == stock_props[key][1].data[lo:lo+size], 'Protected tail/endpoint changed')
    _, old_slots = property_map(stock, SLOTS)
    require(all(final_props[k][1].data == old_slots[k][1].data for k in SLOTS), 'LOOK defaults changed')
    return bytes(output), ledger, allowed


def build_templates(source_tar, output_dir, extra_updates=None, *, expected_archive_sha256=None):
    """Return (tar-member -> replacement Path, manifest) for a package overlay.

    Accepts the original R5 4.00 archive or frozen strict4.04 archive, whose
    template payloads are identical. All source templates and CRC entries must
    match the pinned R5 defaults. No output is written before validation ends.
    """
    source_tar, output_dir = Path(source_tar).resolve(), Path(output_dir).resolve()
    archive_sha = sha_file(source_tar)
    if expected_archive_sha256 is not None:
        require(archive_sha == expected_archive_sha256, 'Source archive identity mismatch')
    fields = colour_fields(extra_updates)
    prepared, rows, source_payloads = {}, [], {}
    with tarfile.open(source_tar, 'r:') as t:
        members = t.getmembers()
        by = {m.name: m for m in members}
        require(len(by) == len(members), 'Duplicate TAR members')
        names = sorted(n for n, m in by.items() if n.startswith('0110_backup/') and n.endswith('.bin') and m.isfile())
        require(set(names) == {PREFIX+n for n in STOCK_HASHES}, 'Expected every one of the 12 GL templates')
        sum_before = t.extractfile(SUM).read()
        sum_lines = sum_before.decode('ascii').splitlines(keepends=True)
        sum_rows = {}
        for i, line in enumerate(sum_lines):
            p = line.rstrip('\r\n').split(',')
            require(len(p) == 12, 'Unexpected backup.sum row layout')
            require(p[10] not in sum_rows, 'Duplicate backup.sum path')
            sum_rows[p[10]] = (i, p)
        for name in names:
            m = by[name]
            before = t.extractfile(m).read()
            require(len(before) == m.size == 2372469, 'Template size mismatch')
            require(sha(before) == STOCK_HASHES[Path(name).name], 'Unknown R5 generic template identity')
            path = name.removeprefix('0110_backup/')
            require(path in sum_rows, 'Missing template CRC')
            i, parts = sum_rows[path]
            require(parts[0] == '0' and int(parts[1], 16) == binascii.crc32(before) & 0xffffffff and int(parts[2], 16) == len(before), 'Source template CRC/size mismatch')
            after, ledger, allowed = patch_template(before, before, fields)
            _, final_props = property_map(after)
            for bank in (22,23,24,25):
                at=0x1e0+bank*768
                target=next(f.data for f in fields if f.key==MATRIX and f.offset==at)
                require(final_props[MATRIX][1].data[at:at+576]==target,'FL23 matrix mismatch')
            repeated, _, _ = patch_template(after, before, fields)
            require(after == repeated, 'Template merge is not idempotent')
            source_payloads[name] = before
            prepared[name] = after
            changed = sum(a != b for a, b in zip(before, after))
            rows.append({'member': name, 'bytes': len(before), 'source_sha256': sha(before), 'target_sha256': sha(after),
                         'changed_bytes': changed, 'fields': ledger, 'allowed_file_ranges': allowed,
                         'source_crc32': parts[1], 'target_crc32': f'{binascii.crc32(after) & 0xffffffff:08x}',
                         'all_other_bytes_unchanged': True, 'bk4_checksums_valid': True, 'idempotent': True,
                         'FL23_four_full768_banks_equal_dynamic_donor': True,
                         'tar_offset_data': m.offset_data,
                         'tar_metadata': {k: v.hex() if isinstance(v, bytes) else v for k, v in m.get_info().items()}})
            replacement = parts[:]
            replacement[1] = f'{binascii.crc32(after) & 0xffffffff:08x}'
            ending = '\r\n' if sum_lines[i].endswith('\r\n') else '\n' if sum_lines[i].endswith('\n') else ''
            sum_lines[i] = ','.join(replacement) + ending
        # This R5 CRC list has 12 bin defaults and one unrelated MainDest file.
        bin_rows = {p[10] for _, p in sum_rows.values() if p[0] == '0' and p[10].endswith('.bin')}
        require(bin_rows == {n.removeprefix('0110_backup/') for n in names}, 'Unexpected or missing template CRC rows')
        sum_after = ''.join(sum_lines).encode('ascii')
        require(len(sum_after) == len(sum_before) == by[SUM].size, 'backup.sum layout changed')
        prepared[SUM] = sum_after
    manifest = {
        'schema': 'r5-sd-colour-preservation434/1', 'passed': True, 'camera_io': False,
        'upstream_commit': 'd4649e21f72e9074031c0c95c9ec2dc23ecb6807',
        'source_archive': relative(source_tar), 'source_archive_sha256': archive_sha,
        'matrix_mode': 'dynamic', 'why_not_upstream_default_fixed_a1': 'Preserve authorized 4.32 / 086df3b dynamic B/A1/A2 baseline; only adopt the template-preservation mechanism.',
        'count': len(rows), 'FL23_fields_each': 10, 'FL23_field_bytes_each': 2504,
        'additional_ST_AWB_ranges_each': 3, 'additional_ST_AWB_field_bytes_each': 242,
        'total_ranges_each': 13, 'total_field_bytes_each': 2746,
        'templates': rows, 'backup_sum': {'member': SUM, 'source_sha256': sha(sum_before), 'target_sha256': sha(sum_after),
                                       'updated_template_CRC_rows': 12, 'bytes': len(sum_after)},
        'preserved': ['LOOK six default slots', 'BK4 property attributes/indexes/geometry', 'all unrelated calibration and defaults',
                      'CC1 row tail16', 'block13 bank tail192', 'R5 ST block13 B/A2', 'MainDest and TAR headers/layout',
                      'native updater migration and save implementation'],
        'personalized_partition_embedded': False, 'AP_hooks_added': False,
        'build_script_sha256': sha(Path(__file__).read_bytes()),
    }
    require(sha_file(source_tar) == archive_sha, 'Source archive changed during preparation')
    output_manifest = output_dir / 'templates_manifest.json'
    require(not output_manifest.exists(), 'Refuse replacing a completed template generation')
    replacements = {}
    for name, payload in prepared.items():
        target = output_dir / name
        require(not target.exists() or target.read_bytes() == payload,
                'Refuse overwriting different prior template output')
        replacements[name] = target
    for name, target in replacements.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with target.open('xb') as f:
                f.write(prepared[name])
        require(target.read_bytes() == prepared[name], 'Template output write mismatch')
    manifest['replacements'] = {name: relative(path) for name, path in replacements.items()}
    original_hashes = {name: sha(payload) for name, payload in source_payloads.items()}
    original_hashes[SUM] = sha(sum_before)
    manifest['replacement_files'] = [
        {'member': name, 'path': relative(path), 'sha256': sha(prepared[name]),
         'source_sha256': original_hashes[name], 'bytes': len(prepared[name]),
         'tar_offset_data': by[name].offset_data}
        for name, path in replacements.items()]
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return replacements, manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-tar', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--expected-sha256')
    args = p.parse_args()
    replacements, manifest = build_templates(args.source_tar, args.output, expected_archive_sha256=args.expected_sha256)
    print(json.dumps({'passed': True, 'templates': manifest['count'], 'replacements': {n: relative(p) for n, p in replacements.items()},
                      'manifest': relative(args.output / 'templates_manifest.json')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
