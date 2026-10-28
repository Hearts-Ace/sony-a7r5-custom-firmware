"""Freeze source/receipt bindings after successful bounded icon investigation."""
from pathlib import Path
import hashlib
import json
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    stock = json.loads((HERE / 'stock_icons.json').read_text())
    images = json.loads((HERE / 'image_resources.json').read_text())
    mapping = json.loads((HERE / 'look_mapping.json').read_text())
    ap = ROOT / 'analysis/r5_firmware433_20261028/ap/appFw.so'
    assert stock['passed'] and images['passed']
    assert stock['AP_sha256'] == images['AP_sha256'] == sha(ap)
    assert stock['script_sha256'] == sha(HERE / 'replay_stock_icons.py')
    assert images['script_sha256'] == sha(HERE / 'verify_image_resources.py')
    assert images['oracle_sha256'] == sha(HERE / 'stock_icons.json')
    assert len(stock['cases']) == 24 and images['resource_cases'] == len(images['cases']) == 48
    assert len(mapping) == 12 and images['look_mapping'] == mapping
    assert {c['bias'] for c in stock['cases']} == {'0x0', '0x40000000'}
    for item in mapping:
        path = ROOT / item['source']['file']
        assert sha(path) == item['source']['sha256']
    sources = {ap, ROOT / images['libObj_path'], ROOT / images['lz77_reference']['path']}
    sources.update(ROOT / i['source']['file'] for i in mapping)
    for case in images['cases']:
        path = ROOT / case['file']
        blob = path.read_bytes()
        assert sha(path) == case['file_sha256']
        at = int(case['record_offset'], 16)
        entry = blob[at:at + 20]
        assert hashlib.sha256(entry).hexdigest() == case['record_sha256']
        assert entry.hex() == case['record_hex']
        assert struct.unpack_from('<I', entry)[0] == int(case['stored_resource'], 16)
        start = int(case['payload_offset'], 16)
        payload = blob[start:start + case['payload_bytes']]
        assert len(payload) == case['payload_bytes']
        assert hashlib.sha256(payload).hexdigest() == case['payload_sha256']
        assert case['native_record_type'] == 6 and case['decoded_bytes'] == 5600
        sources.add(path)
    assert images['bad_resource_image_lookup_rejected']
    assert images['bad_resource_is_help_string']
    sources.update(ROOT / row['file'] for row in images['bad_resource_is_help_string'])
    for relative in ('analysis/r5_firmware433_20261028/fn/replay_fn_save433.py',
                     'analysis/r5_firmware433_20261028/fn/replay_fn433.py',
                     'analysis/r5_firmware433_20261028/fn/patch_fn433.py',
                     'analysis/r5_firmware433_20261028/replay_main_menu425.py',
                     'analysis/r5_firmware433_20261028/import/module_audit.json',
                     'analysis/r5_custom_filter423_20261023/menu_research/read_menu.py'):
        sources.add(ROOT / relative)
    assert sha(ROOT / images['libObj_path']) == images['libObj_sha256']
    assert sha(ROOT / images['lz77_reference']['path']) == images['lz77_reference']['sha256']
    receipt = dict(passed=True, AP_sha256=stock['AP_sha256'], native_selector_cases=24,
                   native_resource_cases=48, independent_record_payload_rechecks=48,
                   original_image_files=6, help_string_negative=True,
                   final_434_private_forwarding_out_of_scope=True)
    (HERE / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    artifacts = [p for p in sorted(HERE.iterdir()) if p.is_file() and p.name != 'frozen_manifest.json']
    manifest = dict(passed=True, AP_sha256=stock['AP_sha256'],
                    artifacts=[dict(path=str(p.relative_to(ROOT)), sha256=sha(p)) for p in artifacts],
                    sources=[dict(path=str(p.relative_to(ROOT)), sha256=sha(p)) for p in sorted(sources)])
    target = HERE / 'frozen_manifest.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(receipt, manifest_sha256=sha(target),
                          artifacts=len(artifacts), sources=len(sources))))


if __name__ == '__main__':
    main()
