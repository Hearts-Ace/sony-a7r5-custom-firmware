"""Bind the narrow 4.24 repair to actual native replays and frozen 4.23.

Offline only. Inherited CP/storage/color receipts remain explicitly historical;
only the fixed menu producer and relevant menu regressions are rerun on 4.24.
"""
from pathlib import Path
import hashlib, io, json, sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT/'vendor/audit-python'), str(ROOT/'tools')]
from elftools.elf.elffile import ELFFile
from build_corrected_fl2_fl3 import geometry

AP = 'a4c036eb4101820165748ca9819dd5afc803d11dc48f8b5eba3c9775f0c7995b'
OLD_AP = '4017b746b8720b0b3c0b1b8d79b00472548361b335048656b72c71be77202717'
CP = '8b38e753f34b1667d79b69079d911b9e6595f1ce1b873cb8e014437c6b4c494d'
MODULE = 'ea09b21bcbdd2466d9b8550c90e52e6555350548ffdcf57c521e6d85425e5941'
AUDIT = 'a62d36c5a94b50de5d7d7e669edc7a8b7d9c0fc2bdbb9c7a80558dc34ea9bff8'
OLD_MANIFEST = '39920b46459f79b08875bcf57e5b5d3367ca5fde1fb423307b982d044c007609'
OLD = ROOT/'analysis/r5_custom_filter423_20261023'
OLD_OUT = ROOT/'research/r5_custom_lut/build_r5_4.23_custom_filter_20261023'
REQUIRED = (
    'ap/ap_build.json', 'main_menu424_replay.json', 'cache_capacity424.json',
    'title/title_native_verification424.json',
    'menu_research/ap_1005_enter423_replay.json',
    'menu_research/native_1005_push_pop423_replay.json',
    'menu_research/menu_route423_verification.json',
    'menu_research/presenter_model423_replay.json',
    'menu_research/native_renderer423_replay.json',
)

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''): h.update(b)
    return h.hexdigest()

def read(p): return json.loads(p.read_text())
def row(p): return dict(path=str(p.relative_to(ROOT)), sha256=sha(p))

