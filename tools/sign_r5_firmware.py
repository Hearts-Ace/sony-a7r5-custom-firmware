#!/usr/bin/env python3
"""Sign the verified R5 CN2 slot-fix DAT with its partition-1 companion key.

Offline only. Preserves every byte except the 256-byte FDAT signature and the
four-byte DEND CRC. Requires original Sony signature verification before build.
"""
if __name__ == '__main__':
    raise SystemExit('Historical reference/helper only; standalone execution is disabled. See PUBLICATION.md.')

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import zlib
from Cryptodome.Hash import SHA256
from Cryptodome.PublicKey import RSA
from Cryptodome.Signature import pkcs1_15

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = '817adac54324ca545081ba913e781c7450d94528616fae1f1dd594875f657edc'
PUBLIC_SHA256 = '4cb3cf8cc7a847a5b6108863c2defa327ceb06280c1dda468cd57c3dd3cae859'
SONY_PUBLIC_SHA256 = '8281413b5607446939613e07d020b2c7d8ee2371349099de56bc8288f7be0a43'
PARTITION1_SHA256 = '7d17697fb83a26bbcd53f49f7c791fea7cdd9e372ad6f4510d1f079e643a0b05'
CHUNK = 4 << 20


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(CHUNK), b''):
            h.update(b)
    return h.hexdigest()


def crc_prefix(path, size):
    crc = 0
    with path.open('rb') as f:
        left = size
        while left:
            b = f.read(min(CHUNK, left))
            require(bool(b), 'Truncated CRC input')
            crc = zlib.crc32(b, crc)
            left -= len(b)
    return crc & 0xffffffff


def inspect(path):
    total = path.stat().st_size
    entries = []
    with path.open('rb') as f:
        require(f.read(8) == b'\x89UFU\r\n\x1a\n', 'Wrong DAT magic')
        while f.tell() < total:
            start = f.tell()
            raw = f.read(8)
            require(len(raw) == 8, 'Truncated chunk header')
            size, kind = struct.unpack('>I4s', raw)
            off = f.tell()
            require(off + size <= total, 'Chunk extends beyond file')
            entries.append({'kind': kind.decode('ascii'), 'offset': off, 'size': size})
            f.seek(off + size)
            if kind == b'DEND':
                require(size == 4 and f.tell() == total, 'Wrong DEND geometry or trailing bytes')
                crc_end = start
                f.seek(off)
                crc_stored = struct.unpack('>I', f.read(4))[0]
                break
        else:
            raise ValueError('No DEND')
    require([x['kind'] for x in entries] == ['DATV', 'PROV', 'UDID', 'FDAT', 'DEND'],
            'Unexpected R5 container chunks')
    require(crc_prefix(path, crc_end) == crc_stored, 'Invalid outer CRC')
    fd = entries[3]
    require((fd['size'] - 272) % 1024 == 0, 'Invalid FDAT block length')
    return {'chunks': entries, 'size': total, 'signed_offset': fd['offset'],
            'signed_size': fd['size'] - 256,
            'signature_offset': fd['offset'] + fd['size'] - 256,
            'dend_crc_offset': entries[-1]['offset'], 'dend_crc': crc_stored}


def hashes_and_signature(path, layout):
    h, body, tampered = SHA256.new(), SHA256.new(), SHA256.new()
    with path.open('rb') as f:
        f.seek(layout['signed_offset'])
        left = layout['signed_size']
        body_left = left - 16
        first = True
        while left:
            b = f.read(min(CHUNK, left))
            require(bool(b), 'Truncated signed region')
            h.update(b)
            n = min(len(b), body_left)
            if n:
                body.update(b[:n])
                body_left -= n
            if first:
                tampered.update(bytes([b[0] ^ 1]) + b[1:])
                first = False
            else:
                tampered.update(b)
            left -= len(b)
        signature = f.read(256)
        require(len(signature) == 256, 'Wrong signature size')
    return h, body, tampered, signature


def verifies(key, h, signature):
    try:
        pkcs1_15.new(key).verify(h, signature)
        return True
    except (ValueError, TypeError):
        return False


def openssl_verify(public, digest, signature):
    cmd = ['/usr/bin/openssl', 'pkeyutl', '-verify', '-pubin', '-inkey', str(public),
           '-sigfile', str(signature), '-in', str(digest), '-pkeyopt', 'digest:sha256']
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(p.returncode == 0, 'Independent OpenSSL signature verification failed: ' +
            p.stderr.decode(errors='replace'))
    return p.stdout.decode(errors='replace').strip()


