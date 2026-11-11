#!/usr/bin/env python3
"""Emit the 20-site replacement UI fragment and AP+UI noninstallable plan."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(HERE.parent / 'integration'), str(ROOT / 'vendor/audit-python'),
               str(ROOT / 'projects/firmware/development/shutter-sound-recovery455/src/lib')]
from inspect_ui import BASE, BASE_SHA, CREATE, DRAW
from inspect_ap import Image
from strict_ap_link import branch
from compile_ui import UI_NATIVE, UI_SOURCES, CANCEL_SOURCES


def make(output, module, ap_contract):
    assert not output.exists(), 'Contract directory must be new'
    image = Image(BASE)
    assert hashlib.sha256(image.raw).hexdigest() == BASE_SHA
    build = json.loads((module / 'module.json').read_text())
    patches = []
    def patch(va, kind, symbol, expected, reason):
        before = image.raw[image.offset(va):image.offset(va) + 4]
        assert before == expected, (hex(va), before.hex(), expected.hex())
        assert symbol in build['symbols']
        branch(va, build['symbols'][symbol], kind == 'BL')
        patches.append(dict(va=hex(va), kind=kind, before=before.hex(), symbol=symbol, reason=reason))
    for i, va in enumerate(CREATE):
        patch(va, 'BL', 'r5_ui_create_hook', bytes.fromhex('00013fd6'),
              'Five-page create/rotation: temporarily enable only native target row; restore flags; bind canvas generation')
    for i, va in enumerate(DRAW):
        patch(va, 'BL', 'r5_ui_page_hook_' + str(i), bytes.fromhex('40003fd6'),
              ('Selection', 'Fn38', 'Fn76')[i] + ': original virtual update first; empty-image native Sprite mask from eligible completed snapshot')
    for i, (va, instruction) in enumerate(((0x2146224, '003c4191'), (0x2156e70, '001c4191'))):
        patch(va, 'B', 'r5_ui_guide_model_' + str(i), bytes.fromhex(instruction),
              'Original model gate first; override only column16 target row for same-page registered completed full-token private Guide')
    for va, symbol in ((0x182e138, 'r5_ui_guide_update'), (0x182e1ac, 'r5_ui_guide_destroy')):
        patch(va, 'B', symbol, bytes.fromhex('fd7bbea9'),
              'Replace old guide wrapper; preserve original native update/destroy and own-pointer lifecycle')
    patch(0x240de2c, 'B', 'r5_ui_guide_show', struct.pack('<I', 0x35000000 | (((0x240db10 - 0x240de2c) // 4) & 0x7ffff) << 5),
          'Keep original CBNZ unless scoped cookie exactly matches producer parameter x20; preserve flags and scratch GPRs')
    for va in (0x1d9bb74, 0x1e17b1c):
        patch(va, 'BL', 'r5_ui_guide_produce', branch(va, 0x240dae0, True),
              'Native body for eligible private still snapshot; publish only after generation/pointer/full token and validity recheck')
    old_sites = (0x1d9ba18, 0x1e179e0, 0x1d1574c, 0x1d15664,
                 0x1d9bb74, 0x1e17b1c, 0x182e138, 0x182e1ac)
    fragment = dict(schema='r5-aspect456-ui-contract/1', status='REVIEWED_UI_PATCH_CONTRACT',
                    base_sha256=BASE_SHA, module_manifest_sha256=hashlib.sha256((module / 'module.json').read_bytes()).hexdigest(),
                    patches=patches, rela_remaps=[], native_symbols=UI_NATIVE,
                    replace_old_guide_sites=[hex(v) for v in old_sites],
                    exclude_sources=['integration/r5_aspect_guide.c', 'integration/r5_aspect_guide_hooks.S'],
                    sources={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in UI_SOURCES + (HERE / 'ui_preview.h', HERE / 'preview_core.h')},
                    pages=['shoot585', 'shoot442', 'Fn38', 'Fn76', 'selection'],
                    ratios=['1.618:1', '2.39:1', '5:4', '1.85:1'], aliases=['0x1660', '0x1661', '0x1662', '0x1663'],
                    runtime_claim='Pending hash-bound offline replay; patch contract is not camera validation',
                    physical_device_verified=False, installable=False,
                    limitations=['Replace, do not stack, old guide source and implicit append hooks',
                                 'Native dynamic exposure/display/output gates are not bypassed',
                                 'Cancel persistence belongs to separately reviewed AP integration',
                                 'No diagnostics, resource/menu reorder, RAW, encoder, package/sign or device operation'])
    ap = json.loads(ap_contract.read_text())
    assert ap['base_sha256'] == BASE_SHA and ap['status'] == 'REVIEWED_AP_CONTRACT'
    assert not set(r['va'] for r in ap['patches']) & set(r['va'] for r in patches)
    ap['schema'] = 'r5-aspect456-ap-plus-ui-contract/1'
    cancel = json.loads((HERE.parent / 'cancel/candidate-f/contract.json').read_text())
    cancel_sites = {0x2adfd3c, 0x2adfd5c, 0x1bd64c8, 0x1bd64d4}
    cancel_rows = [p for p in cancel['patches'] if int(p['va'], 0) in cancel_sites]
    assert len(cancel_rows) == 4
    assert not cancel_sites & {int(p['va'], 0) for p in ap['patches']}
    ap['patches'] += cancel_rows
    ap['cancel_contract'] = dict(source_contract_sha256=hashlib.sha256((HERE.parent / 'cancel/candidate-f/contract.json').read_bytes()).hexdigest(),
                                 patches=cancel_rows,
                                 sources={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in CANCEL_SOURCES})
    ap['patches'] += patches
    ap['ui_contract'] = fragment
    ap['review_scope'] += ['Five-page UI fragment replaces all old guide-only bindings; no implicit patch list']
    assert len({int(p['va'], 0) for p in ap['patches']}) == len(ap['patches'])
    output.mkdir(parents=True)
    (output / 'ui-contract.json').write_text(json.dumps(fragment, indent=2) + '\n')
    (output / 'integration.json').write_text(json.dumps(ap, indent=2) + '\n')
    print(json.dumps(dict(ui_patches=len(patches), all_patches=len(ap['patches']), rela_remaps=len(ap['rela_remaps']))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', type=Path, required=True)
    parser.add_argument('--ap-contract', type=Path, default=HERE.parent / 'ap/integration.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    make(args.output, args.module, args.ap_contract)
