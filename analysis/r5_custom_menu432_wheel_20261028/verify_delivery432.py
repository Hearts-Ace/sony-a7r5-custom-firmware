"""Independent read-only 4.32 DAT verification; report is outside release OUT.

Rechecks the actual container/signature and independently decodes every FDAT
block against the frozen strict4.04 TAR plus the three declared replacements.
No private key, camera, removable medium, or historical output is written.
"""
from pathlib import Path
import hashlib, io, json, stat, struct, sys, tarfile, zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT/'research/r5_custom_lut/build_r5_4.32_wheel_20261028'
BASE = ROOT/'build_r5_m4strict_4.04_20261015'
sys.path[:0] = [str(ROOT/'vendor/audit-python'), str(ROOT/'vendor/fwtool.py-a7iv'), str(ROOT/'tools')]
import numpy as np
from Cryptodome.Cipher import AES
from Cryptodome.PublicKey import RSA
from fwtool.sony import constants
from fwtool.sony.fdat import FdatHeader, FdatFileSystemHeader
from sign_r5_firmware import inspect, hashes_and_signature, verifies, PUBLIC_SHA256
from build_corrected_fl2_fl3 import geometry
from rebuild_tar import update_sum

CP = '8b38e753f34b1667d79b69079d911b9e6595f1ce1b873cb8e014437c6b4c494d'
REQUIRED_RECEIPTS = ('main_menu425_replay.json', 'title_native_verification425.json', 'menu_research/page425_replay.json', 'sync_tests/worker425_verified.json', 'sync_tests/exact_request_bias0.json', 'sync_tests/exact_request_bias40000000.json', 'sync_tests/refresh_wrapper425_verified.json', 'sync_tests/thread_ownership425_verified.json', 'sync_tests/sd430_replay.json', 'crosscore/ap_cp425.json', 'inherited425.json', 'menu_research/native_view426_verified.json', 'menu_research/main_open426_replay.json', 'menu_research/identity426_replay.json')
OLD_MANIFEST = '98d68092f4006b716f072ee95684ae57848e25f77b82d45a43a6539f1780648f'
REQUIRED_RECEIPTS += ('menu_research/native_lifecycle429_verified.json',
                      'menu_research/native_allocator429_verified.json',
                      'menu_research/review429_verified.json')

REQUIRED_RECEIPTS += ('menu_research/name_input429_verified.json', 'delta432_verified.json', 'sync_tests/grid430_verified.json', 'menu_research/interaction431_verified.json', 'parent_evidence/parent431_verified.json', 'style_evidence/native_list431_verified.json', 'menu_research/wheel432_verified.json')

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''): h.update(b)
    return h.hexdigest()

def read(p):
    return json.loads(p.read_text())

def safe(name):
    relative = Path(name)
    assert not relative.is_absolute() and '..' not in relative.parts, name
    return ROOT/relative

class Expected:
    def __init__(self, prefix, source, rows):
        self.prefix = io.BytesIO(prefix)
        self.source = source.open('rb')
        self.rows = rows
    def read(self, n):
        prefix = self.prefix.read(n)
        n -= len(prefix)
        if not n: return prefix
        start = self.source.tell()
        result = bytearray(self.source.read(n)); end = start+len(result)
        for lo, hi, path in self.rows:
            if lo < end and hi > start:
                a, b = max(start, lo), min(end, hi)
                with path.open('rb') as f:
                    f.seek(a-lo); replacement = f.read(b-a)
                assert len(replacement) == b-a
                result[a-start:b-start] = replacement
        return prefix+bytes(result)
    def close(self):
        self.source.close()

