#!/usr/bin/env python3
"""Repackage the verified M4-method R5 4.03 as 4.04, with no feature changes.

Offline only. Preserves the source build and verifies the exact DAT byte diff.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from build_r5_m4strict_release import ROOT, STEPS, digest_file, require

SOURCE = ROOT / 'build_r5_m4strict_4.03_20261015'
SOURCE_SHA = 'da1a641acfc2cd5c8a22124d76c6c4ca59ce225351917766fb73a369bd314abb'
OUT = ROOT / 'build_r5_m4strict_4.04_20261015'


def verify_version_only(source, build):
    sys.path.insert(0, str(ROOT / 'vendor/audit-python'))
    from sign_r5_firmware import inspect
    old_report = json.loads((source / 'verification.json').read_text())
    report = json.loads((build / 'verification.json').read_text())
    require(old_report['version'] == '4.03' and report['version'] == '4.04', 'Wrong version transition')
    for field in ('components', 'archive_sha256', 'updater_sha256', 'public_key_sha256',
                  'changed_tar_members', 'output_bytes'):
        require(old_report[field] == report[field], 'Feature/signing input changed: ' + field)
    old_header = (source / 'FDAT.header.4.03.bin').read_bytes()
    header = (build / 'FDAT.header.4.04.bin').read_bytes()
    positions = [i for i, (a, b) in enumerate(zip(old_header, header)) if a != b]
    require(len(old_header) == len(header) == 512 and old_header[32:34] == b'\x03\x04' and
            header[32:34] == b'\x04\x04' and set(positions) <= {8, 9, 10, 11, 32},
            'Unexpected plaintext header change')
    old = inspect(source / 'BODYDATA.DAT')
    new = inspect(build / 'BODYDATA.DAT')
    require(old['chunks'] == new['chunks'] and old['size'] == new['size'], 'DAT geometry changed')
    allowed = [
        (new['signed_offset'], new['signed_offset'] + 512),
        (new['signature_offset'], new['signature_offset'] + 256),
        (new['dend_crc_offset'], new['dend_crc_offset'] + 4),
    ]
    differences = []
    with (source / 'BODYDATA.DAT').open('rb') as a, (build / 'BODYDATA.DAT').open('rb') as b:
        offset = 0
        while True:
            before, after = a.read(4 << 20), b.read(4 << 20)
            require(len(before) == len(after), 'DAT sizes differ')
            if not before:
                break
            if before != after:
                for i, (x, y) in enumerate(zip(before, after)):
                    if x != y:
                        pos = offset + i
                        require(any(lo <= pos < hi for lo, hi in allowed), 'Unexpected DAT byte change')
                        differences.append(pos)
            offset += len(before)
    result = dict(
        source=str(source / 'BODYDATA.DAT'), source_sha256=SOURCE_SHA,
        output_sha256=digest_file(build / 'BODYDATA.DAT'),
        version_before='4.03', version_after='4.04',
        same_components_archive_updater_and_signing_key=True,
        header_changed_offsets=positions, changed_container_bytes=len(differences),
        allowed_container_ranges=[{'start': lo, 'end_exclusive': hi} for lo, hi in allowed],
        every_other_container_byte_identical=True, camera_io=False, passed=True,
        scope='Version/header CRC, dependent encrypted header block, RSA signature and outer CRC only')
    require(result['output_sha256'] == report['output_sha256'], 'Final DAT identity mismatch')
    (build / 'evidence/version_bump_verification.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=OUT)
    args = parser.parse_args()
    build = args.build.resolve()
    require(not build.exists(), 'Choose a new output directory')
    require(digest_file(SOURCE / 'BODYDATA.DAT') == SOURCE_SHA, 'Verified 4.03 source differs')
    source_report = json.loads((SOURCE / 'verification.json').read_text())
    require(source_report['output_sha256'] == SOURCE_SHA and
            digest_file(SOURCE / 'patched/firmware.tar') == source_report['archive_sha256'],
            'Source report/archive identity mismatch')
    (build / 'patched').mkdir(parents=True)
    (build / 'evidence').mkdir()
    for kind, _, name in STEPS:
        component = SOURCE / 'patched' / name
        require(digest_file(component) == source_report['components'][name]['sha256'], 'Component identity mismatch')
        shutil.copyfile(component, build / 'patched' / name)
        shutil.copytree(SOURCE / 'evidence' / kind, build / 'evidence' / kind)
    shutil.copytree(SOURCE / 'evidence/settings', build / 'evidence/settings')
    provenance = {'source_build': str(SOURCE), 'source_package_sha256': SOURCE_SHA,
                  'components_and_evidence_reused_without_changes': True,
                  'new_component_tests_run': False, 'camera_io': False}
    (build / 'evidence/reuse_provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    subprocess.run([sys.executable, str(ROOT / 'tools/build_r5_m4strict_release.py'),
                    '--build', str(build), '--version', '4.04', '--verified-components-only'], check=True, cwd=ROOT)
    result = verify_version_only(SOURCE, build)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
