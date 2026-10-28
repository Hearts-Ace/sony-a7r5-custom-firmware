#!/usr/bin/env python3
"""Independently prove 4.34 templates only tune AWB white112 to white97.

R6 ST, FL23 dynamic endpoints and all other saved template content must stay
byte-identical to frozen 4.33, except the necessary BK4 checksum and CRC rows.
"""
from pathlib import Path
import binascii
import hashlib
import importlib.util
import json
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'tools'))
from sony_bk4 import find_banks


def sha(data):
    return hashlib.sha256(data).hexdigest()


def manifest(path):
    value = json.loads(path.read_text())
    assert value['passed'] and value['count'] == 12 and value['matrix_mode'] == 'dynamic'
    files = {r['member']: (ROOT/r['path'], r) for r in value['replacement_files']}
    assert len(files) == 13
    for p, r in files.values():
        data = p.read_bytes()
        assert len(data) == r['bytes'] and sha(data) == r['sha256']
    return value, files


def main():
    old_path = ROOT/'analysis/r5_firmware433_20261028/preservation/generated/templates_manifest.json'
    new_path = HERE/'generated/templates_manifest.json'
    old, old_files = manifest(old_path)
    new, new_files = manifest(new_path)
    assert old_files.keys() == new_files.keys()
    rows = []
    for name in sorted(n for n in old_files if n.endswith('.bin')):
        before, after = old_files[name][0].read_bytes(), new_files[name][0].read_bytes()
        a, b = find_banks(before), find_banks(after)
        assert len(a) == len(b) == 2 and [(x.offset, x.size) for x in a] == [(x.offset, x.size) for x in b]
        awb_a, awb_b = a[1].property(0x02a40000), b[1].property(0x02a40000)
        assert awb_a.file_offset == awb_b.file_offset
        assert awb_a.data[0x930:0x934] == b'\x70\xff\x00\x06'
        assert awb_b.data[0x930:0x934] == b'\x61\xff\x00\x06'
        expected = bytearray(before)
        offset = awb_b.file_offset+0x930
        expected[offset] = 97
        checksum_offset = b[1].offset+32
        expected[checksum_offset:checksum_offset+4] = after[checksum_offset:checksum_offset+4]
        assert bytes(expected) == after
        assert all(a[1].property(k).data == b[1].property(k).data for k in (0x02a40001,0x02a4000d))
        rows.append({'member': name, 'old_sha256': sha(before), 'new_sha256': sha(after),
                     'AWB_parameter_file_offset': offset, 'BK4_checksum_offset': checksum_offset,
                     'changed_offsets': [i for i, (x, y) in enumerate(zip(before, after)) if x != y],
                     'only_white_priority_and_BK4_checksum_changed': True,
                     'R6_ST_and_FL23_CC1_block13_byte_identical': True,
                     'ambience_minus1_and_companions_preserved': True})
    assert len(rows) == 12
    sum_name = '0111_backup_sum/backup.sum'
    before, after = old_files[sum_name][0].read_bytes(), new_files[sum_name][0].read_bytes()
    assert len(before) == len(after)
    changes = []
    for x, y in zip(before.decode().splitlines(keepends=True), after.decode().splitlines(keepends=True)):
        a, b = x.rstrip('\r\n').split(','), y.rstrip('\r\n').split(',')
        assert len(a) == len(b) == 12 and a[10] == b[10]
        name = '0110_backup/'+a[10]
        if name in old_files:
            assert a[:1]+a[2:] == b[:1]+b[2:]
            assert int(a[1],16) == binascii.crc32(old_files[name][0].read_bytes()) & 0xffffffff
            assert int(b[1],16) == binascii.crc32(new_files[name][0].read_bytes()) & 0xffffffff
            changes.append(name)
        else:
            assert x == y
    assert len(changes) == 12
    # Invoke the root independent checker without importing the generation code.
    checker_path = HERE.parent/'verify_templates434.py'
    spec = importlib.util.spec_from_file_location('independent_templates434', checker_path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    _, independent = checker.verify()
    assert independent['passed'] and independent['AWB_bytes'] == '61ff0006'
    report = {'schema': 'r5-template434-vs433/1', 'passed': True, 'camera_io': False,
              'old_manifest': {'path': str(old_path.relative_to(ROOT)), 'sha256': sha(old_path.read_bytes())},
              'new_manifest': {'path': str(new_path.relative_to(ROOT)), 'sha256': sha(new_path.read_bytes())},
              'templates': rows, 'template_count': 12, 'backup_sum_only_CRC12_changed': True,
              'backup_sum': {'old_sha256': sha(before), 'new_sha256': sha(after)},
              'independent_current_template_check': independent,
              'checker_sha256': sha(checker_path.read_bytes()),
              'limits': ['Offline generic-template comparison; no current camera, personal settings or image-quality observation.']}
    output = HERE/'compared_433_templates.json'
    assert not output.exists()
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    # Retain the conventional independent colour receipt used by the root gate.
    integrated_path = HERE.parent/'color/integrated_templates_check.json'
    assert not integrated_path.exists()
    integrated_path.write_text(json.dumps({**independent, 'schema':'r5-color434-integrated-templates/1',
                                         'only_awb_white_differs_from433': True,
                                         'comparison_receipt_sha256': sha(output.read_bytes())}, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'passed': True, 'templates': len(rows), 'only_AWB930_and_BK4_checksum_changed': True,
                      'backup_sum_CRCs': 12, 'AWB_bytes':'61ff0006'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