def verify_plain(target, layout, prefix, archive, rows):
    """Different decoder loop from package_bcd; validates actual saved blocks."""
    total = len(prefix)+archive.stat().st_size
    expected_blocks = (total+1019)//1020
    encrypted_bytes = layout['signed_size']-16
    assert encrypted_bytes == expected_blocks*1024
    with target.open('rb') as f:
        f.seek(layout['signature_offset']-16); iv = f.read(16)
    ecb = AES.new(constants.key_aes, AES.MODE_ECB)
    cbc = AES.new(constants.key_cxd90057_k8, AES.MODE_CBC, iv)
    expected = Expected(prefix, archive, rows)
    h = hashlib.sha256(); blocks = seen = 0
    with target.open('rb') as f:
        f.seek(layout['signed_offset'])
        left = encrypted_bytes
        while left:
            raw = f.read(min(4 << 20, left))
            assert raw and len(raw)%1024 == 0
            decoded = ecb.decrypt(raw[:512])+cbc.decrypt(raw[512:]) if not blocks else cbc.decrypt(raw)
            words = np.frombuffer(decoded, dtype='<u2').reshape(-1, 512)
            assert np.array_equal(words[:, 0], words[:, 1:].sum(axis=1, dtype=np.uint64)&65535)
            flags = words[:, 1]>>15
            last_batch = left == len(raw)
            assert not np.any(flags[:-1]) and int(flags[-1]) == int(last_batch)
            lengths = words[:, 1]&0x7fff
            assert np.all(lengths[:-1] == 1020)
            last_length = total-seen-(len(words)-1)*1020 if last_batch else 1020
            assert int(lengths[-1]) == last_length and 1 <= last_length <= 1020
            payload = np.frombuffer(decoded, dtype=np.uint8).reshape(-1, 1024)[:, 4:].tobytes()
            padding = 1020-last_length if last_batch else 0
            if padding:
                assert payload[-padding:] == b'\xff'*padding
                payload = payload[:-padding]
            assert expected.read(len(payload)) == payload, 'Saved FDAT differs from exact frozen inputs'
            h.update(payload); seen += len(payload); blocks += len(words); left -= len(raw)
    assert seen == total and blocks == expected_blocks and expected.read(1) == b''
    expected.close()
    return dict(passed=True, plaintext_bytes=seen, decrypted_blocks=blocks,
                plaintext_sha256=h.hexdigest(), every_plaintext_byte_matches=True,
                all_block_checksums_lengths_flags_and_padding_valid=True)

