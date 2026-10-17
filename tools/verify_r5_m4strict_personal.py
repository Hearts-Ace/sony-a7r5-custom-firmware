#!/usr/bin/env python3
"""Check personal-image adaptation against historical images; never save flash images."""
import argparse
import json
from pathlib import Path
import struct

from build_r5_m4strict_personal import ROOT, SLOTS, KNOWN_HISTORICAL, Fat, bk4_rows, build_image, donors, patch_backup, require, sha, unique
from a7m4 import fl23


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    out = args.build / 'evidence/settings'
    out.mkdir(parents=True, exist_ok=True)
    sources = [ROOT / 'backups/R5_4.00_20261014_full/nflasha2.logical.A.img',
               ROOT / 'analysis/r5_402_gray_audit_20261015/installed_settings_A/nflasha2.logical.img']
    donor_cc, donor_matrix = donors()
    rows = []
    for path in sources:
        source = path.read_bytes()
        require(sha(source) in KNOWN_HISTORICAL, 'Historical test input identity mismatch')
        output, report = build_image(source)
        repeated, _ = build_image(output)
        require(repeated == output, 'Personal patch is not idempotent')
        original_fs, expected_fs = Fat(source), Fat(source)
        author_slots = fl23.SLOTS
        try:
            # Independent author's algorithm with only the six R5 IDs substituted.
            fl23.SLOTS = dict(SLOTS)
            for name in ('BACKUP.BIN', 'BACKUP.BAK'):
                expected_fs.replace(name, fl23.patch_backup(original_fs.read(name), donor_cc, donor_matrix))
        finally:
            fl23.SLOTS = author_slots
        require(expected_fs.bytes() == output, 'Adaptation differs from author algorithm after R5 ID substitution')
        report.update(input_path=str(path), historical_state=KNOWN_HISTORICAL[sha(source)],
                      author_algorithm_equal_with_r5_ids=True, idempotent=True,
                      output_image_saved=False, current_state_verified=False)
        rows.append(report)
    payload = Fat(sources[0].read_bytes()).read('BACKUP.BIN')
    layout = bk4_rows(payload)
    bad = bytearray(payload)
    bad[unique(layout, 0x02cf0b69)['offset']] = 1
    try:
        patch_backup(bytes(bad), donor_cc, donor_matrix)
    except Exception:
        checksum_rejected = True
    else:
        raise ValueError('Checksum corruption was accepted')
    for row in layout:
        start, extent = row['base'], row['extent']
        struct.pack_into('<I', bad, start + 0x20, sum(bad[start:start + 0x20]) + sum(bad[start + 0x24:start + extent]))
    try:
        patch_backup(bytes(bad), donor_cc, donor_matrix)
    except ValueError:
        unknown_slot_rejected = True
    else:
        raise ValueError('Unsupported slot preimage was accepted')
    bad_color = bytearray(payload)
    bad_color[unique(layout, 0x02a40001)['offset'] + 0x100] ^= 1
    for row in layout:
        start, extent = row['base'], row['extent']
        struct.pack_into('<I', bad_color, start + 0x20, sum(bad_color[start:start + 0x20]) + sum(bad_color[start + 0x24:start + extent]))
    try:
        patch_backup(bytes(bad_color), donor_cc, donor_matrix)
    except ValueError:
        unknown_color_rejected = True
    else:
        raise ValueError('Unknown non-target color data was accepted')
    result = {'passed': True, 'camera_io': False, 'historical_inputs_only': True,
              'current_camera_state_verified': False, 'any_partition_image_saved': False,
              'nflasha6_modified': False, 'cases': rows,
              'negative_checks': {'invalid_bk4_checksum_rejected': checksum_rejected,
                                  'unsupported_slot_value_rejected': unknown_slot_rejected,
                                  'unknown_color_baseline_rejected': unknown_color_rejected}}
    (out / 'personal_verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'historical_cases': len(rows), 'any_partition_image_saved': False,
                      'camera_io': False, 'output': str(out / 'personal_verification.json')}))


if __name__ == '__main__':
    main()
