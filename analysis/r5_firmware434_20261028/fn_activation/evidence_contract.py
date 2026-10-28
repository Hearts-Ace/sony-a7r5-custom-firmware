"""Shared final-AP evidence checks; no instruction emulation or camera IO."""
from pathlib import Path
import hashlib
import json
import struct

HERE = Path(__file__).resolve().parent
CAND = HERE.parent
ROOT = CAND.parents[1]
ICON_EVIDENCE = ROOT / 'analysis/r5_icon434_evidence_20261028'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _elf_read(path, va, size):
    raw = Path(path).read_bytes()
    phoff = struct.unpack_from('<Q', raw, 32)[0]
    phent, phnum = struct.unpack_from('<HH', raw, 54)
    for i in range(phnum):
        p = struct.unpack_from('<IIQQQQQQ', raw, phoff + i * phent)
        if p[0] == 1 and p[3] <= va and va + size <= p[3] + p[5]:
            offset = p[2] + va - p[3]
            return raw[offset:offset + size]
    raise AssertionError((str(path), hex(va), size))


def resource_bindings(act):
    """Validate stock oracle, actual image records and the 4.34 native helpers."""
    oracle_path = ICON_EVIDENCE / 'stock_icons.json'
    resource_path = ICON_EVIDENCE / 'image_resources.json'
    oracle = json.loads(oracle_path.read_text())
    resources = json.loads(resource_path.read_text())
    frozen_path = ICON_EVIDENCE / 'frozen_manifest.json'
    frozen = json.loads(frozen_path.read_text())
    independent_path = ICON_EVIDENCE / 'verification.json'
    independent = json.loads(independent_path.read_text())
    baseline = ROOT / 'analysis/r5_firmware433_20261028/ap/appFw.so'
    assert resources['passed'] and oracle['passed']
    assert resources['oracle_sha256'] == sha(oracle_path)
    assert resources['AP_sha256'] == oracle['AP_sha256'] == sha(baseline)
    assert frozen['passed'] and independent['passed']
    assert frozen['AP_sha256'] == independent['AP_sha256'] == oracle['AP_sha256']
    assert (independent['native_selector_cases'], independent['native_resource_cases'],
            independent['independent_record_payload_rechecks']) == (24, 48, 48)
    assert independent['original_image_files'] == 6 and independent['help_string_negative']
    assert resources['script_sha256'] == sha(ICON_EVIDENCE / 'verify_image_resources.py')
    assert oracle['script_sha256'] == sha(ICON_EVIDENCE / 'replay_stock_icons.py')
    assert oracle['current_look_pointer'] == '0x7f207e8'
    assert oracle['look_getter'] == '0x28ae4b0' and oracle['selector'] == '0x1bd642c'
    assert resources['libObj_sha256'] == sha(ROOT / resources['libObj_path'])
    assert resources['resource_cases'] == len(resources['cases']) == 48
    assert resources['bad_resource_image_lookup_rejected']
    assert resources['bad_resource_is_help_string']
    assert resources['native_bank_selector'] == '0x123840'
    assert resources['native_record_reader'] == '0x122930→0x122870'
    assert resources['native_resource_type'] == '0x118858'
    actual = {(row['bias'], icon['look_value']): icon['original_icon']
              for row in act['rows'] for icon in row['dynamic_icons']}
    assert len(actual) == 24
    assert {(r['bias'], r['value']): r['icon'] for r in oracle['cases']} == actual
    names = {r['value']: r for r in resources['look_mapping']}
    assert len(names) == 12 and names[0]['short_name'] == 'ST'
    assert {r['short_name'] for r in names.values()} >= {'ST', 'PT', 'FL', 'FL2', 'FL3'}
    assert {(r['bias'], r['orientation'], r['look_value']) for r in resources['cases']} == {
        (bias, orientation, value) for bias in ('0x0', '0x40000000')
        for orientation in ('23', '32') for value in names}
    paths = [oracle_path, resource_path, frozen_path, independent_path, ICON_EVIDENCE / 'replay_stock_icons.py',
             ICON_EVIDENCE / 'verify_image_resources.py', baseline,
             ROOT / resources['libObj_path'], ROOT / resources['lz77_reference']['path']]
    for row in frozen['artifacts'] + frozen['sources']:
        path = ROOT / row['path']
        assert not Path(row['path']).is_absolute() and '..' not in Path(row['path']).parts
        assert sha(path) == row['sha256'], row['path']
        paths.append(path)
    assert sha(ROOT / resources['lz77_reference']['path']) == resources['lz77_reference']['sha256']
    for row in resources['cases']:
        assert row['resource'] == actual[row['bias'], row['look_value']]
        assert row['look_name'] == names[row['look_value']]['short_name']
        assert row['native_record_type'] == 6 and (row['width'], row['height']) == (70, 35)
        assert row['decoded_bytes'] == 5600
        path = ROOT / row['file']
        assert sha(path) == row['file_sha256']
        paths.append(path)
    for row in resources['look_mapping']:
        path = ROOT / row['source']['file']
        assert sha(path) == row['source']['sha256']
        paths.append(path)
    for row in resources['bad_resource_is_help_string']:
        path = ROOT / row['file']
        assert sha(path) == row['file_sha256']
        paths.append(path)
    helpers = []
    for va, size in ((0x1bd642c, 0x4c), (0x1bd63b8, 0x74),
                     (0x1bd62ac, 0x4c), (0x1bd6384, 0x30),
                     (0x1bc50ec, 0x180), (0x28ae4b0, 0x14)):
        before = _elf_read(baseline, va, size)
        after = _elf_read(CAND / 'ap/appFw.so', va, size)
        assert before == after, hex(va)
        helpers.append(dict(address=hex(va), bytes=size, sha256=hashlib.sha256(after).hexdigest()))
    paths = sorted(set(paths))
    return dict(native_image_resource_cases=48, original_look_states=12,
                native_stock_helpers_unchanged=helpers,
                ordinary_main_menu_small_logo_in_scope=False,
                bindings=[dict(path=str(p.relative_to(ROOT)), sha256=sha(p)) for p in paths])


