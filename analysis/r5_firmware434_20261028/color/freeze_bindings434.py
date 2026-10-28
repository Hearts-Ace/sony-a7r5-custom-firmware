#!/usr/bin/env python3
"""Bind the 4.34 parameter sources/receipts after the actual validations pass."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRESERVE = HERE.parent/'preservation'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    old_path = ROOT/'analysis/r5_firmware433_20261028/color/source_bindings.json'
    old = json.loads(old_path.read_text())
    paths = []
    for row in old['rows']:
        if row['path'].startswith('analysis/r5_firmware433_20261028/color/'):
            name = row['path'].replace('r5_firmware433_20261028', 'r5_firmware434_20261028').replace('color433', 'color434')
        else:
            name = row['path']
        path = ROOT/name
        data = path.read_bytes()
        if name == row['path']:
            assert len(data) == row['bytes'] and sha(data) == row['sha256']
        paths.append(path)
    paths += [Path(__file__), HERE/'integrated_templates_check.json', PRESERVE/'compare_433_templates.py',
              PRESERVE/'compared_433_templates.json', HERE.parent/'verify_templates434.py',
              PRESERVE/'prepare_templates.py', PRESERVE/'verify_templates.py',
              PRESERVE/'verification.json', PRESERVE/'generated/templates_manifest.json']
    required_reports = [HERE/'color434_verified.json', HERE/'integrated_templates_check.json',
                        PRESERVE/'verification.json', PRESERVE/'compared_433_templates.json']
    assert all(json.loads(p.read_text())['passed'] for p in required_reports)
    rows = []
    for p in sorted(set(paths)):
        data = p.read_bytes()
        rows.append({'path': str(p.relative_to(ROOT)), 'sha256': sha(data), 'bytes': len(data)})
    binding = {'schema': 'r5-color434-source-bindings/1', 'camera_io': False,
               'origin_433_bindings': {'path': str(old_path.relative_to(ROOT)), 'sha256': sha(old_path.read_bytes())},
               'AWB_white97_ambience_minus1': True, 'R6_ST_and_FL23_preserved_from433': True, 'rows': rows}
    output = HERE/'source_bindings.json'
    assert not output.exists()
    output.write_text(json.dumps(binding, indent=2, ensure_ascii=False)+'\n')
    upstream = []
    for p in sorted((PRESERVE/'upstream').iterdir()):
        if p.is_file():
            data = p.read_bytes()
            upstream.append({'path': str(p.relative_to(PRESERVE)), 'bytes': len(data), 'sha256': sha(data)})
    main_commit = json.loads((PRESERVE/'upstream/main_commit.json').read_text())
    assert main_commit['sha'] == 'd4649e21f72e9074031c0c95c9ec2dc23ecb6807'
    assert (PRESERVE/'upstream/sd-colour-preservation.md').read_bytes() == (PRESERVE/'upstream/sd-colour-preservation.pinned.md').read_bytes()
    upstream_manifest = {'upstream': 'https://github.com/Erlla/sony-a7m4-custom-firmware',
                         'commit': main_commit['sha'], 'reference_only': True, 'direct_source_imported': False,
                         'files': upstream, 'adaptation': 'R5 twelve GL templates, dynamic endpoints and R6 ST preserved; white97/ambience-1; no AP runtime hooks',
                         'original_m4_template_count': 32, 'r5_template_count': 12,
                         'source_note': 'Rebound local copies of the 4.33 pinned upstream evidence; no new upstream fetch for this AWB-only adjustment.'}
    (PRESERVE/'upstream_manifest.json').write_text(json.dumps(upstream_manifest, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({'passed': True, 'source_rows': len(rows), 'source_bindings_sha256': sha(output.read_bytes()),
                      'upstream_manifest_sha256': sha((PRESERVE/'upstream_manifest.json').read_bytes())}))


if __name__ == '__main__':
    main()
