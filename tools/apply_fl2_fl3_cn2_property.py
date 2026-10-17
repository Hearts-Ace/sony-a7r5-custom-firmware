#!/usr/bin/env python3
"""Patch only the supplied R5 4.00 mainland-China (CN2) backup copy.

Keep all original region/model data, properties and file geometry. Change
only four new-look mappings, four coefficient rows and their bank checksum.
"""
from __future__ import annotations
if __name__ == '__main__':
    raise SystemExit('Historical reference/helper only; standalone execution is disabled. See PUBLICATION.md.')

import argparse
import hashlib
import json
import struct
from pathlib import Path
from apply_fl2_fl3_property import MAP_SLOTS, row_data, PROPERTY_SHA
from sony_bk4 import find_banks

ROOT = Path(__file__).resolve().parents[1]
NAME = 'CX89201_CN2.bin'
BASELINE = ROOT / 'unpacked/r5/firmware/0110_backup/SYSIPSX-DSLR/GL' / NAME
BASE_SHA = '84406c970097c6ceb46f2001528a08d3f1d5aad6cc926b0dbf5850e68a8901ec'
SLOT_TYPES = {0x02cf0b69: 10, 0x02cf0b6f: 11}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def expected_bytes(raw, slot_types=False):
    assert digest(raw) == BASE_SHA, 'Unsupported R5 CN2 baseline'
    banks = find_banks(raw)
    assert len(banks) == 2
    bank = banks[1]
    prop = bank.property(0x02a40001)
    assert prop.attributes == 8 and len(prop.data) == 8192
    assert digest(prop.data) == PROPERTY_SHA
    payload = bytearray(prop.data)
    rows = row_data()
    for profile, (map_offset, value, row) in MAP_SLOTS.items():
        row_offset = 0x1250 + 64 * row
        assert payload[map_offset] == 0
        assert payload[row_offset:row_offset + 48] == bytes(48)
        assert row not in prop.data[0x1200:0x1250], 'New row already used by an original profile'
        payload[map_offset] = value
        payload[row_offset:row_offset + 48] = rows[profile]
    output = bytearray(raw)
    output[prop.file_offset:prop.file_offset + len(payload)] = payload
    if slot_types:
        for pid, value in SLOT_TYPES.items():
            slot_prop = banks[0].property(pid)
            assert slot_prop.attributes == 0x60 and slot_prop.data == bytes(1)
            output[slot_prop.file_offset] = value
    for target_bank in banks:
        changed_bank = output[target_bank.offset:target_bank.offset + target_bank.size]
        checksum = (sum(changed_bank[:0x20]) + sum(changed_bank[0x24:])) & 0xffffffff
        struct.pack_into('<I', output, target_bank.offset + 0x20, checksum)
    return bytes(output)


def verify(path, slot_types=False):
    baseline, actual = BASELINE.read_bytes(), Path(path).read_bytes()
    expected = expected_bytes(baseline, slot_types=slot_types)
    assert actual == expected, 'Changes outside exact CN2 target property/checksum plan'
    before, after = find_banks(baseline), find_banks(actual)
    assert [(b.offset, b.size, b.num_properties) for b in before] == [
        (b.offset, b.size, b.num_properties) for b in after]
    if not slot_types:
        assert actual[:before[1].offset] == baseline[:before[1].offset]
    prop = after[1].property(0x02a40001)
    slot_records = []
    for pid, value in SLOT_TYPES.items():
        b, a = before[0].property(pid), after[0].property(pid)
        assert a.attributes == b.attributes == 0x60
        assert a.data == (bytes([value]) if slot_types else b.data)
        slot_records.append({'property_id': hex(pid), 'before': b.data.hex(),
                             'after': a.data.hex(), 'attributes_unchanged': True})
    return {'region': 'CN2 / mainland China', 'container': NAME,
            'baseline_sha256': digest(baseline), 'sha256': digest(actual),
            'property_sha256': digest(prop.data), 'property_attributes': prop.attributes,
            'changed_bytes': sum(a != b for a, b in zip(baseline, actual)),
            'bank_count': len(after), 'all_discovered_bank_checksums_valid': True,
            'exact_property_and_checksum_diff_verified': True,
            'model_region_and_all_other_bytes_preserved': True,
            'slot_types_fixed': slot_types, 'slot_type_properties': slot_records,
            'maps': {hex(p): prop.data[mo] for p, (mo, _, _) in MAP_SLOTS.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=Path)
    parser.add_argument('--slot-types', action='store_true',
                        help='Also fix only CN2 slot16/17 type defaults; preserve attributes and adjustments')
    args = parser.parse_args()
    output = args.build / 'patched' / NAME
    assert not output.exists(), 'Refusing to overwrite an existing candidate'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(expected_bytes(BASELINE.read_bytes(), slot_types=args.slot_types))
    try:
        report = verify(output, slot_types=args.slot_types)
    except Exception:
        output.unlink()
        raise
    evidence = args.build / 'evidence/cn2_property.json'
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