def projection(row, expected=None):
    assert row['title_text'] == '自定义滤镜'
    assert row['stock_mid'] == '0x1e6' and row['private_mid'] == '0x635'
    assert row['matches_original_current_look']
    assert row['stock_resource'] == row['tile_resource'] == row['sprite_resource']
    assert row['stock_resource'] not in ('0x21c6410', '0xffffffff', '0x2002290')
    if expected is not None:
        assert row['stock_resource'] == expected
    assert row['tile_type'] == 6 and row['sprite_resource_enabled']
    assert row['full_tile_refresh'] == '0x21706d0' and row['tiles_checked'] == 12
    assert row['alternating_private_and_original']
    assert row['tile_renderer'] == '0x183c85c' and row['native_sprite_writer'] == '0x183c138'


def verify_activation(ap, act, stack):
    build = json.loads((CAND / 'ap/ap_build.json').read_text())
    assert ap == build['AP_sha256']
    assert ap == hashlib.sha256((CAND / 'ap/appFw.so').read_bytes()).hexdigest()
    for report in (act, stack):
        assert report['passed'] and report['AP_sha256'] == ap
    assert (act['native_activation_cases'], act['native_dynamic_icon_cases'],
            act['native_help_projection_cases'], act['native_private_return_cases']) == (48, 24, 4, 2)
    assert {(r['bias'], c['kind'], c['slot']) for r in act['rows'] for c in r['activations']} == {
        (bias, kind, slot) for bias in ('0x0', '0x40000000')
        for kind in ('still', 'movie') for slot in range(12)}
    state_sets = []
    for row in act['rows']:
        for case in row['activations']:
            assert case['queue_record'] == [0xc2, 0xd9, 0xc2, 0, 1, 0]
            assert case['reader_mid'] == case['selected_pid_3b2'] == '0x635'
            assert case['row_pid_3b7'] == '0x1607'
        help_text = row['help_text']
        assert help_text['help_getter'] == '0x1bd5630'
        assert help_text['help_producers'] == ['0x20d34f8', '0x20d1e54']
        assert help_text['private_help_resource'] == '0x21c6410'
        assert help_text['static_image_sentinel'] == '0xffffffff'
        assert help_text['title'] == '自定义滤镜'
        assert row['private_return']['close_request'] == '0xd9'
        assert len(row['dynamic_icons']) == 12
        assert len({r['look_value'] for r in row['dynamic_icons']}) == 12
        assert len({r['projection']['presenter'] for r in row['dynamic_icons']}) == 1
        states = {}
        for icon in row['dynamic_icons']:
            assert icon['original_icon'] == icon['private_icon'] == icon['common_preview_icon']
            assert icon['original_type'] == icon['private_type'] == 6
            assert icon['common_preview_helper'] == '0x1bc42c8'
            projection(icon['projection'], icon['original_icon'])
            states[icon['look_value']] = icon['original_icon']
        state_sets.append(states)
        for p in row['fn_projection']:
            projection(p, states[p['look_value']])
    assert state_sets[0] == state_sets[1]
    assert stack['cases'] == len(stack['rows']) == 6
    for case in stack['rows']:
        assert case['push_count'] == case['pop_count'] == 1
        assert case['main_screen'] == case['restored_screen'] == '0xc2'
        assert case['fn_presenter_reconstructed'] and case['lower_stack_unchanged'] and case['callee_saved']
        p = case['restored_presenter_native_projection']
        projection(p, state_sets[0][p['look_value']])
    return dict(native_activation_cases=48, dynamic_look_cases=24,
                same_presenter_full_tile_refreshes=24, dynamic_tile_parameters_checked=288,
                native_stack_restore_cases=6, help_text_excluded_from_image_oracle=True)
