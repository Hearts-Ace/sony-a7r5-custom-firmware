"""Independent read-only 4.28 DAT verification; report is outside release OUT.

Rechecks the actual container/signature and independently decodes every FDAT
block against the frozen strict4.04 TAR plus the three declared replacements.
No private key, camera, removable medium, or historical output is written.
"""
from pathlib import Path
import hashlib, io, json, stat, struct, sys, tarfile, zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT/'research/r5_custom_lut/build_r5_4.28_rollback425_20261024'
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
REQUIRED_RECEIPTS = ('main_menu425_replay.json', 'title_native_verification425.json', 'menu_research/page425_replay.json', 'sync_tests/worker425_verified.json', 'sync_tests/exact_request_bias0.json', 'sync_tests/exact_request_bias40000000.json', 'sync_tests/refresh_wrapper425_verified.json', 'sync_tests/thread_ownership425_verified.json', 'sync_tests/sd425_final_binding.json', 'crosscore/ap_cp425.json', 'inherited425.json')
REQUIRED_RECEIPTS += ('rollback428_verified.json','sync_tests/sync_inheritance428_verified.json')

OLD_MANIFEST = '39920b46459f79b08875bcf57e5b5d3367ca5fde1fb423307b982d044c007609'

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
    assert digest == v['output_sha256'] and v['version'] == '4.28'
    assert v['inherited423_manifest_sha256'] == OLD_MANIFEST
    assert v['CP_exactly_frozen423'] and v['AP_rebuilt_from_pinned_native_baseline']
    assert v['selection_saved_immediately'] is False
    assert v['components']['cpapp-b.bin']['sha256'] == CP
    manifest_path = OUT/'evidence/source_manifest.json'
    assert sha(manifest_path) == v['source_manifest_sha256']
    manifest = read(manifest_path)
    assert manifest['schema'] == 'r5-menu428-source-manifest/1'
    for row in manifest['rows']:
        assert sha(safe(row['path'])) == row['sha256'], row['path']
    gate = read(HERE/'release_tests/final_gate.json')
    assert gate['passed'] and gate['version'] == '4.28' and gate['CP_sha256'] == CP
    assert (HERE/'release_tests/final_gate.json').read_bytes() == (OUT/'evidence/final_gate.json').read_bytes()
    assert gate['AP_sha256'] == v['components']['appFw.so']['sha256']
    required_checks = ('menu_visibility_fix_preserved', 'menu_layout_transparent',
                       'manual_menu_reload_removed', 'selection_waits_for_apply',
                       'parent_selection_before_close', 'grid_lifecycle_422_preserved')
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
    sd = read(HERE/'sync_tests/sd425_final_binding.json')
    assert sd['AP_sha256'] == gate['AP_sha256']
    assert sd['execution_inherited_by_exact_implementation_identity'] and not sd['final_AP_executed_by_this_SD_replay']
    assert sd['all_importer_module_sections_exact']
    assert sha(safe(sd['receipt'])) == sd['receipt_sha256']
    actual_sd = read(safe(sd['receipt']))
    assert actual_sd['passed'] and actual_sd['cases'] == 162
    assert actual_sd['AP_sha256'] == sd['actual_execution_AP_sha256']
    assert sha(safe(sd['reference_AP'])) == sd['reference_AP_sha256']
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
    header = (OUT/'FDAT.header.4.28.bin').read_bytes()
    assert len(header) == 512 and header[32:34] == bytes.fromhex('2804')
    with (ROOT/'unpacked/r5/firmware.fdat').open('rb') as f:
        old_header = f.read(512)
    assert all(i in (8, 9, 10, 11, 32) for i, (a, b) in enumerate(zip(old_header, header)) if a != b)
    h = FdatHeader.unpack(io.BytesIO(header)); fs = FdatFileSystemHeader.unpack(h.fileSystemHeaders, 0)
    updater = (ROOT/'unpacked/r5/updater.img').read_bytes()
    assert (h.versionMajor, h.versionMinor, h.model, h.region, h.modeType, h.luwFlag) == (4, 0x28, 0x11030080, 0, b'U', b'N')
    assert zlib.crc32(header[12:]) == h.checksum
    assert fs.offset == 512 and fs.size == len(updater) and h.firmwareOffset == 512+len(updater)
    assert hashlib.sha256(updater).hexdigest() == 'c4b18a82eea52a507fb82b86ad50bab6047070b8908d03c28edcce4a9577d348'
    ar = read(OUT/'evidence/archive_verification_428.json')
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
    report = dict(passed=True, version='4.28', output=str(target), output_bytes=s.st_size,
                  output_sha256=digest, ordinary_file=True, BCD='2804',
                  actual_outer_crc_and_signature_rechecked=True, tampered_signature_rejected=True,
                  AP_CP_independently_extracted=True, CP_exact_frozen423=True,
                  exact_strict404_overlay_members=sorted(names), plaintext_verification=plain,
                  sha256sum_entries=sums, frozen_source_inputs=len(manifest['rows']),
                  required_receipts_rechecked=len(required), synchronized_checks_rechecked=list(required_checks),
                  camera_io=False, device_acceptance_tested=False)
    result = HERE/'release_tests/delivery_verified.json'
    assert not result.exists(), 'Refuse replacing an independent final receipt'
    result.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps(report, ensure_ascii=False))

if __name__ == '__main__': main()