def exact_diff(source, output, layout):
    allowed = [(layout['signature_offset'], layout['signature_offset'] + 256),
               (layout['dend_crc_offset'], layout['dend_crc_offset'] + 4)]
    count = 0
    with source.open('rb') as a, output.open('rb') as b:
        offset = 0
        while True:
            old, new = a.read(CHUNK), b.read(CHUNK)
            require(len(old) == len(new), 'Output length changed')
            if not old:
                break
            if old != new:
                for i, (x, y) in enumerate(zip(old, new)):
                    if x != y:
                        pos = offset + i
                        require(any(start <= pos < end for start, end in allowed),
                                'Firmware body or metadata changed at byte ' + str(pos))
                        count += 1
            offset += len(old)
    return count, allowed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True,
                    help='New output directory; existing directories are rejected')
    args = ap.parse_args()
    out = args.output.resolve()
    require(not out.exists(), 'Output directory already exists')
    source = ROOT / 'build_fl2_fl3_20261014_cn2_slotfix/package/BODYDATA_R5_CN2_FL2_FL3_SLOTFIX_RESEARCH.DAT'
    donor = ROOT / 'BODYDATA.DAT'
    build = ROOT / 'build_r5_partition1_20261014'
    public = build / 'r5-update-verification-public.pem'
    private = build / 'keys/r5-update-signing-private.pem'
    sony_public = ROOT / 'analysis/r5_live_system_20261014/boot_probe_B/update_initrd/etc/VerificationKey.pem'
    companion = build / 'nflasha1.R5_4.00.custom-key.logical.img'
    require(digest_file(source) == SOURCE_SHA256, 'Wrong source firmware; refuse signing')
    require(digest_file(public) == PUBLIC_SHA256, 'Wrong new public key')
    require(digest_file(sony_public) == SONY_PUBLIC_SHA256, 'Wrong Sony public key')
    require(digest_file(companion) == PARTITION1_SHA256, 'Wrong companion partition-1 image')
    key = RSA.import_key(private.read_bytes())
    pub = RSA.import_key(public.read_bytes())
    sony = RSA.import_key(sony_public.read_bytes())
    require(key.has_private() and key.size_in_bits() == 2048 and key.e == 65537,
            'Expected the existing RSA-2048 private key')
    require((key.n, key.e) == (pub.n, pub.e), 'Private/public key mismatch')
    require((private.stat().st_mode & 0o777) == 0o600, 'Private key permission is not 0600')
    evidence = json.loads((ROOT / 'build_fl2_fl3_20261014_cn2_slotfix/evidence/independent_package_verification.json').read_text())
    require(evidence['package_sha256'] == SOURCE_SHA256 and evidence['exact_five_member_scope_verified'],
            'Source does not match previously verified slot-fix package')
    print('Source firmware, companion image and matching key verified.', flush=True)
    original_layout = inspect(donor)
    dh, dbody, dtampered, dsig = hashes_and_signature(donor, original_layout)
    require(verifies(sony, dh, dsig), 'Sony original signature failed; signing format unconfirmed')
    require(not verifies(sony, dbody, dsig), 'Unexpected signature coverage')
    require(not verifies(sony, dtampered, dsig), 'Original tamper check failed')
    print('Original Sony RSA/SHA256 signature verified over ciphertext + IV.', flush=True)
    layout = inspect(source)
    require(layout['chunks'] == original_layout['chunks'], 'Source chunk geometry changed')
    h, body, tampered, old_signature = hashes_and_signature(source, layout)
    require(old_signature == dsig, 'Source signature differs from archived original')
    require(not verifies(sony, h, old_signature), 'Modified source unexpectedly retains valid Sony signature')
    new_signature = pkcs1_15.new(key).sign(h)
    require(len(new_signature) == 256 and verifies(pub, h, new_signature), 'New signature self-verification failed')
    require(not verifies(pub, tampered, new_signature), 'New tamper check failed')
    out.mkdir(parents=True)
    pkg = out / 'BODYDATA_R5_CN2_FL2_FL3_SLOTFIX_CUSTOMKEY_RESEARCH.DAT'
    with source.open('rb') as f, pkg.open('xb') as dst:
        for b in iter(lambda: f.read(CHUNK), b''):
            dst.write(b)
        dst.seek(layout['signature_offset'])
        dst.write(new_signature)
        dst.flush()
        os.fsync(dst.fileno())
    new_crc = crc_prefix(pkg, layout['dend_crc_offset'] - 8)
    with pkg.open('r+b') as dst:
        dst.seek(layout['dend_crc_offset'])
        dst.write(struct.pack('>I', new_crc))
        dst.flush()
        os.fsync(dst.fileno())
    readback_layout = inspect(pkg)
    rh, rb, rt, rs = hashes_and_signature(pkg, readback_layout)
    require(rh.digest() == h.digest() and rb.digest() == body.digest(), 'Signed ciphertext or IV changed')
    require(rs == new_signature and verifies(pub, rh, rs), 'Saved file signature invalid')
    require(not verifies(sony, rh, rs) and not verifies(pub, rt, rs), 'Negative signature checks failed')
    changed, ranges = exact_diff(source, pkg, layout)
    (out / 'VerificationKey.pem').write_bytes(public.read_bytes())
    (out / 'FDAT.signature.bin').write_bytes(rs)
    (out / 'FDAT.signed.sha256.bin').write_bytes(rh.digest())
    (out / 'Sony.original.signature.bin').write_bytes(dsig)
    (out / 'Sony.original.signed.sha256.bin').write_bytes(dh.digest())
    openssl_new = openssl_verify(out / 'VerificationKey.pem', out / 'FDAT.signed.sha256.bin', out / 'FDAT.signature.bin')
    openssl_original = openssl_verify(sony_public, out / 'Sony.original.signed.sha256.bin', out / 'Sony.original.signature.bin')
    report = {
        'model': 'Sony ILCE-7RM5 / A7R V', 'firmware_version': '4.00', 'region': 'CN2',
        'source': str(source), 'source_sha256': SOURCE_SHA256,
        'source_validation': str(ROOT / 'build_fl2_fl3_20261014_cn2_slotfix/evidence/independent_package_verification.json'),
        'donor': str(donor), 'donor_sha256': digest_file(donor),
        'output': str(pkg), 'output_size': pkg.stat().st_size, 'output_sha256': digest_file(pkg),
        'algorithm': 'RSASSA-PKCS1-v1_5 with SHA-256', 'rsa_bits': 2048,
        'new_public_key_sha256': PUBLIC_SHA256, 'sony_public_key_sha256': SONY_PUBLIC_SHA256,
        'companion_partition1_image': str(companion), 'companion_partition1_sha256': PARTITION1_SHA256,
        'signature_coverage': 'FDAT payload ciphertext followed by its 16-byte IV; excludes the 256-byte signature',
        'signed_region': [layout['signed_offset'], layout['signature_offset']],
        'signed_region_sha256': rh.hexdigest(), 'ciphertext_sha256': rb.hexdigest(),
        'original_signed_region_sha256': dh.hexdigest(),
        'changed_bytes': changed, 'allowed_change_ranges_exclusive': ranges,
        'original_dend_crc32': hex(layout['dend_crc']), 'new_dend_crc32': hex(new_crc),
        'checks': {'sony_original_signature_verified': True, 'sony_original_tamper_rejected': True,
                   'source_original_signature_invalid_as_expected': True,
                   'saved_custom_signature_verified': True, 'saved_signature_verified_with_openssl': True,
                   'original_signature_verified_with_openssl': True, 'new_signature_rejected_with_sony_key': True,
                   'saved_tamper_rejected': True, 'full_source_output_comparison_passed': True,
                   'only_signature_and_outer_crc_changed': True, 'ciphertext_and_iv_unchanged': True,
                   'outer_crc_verified_from_saved_file': True, 'private_key_matches_companion_public_key': True},
        'openssl_verification': {'original': openssl_original, 'custom': openssl_new},
        'camera_io_performed': False, 'camera_new_public_key_flashing_performed': False,
        'device_acceptance_tested': False,
        'limitations': ['Camera still uses original Sony key until the companion partition-1 image is installed.',
                        'No actual update, boot, image capture, version/rollback or recovery write has been tested.']}
    (out / 'signature-verification.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    sums = []
    for path in sorted(out.iterdir()):
        sums.append(digest_file(path) + '  ' + path.name + '\n')
    (out / 'SHA256SUMS').write_text(''.join(sums))
    print(json.dumps({'output': str(pkg), 'size': report['output_size'], 'sha256': report['output_sha256'],
                      'changed_bytes': changed, 'openssl': openssl_new}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