def main():
    target = OUT/'BODYDATA.DAT'; s = target.lstat(); v = read(OUT/'verification.json')
    assert stat.S_ISREG(s.st_mode) and not target.is_symlink() and s.st_size == 754525608
    digest = sha(target)
    assert digest == v['output_sha256'] and v['version'] == '4.32'
    assert v['inherited428_manifest_sha256'] == OLD_MANIFEST
    assert v['CP_exactly_frozen423'] and v['AP_rebuilt_from_pinned_native_baseline']
    assert v['selection_saved_immediately'] is False
    assert v['movement_applies_and_saves'] and v['selected_confirm_reapplies'] is False
    assert v['parent_refresh_error_distinct']
    assert v['wheel_updates_custom_focus_and_full_name'] and v['wheel_uses_custom_selection_request']
    assert v['wheel_native_look_setter_bypassed'] and v['wheel_repeated_events_supported']
    assert v['wheel_step_contract']=='One available-item step per native event, clamped at both ends; message payload step count and direction are not interpreted.'
    assert v['components']['cpapp-b.bin']['sha256'] == CP
    manifest_path = OUT/'evidence/source_manifest.json'
    assert sha(manifest_path) == v['source_manifest_sha256']
    manifest = read(manifest_path)
    assert manifest['schema'] == 'r5-menu432-source-manifest/1'
    for row in manifest['rows']:
        assert sha(safe(row['path'])) == row['sha256'], row['path']
    gate = read(HERE/'release_tests/final_gate.json')
    assert gate['passed'] and gate['version'] == '4.32' and gate['CP_sha256'] == CP
    assert (HERE/'release_tests/final_gate.json').read_bytes() == (OUT/'evidence/final_gate.json').read_bytes()
    assert gate['AP_sha256'] == v['components']['appFw.so']['sha256']
    required_checks = ('menu_visibility_fix_preserved', 'menu_layout_transparent',
                       'menu_update_operation_absent', 'selection_waits_for_apply',
                       'parent_selection_before_close', 'grid_lifecycle_422_preserved',
                       'update_widgets_absent', 'right_pane_name_only')
    required_checks += ('private_inputs_isolated', 'original_creative_look_preserved', 'full_and_short_names_verified')
    required_checks += ('native_presenter_vtable_ABI', 'full_native_controller_lifecycle',
                        'first_view_update_mode_zero', 'native_view_arena_checked')
    required_checks += ('startup_selection_yields', 'current_filter_diagnostic_only', 'same_boot_SD_bank_retry', 'unchanged_bank_deduplicated', 'independent_ready_card_slot', 'late_media_READY_revalidated', 'movement_applies_and_saves', 'native_list_highlight', 'apply_and_parent_errors_distinct', 'native_parent_rebuilt_after_pop', 'destroyed_parent_never_dereferenced', 'wheel_updates_focus_and_preview', 'wheel_uses_selection_request', 'wheel_avoids_original_look_setter', 'wheel_batched_steps_verified')
    assert v['synchronized_menu_checks'] == gate['required_checks']
    for check in required_checks: assert gate['required_checks'][check] is True, check
    required = {str((HERE/name).relative_to(ROOT)) for name in REQUIRED_RECEIPTS}
    assert set(gate['required_receipts']) == required
    assert len(required) == len(gate['required_receipts'])
    assert {r['path'] for r in gate['receipts']} == required
    assert len(gate['receipts']) == len(required) and gate['inputs']
    for row in gate['inputs'] + gate['receipts']:
        assert sha(safe(row['path'])) == row['sha256'], row['path']
    for row in gate['receipts']:
        receipt = read(safe(row['path']))
        assert receipt['passed'] is True
        assert receipt.get('AP_sha256', receipt.get('sha256')) == gate['AP_sha256']
        if 'CP_sha256' in receipt: assert receipt['CP_sha256'] == CP
    wheel=read(HERE/'menu_research/wheel432_verified.json')
    assert wheel['passed'] and wheel['version']=='4.32' and wheel['AP_sha256']==gate['AP_sha256']
    for field in ('wheel_updates_focus_and_preview','same_request_path','no_original_look_setter','batched_steps_verified'):
        assert wheel[field],field
    assert wheel['batch_contract']=='Repeated native wheel events each advance one available item, clamped at boundaries. No unverified message count is interpreted.'
    assert len(wheel['cases'])==26 and len(wheel['baseline431'])==8
    regular='bidirectional_burst_boundary_mixed_closing'
    current_rows=[row for row in wheel['cases'] if row['mode']==regular]
    assert len(current_rows)==16
    assert {(row['bias'],row['layout'],row['mask']) for row in current_rows}=={(bias,layout,hex(mask)) for bias in ('0x0','0x40000000') for layout in (0,1) for mask in (4095,258,0,2048)}
    for row in current_rows:
        available=[0]+[i for i in range(1,13)if int(row['mask'],16)&(1<<(i-1))]
        count=len(available)
        forward=[available[min(i+1,count-1)] for i in range(count+3)]
        backward=[available[max(count-2-i,0)] for i in range(count+3)]
        assert [state['selected'] for state in row['states']]==forward+backward
        for state in row['states']:
            assert state['native_list_focus']==available.index(state['selected'])
            assert int(state['full_name_resource'],16)==0x02ff4400+state['selected']
        assert row['private_requests']==(2*count if count>1 else 1)
        assert row['no_original_look_setter']
    remaining=[row for row in wheel['cases'] if row['mode']!=regular]
    assert len(remaining)==10
    assert {(row['bias'],row['mode']) for row in remaining}=={(bias,mode) for bias in ('0x0','0x40000000') for mode in ('pending','failure','stale_serial','wrong_mid','stock')}
    for row in remaining:
        assert row['selected']==(2 if row['mode']=='pending' else 0)
        assert row['no_original_look_setter'] is (row['mode']!='stock')
    assert {(row['bias'],row['event']) for row in wheel['baseline431']}=={(bias,hex(event)) for bias in ('0x0','0x40000000') for event in (0x2050000,0x2050001,0x2050004,0x2050005)}
    for row in wheel['baseline431']:
        assert row['private_projection_unchanged'] and '0x1a6d8cc' in row['native_escape']
    assert sha(ROOT/'analysis/r5_custom_menu431_interaction_20261027/ap/appFw.so')=='3c832336b73fc5d8b5a902faebd07249821888a17d3609831def42d4419ba941'
    sd = read(HERE/'sync_tests/sd430_replay.json')
    assert sd['passed'] and sd['AP_sha256'] == gate['AP_sha256'] and sd['cases'] == 180
    assert sd['manual_reload_production_wrapper_executed'] and sd['current_set_digest_boundary_checked']
    for image, component, wanted in ((HERE/'ap/nflasha15', 'appFw.so', gate['AP_sha256']),
                                   (OUT/'patched/nflasha8', 'cpapp-b.bin', CP)):
        raw, _, _, _ = geometry(image, component)
        assert hashlib.sha256(raw).hexdigest() == wanted
        del raw
    layout = inspect(target)  # Recalculates actual DEND outer CRC.
    public_path = OUT/'VerificationKey.pem'; assert sha(public_path) == PUBLIC_SHA256
    public = RSA.import_key(public_path.read_bytes())
    signed, _, tampered, signature = hashes_and_signature(target, layout)
    assert verifies(public, signed, signature) and not verifies(public, tampered, signature)
    assert signed.digest() == (OUT/'FDAT.signed.sha256.bin').read_bytes()
    assert signature == (OUT/'FDAT.signature.bin').read_bytes()
    donor = ROOT/'BODYDATA.DAT'; donor_layout = inspect(donor)
    with donor.open('rb') as a, target.open('rb') as b:
        for old, new in zip(donor_layout['chunks'][:3], layout['chunks'][:3]):
            assert old == new
            a.seek(old['offset']); b.seek(new['offset'])
            assert a.read(old['size']) == b.read(new['size'])
    header = (OUT/'FDAT.header.4.32.bin').read_bytes()
    assert len(header) == 512 and header[32:34] == bytes.fromhex('3204')
    with (ROOT/'unpacked/r5/firmware.fdat').open('rb') as f:
        old_header = f.read(512)
    assert all(i in (8, 9, 10, 11, 32) for i, (a, b) in enumerate(zip(old_header, header)) if a != b)
    h = FdatHeader.unpack(io.BytesIO(header)); fs = FdatFileSystemHeader.unpack(h.fileSystemHeaders, 0)
    updater = (ROOT/'unpacked/r5/updater.img').read_bytes()
    assert (h.versionMajor, h.versionMinor, h.model, h.region, h.modeType, h.luwFlag) == (4, 0x32, 0x11030080, 0, b'U', b'N')
    assert zlib.crc32(header[12:]) == h.checksum
    assert fs.offset == 512 and fs.size == len(updater) and h.firmwareOffset == 512+len(updater)
    assert hashlib.sha256(updater).hexdigest() == 'c4b18a82eea52a507fb82b86ad50bab6047070b8908d03c28edcce4a9577d348'
    ar = read(OUT/'evidence/archive_verification_432.json')
    archive = BASE/'patched/firmware.tar'
    assert ar['passed'] and safe(ar['overlay_source']) == archive and sha(archive) == ar['source_sha256']
    assert h.firmwareSize == archive.stat().st_size == ar['bytes']
    names = {'0700_part_image/dev/nflasha8': OUT/'patched/nflasha8',
             '0700_part_image/dev/nflasha15': HERE/'ap/nflasha15',
             '0701_part_image_sum/part_image.sum': OUT/'patched/part_image.sum'}
    assert set(ar['changed_members']) == set(names)
    with tarfile.open(archive, 'r:') as t:
        by = {m.name: m for m in t.getmembers()}
        rows = sorted((by[name].offset_data, by[name].offset_data+by[name].size, path) for name, path in names.items())
        for name, path in names.items(): assert by[name].size == path.stat().st_size
        mapping = {name.removeprefix('0700_part_image/'): path for name, path in names.items() if name.startswith('0700_part_image/')}
        text, changes = update_sum(t.extractfile('0701_part_image_sum/part_image.sum').read().decode('ascii'),
                                   mapping, {name: p.stat().st_size for name, p in mapping.items()})
        assert len(changes) == 2 and text.encode('ascii') == names['0701_part_image_sum/part_image.sum'].read_bytes()
    assert len(ar['overlay_ranges']) == len(rows)
    for recorded, (lo, hi, path) in zip(ar['overlay_ranges'], rows):
        assert (recorded['start'], recorded['end'], safe(recorded['path'])) == (lo, hi, path)
        assert sha(path) == recorded['sha256']
    plain = verify_plain(target, layout, header+updater, archive, rows)
    assert plain['plaintext_sha256'] == v['plaintext_verification']['plaintext_sha256']
    sums = 0; members = set()
    for line in (OUT/'SHA256SUMS').read_text().splitlines():
        expected, name = line.split('  ', 1); relative = Path(name)
        assert name not in members and not relative.is_absolute() and '..' not in relative.parts
        members.add(name); assert sha(OUT/relative) == expected, name; sums += 1
    assert members == {str(p.relative_to(OUT)) for p in OUT.rglob('*') if p.is_file() and p.name != 'SHA256SUMS'}
    report = dict(passed=True, version='4.32', verifier_source_sha256=sha(Path(__file__)), verifier=str(Path(__file__).relative_to(ROOT)), output=str(target), output_bytes=s.st_size,
                  output_sha256=digest, ordinary_file=True, BCD='3204',
                  actual_outer_crc_and_signature_rechecked=True, tampered_signature_rejected=True,
                  AP_CP_independently_extracted=True, CP_exact_frozen423=True,
                  exact_strict404_overlay_members=sorted(names), plaintext_verification=plain,
                  sha256sum_entries=sums, frozen_source_inputs=len(manifest['rows']),
                  required_receipts_rechecked=len(required), synchronized_checks_rechecked=list(required_checks),
                  wheel_state_cases_rechecked=26, wheel_baseline431_witnesses_rechecked=8,
                  wheel_events_checked_as_individual_single_steps=True,
                  camera_io=False, device_acceptance_tested=False)
    result = HERE/'release_tests/delivery_verified.json'
    assert not result.exists(), 'Refuse replacing an independent final receipt'
    result.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps(report, ensure_ascii=False))

if __name__ == '__main__': main()
