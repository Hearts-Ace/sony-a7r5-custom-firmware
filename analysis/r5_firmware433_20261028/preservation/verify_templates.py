#!/usr/bin/env python3
"""Verify real default-template merges and original R5 migration instructions.

Native migration helpers for headers, property lookup and memcpy are modeled;
this is not a full updater/OS/VFS execution or physical persistence evidence.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.dont_write_bytecode = True
sys.path[:0] = [str(HERE), str(ROOT/'tools'), str(ROOT/'vendor/audit-python')]
import prepare_templates as prepare


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reject(label, fn):
    try:
        fn()
    except ValueError as e:
        return {'name': label, 'rejected': True, 'error': str(e)}
    raise AssertionError('Expected rejection: '+label)


def repair_checksum(data):
    # The second bank's geometry is pinned by the unmodified original template.
    out = bytearray(data)
    original = (ROOT/'unpacked/r5/firmware/0110_backup/SYSIPSX-DSLR/GL/CX89200_ALLLANG.bin').read_bytes()
    for b in prepare.find_banks(original):
        checksum = sum(out[b.offset:b.offset+32]) + sum(out[b.offset+36:b.offset+b.size])
        struct.pack_into('<I', out, b.offset+32, checksum)
    return bytes(out)


def main():
    manifest_path = HERE/'generated/templates_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assert manifest['passed'] and manifest['count'] == 12
    for row in manifest['replacement_files']:
        p = ROOT/row['path']
        data = p.read_bytes()
        assert len(data) == row['bytes'] and sha(data) == row['sha256']
    source = ROOT/'unpacked/r5/firmware/0110_backup/SYSIPSX-DSLR/GL/CX89200_ALLLANG.bin'
    target = HERE/'generated/0110_backup/SYSIPSX-DSLR/GL/CX89200_ALLLANG.bin'
    before, after = source.read_bytes(), target.read_bytes()
    fields = prepare.colour_fields()
    assert prepare.patch_template(before, before, fields)[0] == after
    assert prepare.patch_template(after, before, fields)[0] == after
    _, props = prepare.property_map(before)
    damaged = bytearray(before)
    damaged[props[prepare.CC1][1].file_offset+0x1250] ^= 1
    bad_preimage = repair_checksum(damaged)
    unrelated = bytearray(before)
    unrelated[props[prepare.CC1][1].file_offset+0x1100] ^= 1
    unknown_outside = repair_checksum(unrelated)
    corrupt_checksum = bytearray(before)
    corrupt_checksum[0x20] ^= 1
    negatives = [
        reject('checksum_corruption', lambda: prepare.patch_template(corrupt_checksum, before, fields)),
        reject('unknown_valid_checksum_ST_preimage', lambda: prepare.patch_template(bad_preimage, before, fields)),
        reject('unrelated_valid_checksum_byte_change', lambda: prepare.patch_template(unknown_outside, before, fields)),
        reject('overlapping_fields', lambda: prepare.patch_template(before, before, fields+(fields[0],))),
    ]
    # Source-bounded original migration core; import its policy helper only.
    harness_path = ROOT/'analysis/r5_fl23_st_color_audit_20261016/replay_update_preservation.py'
    harness = load(harness_path, 'r5_original_migration_harness433')
    kernels = {
        'original_update_initrd': ('analysis/r5_live_system_20261014/boot_probe_B/update_initrd/usr/kmod/backup.ko', 0x2a8,
                                   '03fd3ade000ba8953d1e9c5c412d527a97de2648b701008456bb4cd79bc12f69'),
        'stock_application_rootfs': ('unpacked/r5/usr_complete/kmod/backup.ko', 0xbc8,
                                     '8e794d5a02f973e7220fc65baec8fd33bf0fe33dc92939abbb70f16da9502cc5'),
    }
    _, old_props = prepare.property_map(before, (prepare.CC1, prepare.MATRIX, prepare.AWB)+prepare.SLOTS)
    _, new_props = prepare.property_map(after, (prepare.CC1, prepare.MATRIX, prepare.AWB)+prepare.SLOTS)
    runs = []
    for label, (path, entry, expected) in kernels.items():
        kernel = ROOT/path
        assert sha(kernel.read_bytes()) == expected
        for key in (prepare.CC1, prepare.MATRIX, prepare.AWB):
            attr = new_props[key][1].attributes
            assert attr == 8
            for mode in (0, 2, 4, 5):
                result = harness.policy(kernel, entry, old_props[key][1].data, new_props[key][1].data, attr, mode)
                assert result['equals_template'] and not result['equals_old'] and not result['copied_old_value']
                runs.append({'kernel': label, 'mode': mode, 'property': f'0x{key:08X}', 'attributes': attr,
                             'bytes': len(new_props[key][1].data), **result})
        for key, enabled in zip(prepare.SLOTS, (10, 11, 10, 11, 10, 11)):
            attr = new_props[key][1].attributes
            assert attr == 0x60 and new_props[key][1].data == b'\0'
            for mode in (0, 2, 4, 5):
                result = harness.policy(kernel, entry, bytes([enabled]), new_props[key][1].data, attr, mode)
                assert result['copied_old_value'] == result['equals_old'] == (mode == 5)
                assert result['equals_template'] == (mode != 5)
                runs.append({'kernel': label, 'mode': mode, 'property': f'0x{key:08X}', 'attributes': attr,
                             'synthetic_enabled_old': enabled, **result})
    report = {
        'schema': 'r5-template433-native-migration/1', 'passed': True, 'camera_io': False,
        'templates_manifest_sha256': sha(manifest_path.read_bytes()),
        'template_count': 12, 'patched_templates_BK4_checksums_and_native_ranges_verified': True,
        'all_full_dynamic_donor_banks_verified': True, 'idempotence_passed': True,
        'negative_checks': negatives,
        'native_core_cases': len(runs), 'native_runs': runs,
        'kernels': {name: {'path': path, 'sha256': digest, 'text_entry': hex(entry)}
                    for name, (path, entry, digest) in kernels.items()},
        'native_harness': {'path': str(harness_path.relative_to(ROOT)), 'sha256': sha(harness_path.read_bytes())},
        'findings': [
            'For all four reviewed modes, attrs8 AWB/CC1/block13 are selected from the new template, including R6 ST/AWB changes and FL23 fields.',
            'Under mode5, the six enabled LOOK slots (attrs0x60) are copied from the old settings while patched template colour properties remain active.',
            'Other modes do not preserve enabled LOOK slots; untouched generic LOOK defaults deliberately stay zero.',
            'No AP runtime writes or updater/Backup instruction patches are required by this preservation method.',
        ],
        'limits': [
            'Runs execute original ARM64 migration policy with modeled valid property/header services and memcpy, not complete Backup parsing, updater, VFS or device hardware.',
            'Native parser/checksum verification of all real generated templates is independent of the modeled migration helper boundary.',
            'Actual selected UUD/Backup mode on the user camera is not observed; already-enabled LOOK preservation is demonstrated for reviewed mode5 only.',
            'No personal settings/restore image is generated, embedded, written or reused.',
            'Install, readback, eMMC/physical-NOR consistency and final camera behaviour need separate device acceptance.',
        ],
    }
    output = HERE/'verification.json'
    assert not output.exists(), 'Refuse overwriting prior execution evidence'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'passed': True, 'templates': 12, 'native_cases': len(runs), 'negative_checks': len(negatives),
                      'report': str(output.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == '__main__':
    main()