def main():
    target = HERE/'release_tests/final_gate.json'
    assert not target.exists(), 'Refuse replacing frozen acceptance'
    original = (OLD/'ap/appFw.so').read_bytes()
    actual = (HERE/'ap/appFw.so').read_bytes()
    assert hashlib.sha256(original).hexdigest() == OLD_AP
    assert hashlib.sha256(actual).hexdigest() == AP and len(actual) == len(original)
    build = read(HERE/'ap/ap_build.json')
    assert build['AP_sha256'] == AP and build['patch_only_from_423']
    assert build['reverse423_exact'] and build['native_readonly_e2fsck_passed']
    reverse = bytearray(actual)
    assert [(e['offset'], e['bytes']) for e in build['changes']] == [
        (97441472, 24), (29171744, 4), (97386864, 16)]
    for e in build['changes']:
        at, n = e['offset'], e['bytes']
        assert actual[at:at+n].hex() == e['after']
        assert original[at:at+n].hex() == e['before']
        reverse[at:at+n] = bytes.fromhex(e['before'])
    assert reverse == original, 'Undeclared change outside menu repair'
    for name in ('.rela.dyn', '.rela.plt', '.dynamic', '.dynsym', '.dynstr'):
        assert ELFFile(io.BytesIO(actual)).get_section_by_name(name).data() == ELFFile(io.BytesIO(original)).get_section_by_name(name).data()
    for name, expected in [('cp/cp423.NONINSTALLABLE.bin', CP),
                           ('import/runtime_rx.bin', MODULE), ('import/module_audit.json', AUDIT)]:
        assert sha(OLD/name) == expected
        if name.startswith('import/'): assert sha(HERE/name) == expected
    code = (OLD/'import/runtime_rx.bin').read_bytes()
    lo = read(OLD/'ap/ap_build.json')['rx_file']
    assert actual[lo+448:lo+len(code)] == code[448:]
    integrated, _, _, _ = geometry(HERE/'ap/nflasha15', 'appFw.so')
    assert integrated == actual

    manifest_path = OLD_OUT/'evidence/source_manifest.json'
    assert sha(manifest_path) == OLD_MANIFEST
    previous = read(manifest_path)
    for r in previous['rows']: assert sha(ROOT/r['path']) == r['sha256'], r['path']
    receipts = [HERE/n for n in REQUIRED]
    for p in receipts:
        q = read(p)
        assert q['passed'] is True, p
        assert q.get('AP_sha256', q.get('sha256')) == AP, p
        if 'CP_sha256' in q: assert q['CP_sha256'] == CP
    menu = read(HERE/'main_menu424_replay.json')
    assert menu['script_sha256'] == sha(HERE/'replay_main_menu424.py')
    labels = {r['label'] for r in menu['rows']}
    assert labels == {'source423', 'candidate424'}
    assert len(menu['rows']) == 6
    for label in labels:
        assert {r['bias'] for r in menu['rows'] if r['label'] == label} == {'0x0', '0x40000000', '0x7000000000'}
    for r in menu['rows']:
        candidate = r['label'] == 'candidate424'
        assert r['sha256'] == (AP if candidate else OLD_AP)
        assert r['old_alias_keys_checked'] == 1589 and r['private_key_absent_from_fixture']
        assert len(r['views']) == 4
        for v in r['views']:
            assert v['rows'] == [[0, 0x635 if candidate else 0xca4]]
            assert v['present'] == 1 and v['concrete_private_record'] == 0
            assert v['available'] == 1 and v['produced_mid_present'] == int(candidate)
            for t in v['titles']:
                if candidate:
                    assert int(t['resource'], 16) == 0x02ff4230
                    assert t['text_dispatch'] == [['name_char', '自定义滤镜']]
                else: assert int(t['resource'], 16) != 0x02ff4230
    capacity = read(HERE/'cache_capacity424.json')
    assert capacity['private_index_in_bounds'] is True
    title = read(HERE/'title/title_native_verification424.json')
    assert title['cases'] == 16
    route = read(HERE/'menu_research/menu_route423_verification.json')
    for name, digest in route['artifacts'].items():
        assert sha(HERE/'menu_research'/name) == digest
    assert route['selection']['enter_cases'] == 78
    assert route['selection']['direct_callback_cases'] == 108
    assert route['selection']['off_always_selectable']
    assert route['restoration']['cases'] == 6
    inputs = {HERE/'ap/appFw.so', HERE/'ap/nflasha15', HERE/'ap/e2fsck.log',
              OLD/'ap/appFw.so', OLD/'cp/cp423.NONINSTALLABLE.bin',
              OLD/'import/runtime_rx.bin', OLD/'import/module_audit.json',
              manifest_path, OLD_OUT/'evidence/final_gate.json'}
    inputs.update(p for p in HERE.rglob('*') if p.is_file() and p.suffix in ('.py', '.c', '.h', '.S') and 'reference' not in p.parts)
    result = dict(schema='r5-menu424-final-offline-gate/1', passed=True, version='4.24',
                  AP_sha256=AP, AP_partition_sha256=sha(HERE/'ap/nflasha15'), CP_sha256=CP,
                  patch_only_from_423=True, menu_visible_title_cached_gate_native_replayed=True,
                  menu_route_selection_back_preserved=True, custom_filter423_payload_preserved=True,
                  inherited423_manifest_sha256=OLD_MANIFEST,
                  inherited423_source_files_verified=len(previous['rows']),
                  inherited_CP_storage_color_tests_rerun=False,
                  required_receipts=[str((HERE/n).relative_to(ROOT)) for n in REQUIRED],
                  inputs=[row(p) for p in sorted(inputs)], receipts=[row(p) for p in receipts],
                  camera_io=False, device_acceptance_tested=False,
                  limits=['Native CPU replays use declared container/profile/allocator/UI fixtures. No physical LCD/font/boot or full Sony event-loop acceptance.',
                          'Unchanged CP, import, selection persistence, grid lifecycle and Gamma tail inherit exact frozen 4.23 evidence; their tests were not presented as rerun.'])
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(passed=True, AP_sha256=AP, inputs=len(inputs), receipts=len(receipts))))

if __name__ == '__main__': main()
