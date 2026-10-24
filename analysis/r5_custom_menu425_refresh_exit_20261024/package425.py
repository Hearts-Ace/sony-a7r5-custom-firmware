"""Offline 4.25 synchronized-menu package. No historical or device writes.

The new AP is built from its pinned native baseline and newly replayed menu /
transaction sources. CP is inherited by exact identity only. Both stages are
explicit; final_gate.json must bind the actual candidate and required receipts.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, shutil, struct, sys, tarfile, types

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OLD = ROOT/'analysis/r5_custom_filter423_20261023'
OLD_OUT = ROOT/'research/r5_custom_lut/build_r5_4.23_custom_filter_20261023'
OUT = ROOT/'research/r5_custom_lut/build_r5_4.25_sync_exit_20261024'
BASE = ROOT/'build_r5_m4strict_4.04_20261015'
AP423 = '4017b746b8720b0b3c0b1b8d79b00472548361b335048656b72c71be77202717'
CP423 = '8b38e753f34b1667d79b69079d911b9e6595f1ce1b873cb8e014437c6b4c494d'
OLD_MANIFEST = '39920b46459f79b08875bcf57e5b5d3367ca5fde1fb423307b982d044c007609'
PACK_SOURCE = ROOT/'research/r5_custom_lut/build_r5_4.16_bcd_fixed_20261021/source/pack_bcd.py'
sys.path[:0] = [str(ROOT/'vendor/audit-python'), str(ROOT/'vendor/fwtool.py-a7iv'), str(ROOT/'tools')]
from build_corrected_fl2_fl3 import geometry, digest_file, digest_stream
from rebuild_tar import update_sum
REQUIRED_RECEIPTS = ('main_menu425_replay.json', 'title_native_verification425.json', 'menu_research/page425_replay.json', 'sync_tests/worker425_verified.json', 'sync_tests/exact_request_bias0.json', 'sync_tests/exact_request_bias40000000.json', 'sync_tests/refresh_wrapper425_verified.json', 'sync_tests/thread_ownership425_verified.json', 'sync_tests/sd425_final_binding.json', 'crosscore/ap_cp425.json', 'inherited425.json')
REQUIRED_CHECKS = ('menu_visibility_fix_preserved', 'menu_layout_transparent',
                   'manual_SD_reload', 'manual_SD_reload_waits_before_close', 'selection_waits_for_apply',
                   'parent_selection_before_close', 'grid_lifecycle_422_preserved')

# Importing the historical module defines helpers only. Never call its stages,
# mutate its OUT, or execute its CLI. All writes below target the new OUT/HERE.
spec = importlib.util.spec_from_file_location('r5_frozen_package423_helpers', OLD/'package423.py')
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
Overlay = legacy.Overlay

def read(path):
    return json.loads(path.read_text())

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')

def bound(row):
    relative = Path(row['path'])
    assert not relative.is_absolute() and '..' not in relative.parts, row['path']
    path = ROOT/relative
    assert path.is_file() and digest_file(path) == row['sha256'], row['path']
    return path

def inherited():
    """Read exact existing receipts; do not rerun historical build pipelines."""
    manifest_path = OLD_OUT/'evidence/source_manifest.json'
    assert digest_file(manifest_path) == OLD_MANIFEST
    manifest = read(manifest_path)
    assert manifest['schema'] == 'r5-423-source-manifest/1'
    v = read(OLD_OUT/'verification.json')
    assert v['version'] == '4.23' and v['source_manifest_sha256'] == OLD_MANIFEST
    assert v['output_sha256'] == 'ce2e3053fa3c4b7a5ad335b266fa10e915b50a4865e10a397e4933fc773409bb'
    assert v['components']['appFw.so']['sha256'] == AP423
    assert v['components']['cpapp-b.bin']['sha256'] == CP423
    assert digest_file(OLD/'ap/appFw.so') == AP423
    assert digest_file(OLD/'cp/cp423.NONINSTALLABLE.bin') == CP423
    assert (OLD/'release_tests/final_gate.json').read_bytes() == (OLD_OUT/'evidence/final_gate.json').read_bytes()
    return manifest, v

def gates(require_partition=True):
    gate = read(HERE/'release_tests/final_gate.json')
    assert gate['passed'] is True and gate['version'] == '4.25'
    assert gate.get('device_acceptance_tested', False) is False
    for key in REQUIRED_CHECKS:
        assert gate['required_checks'][key] is True, key
    assert gate['CP_sha256'] == CP423
    assert gate['AP_sha256'] != AP423
    assert digest_file(HERE/'ap/appFw.so') == gate['AP_sha256']
    assert digest_file(HERE/'ap/nflasha15') == gate['AP_partition_sha256']
    required = {str((HERE/name).relative_to(ROOT)) for name in REQUIRED_RECEIPTS}
    assert set(gate['required_receipts']) == required
    assert len(required) == len(gate['required_receipts'])
    assert {row['path'] for row in gate['receipts']} == required
    assert len(gate['receipts']) == len(required)
    assert gate['inputs'], 'Candidate input binding is required'
    for row in gate['inputs']:
        bound(row)
    for row in gate['receipts']:
        p = bound(row)
        assert p.is_relative_to(HERE), '425 receipt must be local to new analysis'
        q = read(p)
        assert q['passed'] is True, row['path']
        assert q.get('AP_sha256', q.get('sha256')) == gate['AP_sha256'], row['path']
        for key in ('AP_sha256', 'candidate_sha256'):
            if key in q:
                assert q[key] == gate['AP_sha256'], (row['path'], key)
        if 'CP_sha256' in q:
            assert q['CP_sha256'] == CP423, row['path']
    sd = read(HERE/'sync_tests/sd425_final_binding.json')
    assert sd['AP_sha256'] == gate['AP_sha256']
    assert sd['execution_inherited_by_exact_implementation_identity'] is True
    assert sd['final_AP_executed_by_this_SD_replay'] is False
    assert sd['all_importer_module_sections_exact'] is True
    actual = bound(dict(path=sd['receipt'], sha256=sd['receipt_sha256']))
    executed = read(actual)
    assert executed['passed'] and executed['cases'] == 162
    assert executed['AP_sha256'] == sd['actual_execution_AP_sha256']
    assert executed['manual_reload_production_wrapper_executed'] is True
    bound(dict(path=sd['reference_AP'], sha256=sd['reference_AP_sha256']))
    build = read(HERE/'ap/ap_build.json')
    assert build['passed'] is True
    assert build['AP_sha256'] == gate['AP_sha256']
    assert build['partition_sha256'] == gate['AP_partition_sha256']
    assert build['native_readonly_e2fsck_passed'] is True
    integrated, _, _, _ = geometry(HERE/'ap/nflasha15', 'appFw.so')
    assert hashlib.sha256(integrated).hexdigest() == gate['AP_sha256']
    del integrated
    if require_partition:
        p = OUT/'patched/nflasha8'
        receipt = read(OUT/'evidence/cp_partition.json')
        assert receipt['passed'] is True and receipt['CP_sha256'] == CP423
        assert receipt['partition_sha256'] == digest_file(p)
        assert receipt['original_partition_sha256'] == digest_file(BASE/'patched/nflasha8')
        assert receipt['full_component_readback'] and receipt['all_other_bytes_unchanged']
        integrated, _, _, _ = geometry(p, 'cpapp-b.bin')
        assert hashlib.sha256(integrated).hexdigest() == CP423
    v = read(BASE/'verification.json')
    assert v['version'] == '4.04'
    assert v['source_commit'] == '086df3b1e33dfa0206553ac2bb003535c58ddb80'
    assert digest_file(BASE/'patched/firmware.tar') == v['archive_sha256']
    components = {name: dict(row, path=str((BASE/'patched'/name).relative_to(ROOT)))
                  for name, row in v['components'].items()}
    components['appFw.so'] = dict(path=str((HERE/'ap/appFw.so').relative_to(ROOT)), sha256=gate['AP_sha256'])
    components['cpapp-b.bin'] = dict(path=str((OLD/'cp/cp423.NONINSTALLABLE.bin').relative_to(ROOT)), sha256=CP423)
    for row in components.values():
        bound(row)
    return dict(passed=True, camera_io=False, upstream_commit=v['source_commit'], components=components,
                AP_sha256=gate['AP_sha256'], CP_sha256=CP423,
                original_header=legacy.original_header_identity())

def cp_partition():
    assert not (OUT/'BODYDATA.DAT').exists(), 'Refuse changing an already packaged release'
    inherited()
    gates(require_partition=False)
    old_receipt = read(OLD_OUT/'evidence/cp_partition.json')
    assert old_receipt['passed'] is True and old_receipt['CP_sha256'] == CP423
    source = OLD_OUT/'patched/nflasha8'
    assert digest_file(source) == old_receipt['partition_sha256']
    assert digest_file(BASE/'patched/nflasha8') == old_receipt['original_partition_sha256']
    assert old_receipt['all_other_bytes_unchanged'] and old_receipt['full_component_readback']
    before, offsets, unit, meta = geometry(BASE/'patched/nflasha8', 'cpapp-b.bin')
    after, offsets2, unit2, meta2 = geometry(source, 'cpapp-b.bin')
    assert (offsets, unit, meta) == (offsets2, unit2, meta2)
    assert hashlib.sha256(before).hexdigest() == '8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32'
    assert after == (OLD/'cp/cp423.NONINSTALLABLE.bin').read_bytes()
    spans = sorted((at, at+min(unit, len(after)-i*unit)) for i, at in enumerate(offsets))
    with (BASE/'patched/nflasha8').open('rb') as x, source.open('rb') as y:
        pos = 0
        for a, b in spans:
            assert x.read(a-pos) == y.read(a-pos)
            x.seek(b); y.seek(b); pos = b
        assert x.read() == y.read()
    (OUT/'patched').mkdir(parents=True, exist_ok=True)
    dest = OUT/'patched/nflasha8'
    if dest.exists():
        assert digest_file(dest) == old_receipt['partition_sha256']
    else:
        shutil.copyfile(source, dest)
        with dest.open('rb') as f:
            os.fsync(f.fileno())
    assert digest_file(dest) == old_receipt['partition_sha256']
    save(OUT/'evidence/cp_partition.json', dict(
        passed=True, CP_sha256=CP423, partition_sha256=digest_file(dest),
        original_partition_sha256=old_receipt['original_partition_sha256'],
        reused_frozen423_partition=str(source.relative_to(ROOT)),
        inherited_receipt_sha256=digest_file(OLD_OUT/'evidence/cp_partition.json'),
        all_other_bytes_unchanged=True, full_component_readback=True, camera_io=False))

def archive():
    source = BASE/'patched/firmware.tar'
    replacements = {'0700_part_image/dev/nflasha8': OUT/'patched/nflasha8',
                    '0700_part_image/dev/nflasha15': HERE/'ap/nflasha15'}
    with tarfile.open(source, 'r:') as t:
        members = t.getmembers(); by = {m.name: m for m in members}
        assert len(by) == len(members)
        name = '0701_part_image_sum/part_image.sum'
        mapping = {n.removeprefix('0700_part_image/'): p for n, p in replacements.items()}
        text, changes = update_sum(t.extractfile(name).read().decode('ascii'), mapping,
                                   {n: p.stat().st_size for n, p in mapping.items()})
        assert len(changes) == 2
        p = OUT/'patched/part_image.sum'; p.write_text(text); replacements[name] = p
    rows = []
    for n, p in sorted(replacements.items(), key=lambda item: by[item[0]].offset_data):
        m = by[n]; assert p.stat().st_size == m.size
        rows.append((m.offset_data, m.offset_data+m.size, p))
    overlay = Overlay(source, rows)
    with overlay.open('rb') as f:
        h = digest_stream(f)
    with source.open('rb') as a, overlay.open('rb') as b:
        pos = 0
        for lo, hi, path in rows:
            left = lo-pos
            while left:
                n = min(4 << 20, left); assert a.read(n) == b.read(n); left -= n
            with path.open('rb') as p:
                left = hi-lo
                while left:
                    n = min(4 << 20, left); assert b.read(n) == p.read(n); left -= n
            a.seek(hi); pos = hi
        while True:
            x = a.read(4 << 20); y = b.read(len(x)); assert x == y
            if not x: break
    facts = []
    with tarfile.open(source, 'r:') as a, overlay.open('rb') as f, tarfile.open(fileobj=f, mode='r:') as b:
        assert [m.get_info() for m in a.getmembers()] == [m.get_info() for m in b.getmembers()]
        for m in members:
            if not m.isfile(): continue
            before, after = digest_stream(a.extractfile(m)), digest_stream(b.extractfile(m))
            assert after == (digest_file(replacements[m.name]) if m.name in replacements else before)
            assert (before != after) == (m.name in replacements)
            facts.append(dict(name=m.name, sha256=after, baseline_sha256=before, changed=before != after))
    save(OUT/'evidence/archive_verification_425.json', dict(
        passed=True, source_sha256=digest_file(source), output_sha256=h, bytes=source.stat().st_size,
        changed_members=list(replacements), members=facts, crc_updates=changes, virtual_archive=True,
        all_other_bytes_headers_padding_trailer_unchanged=True,
        overlay_source=str(source.relative_to(ROOT)),
        overlay_ranges=[dict(start=lo, end=hi, path=str(p.relative_to(ROOT)), sha256=digest_file(p))
                        for lo, hi, p in rows]))
    return overlay

def source_manifest():
    previous, _ = inherited()
    bindings = {row['path']: row['sha256'] for row in previous['rows']}
    paths = [p for p in HERE.rglob('*') if p.is_file() and p.suffix in ('.py', '.c', '.h', '.S')
             and '__pycache__' not in p.parts and 'reference' not in p.parts]
    paths += [PACK_SOURCE, OLD/'package423.py', OLD_OUT/'verification.json',
              OLD_OUT/'evidence/source_manifest.json', OLD_OUT/'evidence/cp_partition.json',
              OLD_OUT/'evidence/final_gate.json', HERE/'release_tests/final_gate.json',
              OUT/'patched/nflasha8', OUT/'evidence/cp_partition.json']
    gate = read(HERE/'release_tests/final_gate.json')
    for row in gate['inputs']+gate['receipts']:
        path = bound(row); paths.append(path)
    for p in sorted(set(paths)):
        name = str(p.relative_to(ROOT)); digest = digest_file(p)
        if name in bindings: assert bindings[name] == digest, name
        bindings[name] = digest
    rows = [dict(path=name, sha256=digest) for name, digest in sorted(bindings.items())]
    for row in rows: bound(row)
    q = dict(schema='r5-menu425-source-manifest/1', rows=rows,
             inherited423_manifest_sha256=OLD_MANIFEST, camera_io=False)
    save(OUT/'evidence/source_manifest.json', q)
    return q

def package():
    assert not (OUT/'BODYDATA.DAT').exists(), 'Refuse replacing a packaged release'
    gates(); manifest = source_manifest(); overlay = archive()
    pack = types.ModuleType('r5_menu425_frozen_bcd_package')
    pack.__file__ = str(ROOT/'tools/build_r5_m4strict403.py')
    exec(compile(PACK_SOURCE.read_text(), str(PACK_SOURCE), 'exec'), pack.__dict__)
    original_digest = pack.digest_file
    def digest(p):
        if p is overlay:
            with overlay.open('rb') as f: return digest_stream(f)
        return original_digest(p)
    pack.digest_file = digest
    pack.OUT = OUT; pack.TAR = overlay; pack.TAG = '425'; pack.VERSION = '4.25'; pack.components = gates
    pack.build_package()
    assert (OUT/'FDAT.header.4.25.bin').read_bytes()[32:34] == bytes.fromhex('2504')
    target = OUT/'BODYDATA.DAT'
    assert target.stat().st_size == 754525608 and not target.is_symlink()
    for row in manifest['rows']: bound(row)
    gates()
    q = read(OUT/'verification.json'); q.pop('exact_four_member_scope_verified', None)
    _, old = inherited()
    for key in ('config_version', 'config_schema', 'custom_filter_menu',
                'creative_look_and_custom_selection_independent', 'grid_mandatory',
                'grid_switch_present', 'legacy_BIN_accepted',
                'native_Gamma_tail_preserved_for_actual_Creative_Look', 'SD_import_policy',
                'SD_file', 'selection_file'):
        q[key] = old[key]
    gate = read(HERE/'release_tests/final_gate.json')
    q.update(firmware_release='4.25', base_firmware='strict4.04 native baseline',
             AP_rebuilt_from_pinned_native_baseline=True, CP_exactly_frozen423=True,
             menu_visibility_and_secondary_identity_fix=True,
             selection_saved_immediately=False,
             manual_SD_reload_supported=True,
             manual_SD_reload_waits_before_close=True,
             selection_close_policy='After CP selection acknowledgements, exact native E4 execution return, durable selection publication and parent-value postcondition; failure retains the menu.',
             synchronized_menu_checks=gate['required_checks'],
             inherited423_manifest_sha256=OLD_MANIFEST,
             source_manifest_sha256=digest_file(OUT/'evidence/source_manifest.json'),
             camera_io_performed=False, device_acceptance_tested=False, experimental_candidate=True,
             limitations=[
                 'Offline replay and package verification do not establish physical menu rendering, real event timing, cold boot or power-recovery behavior.',
                 'The preserved 4.22 CP grid lifecycle is inherited by exact component identity; device heap/cache and live-view/JPG color remain separate acceptance steps.',
                 'Native filesystem calls can exceed polling deadlines. Read-only SD import and atomic internal persistence are tested independently of camera media.',
             ] + gate.get('limitations', []))
    save(OUT/'verification.json', q)
    shutil.copyfile(HERE/'release_tests/final_gate.json', OUT/'evidence/final_gate.json')
    (OUT/'SHA256SUMS').write_text('\n'.join(digest_file(p)+'  '+str(p.relative_to(OUT))
        for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS')+'\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['images', 'package'], required=True)
    args = parser.parse_args()
    cp_partition() if args.stage == 'images' else package()
