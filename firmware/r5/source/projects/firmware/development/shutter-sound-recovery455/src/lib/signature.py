import hashlib, struct, subprocess, zlib
from Cryptodome.Hash import SHA256
from Cryptodome.PublicKey import RSA
from Cryptodome.Signature import pkcs1_15
CHUNK=4<<20

PUBLIC_SHA256 = '4cb3cf8cc7a847a5b6108863c2defa327ceb06280c1dda468cd57c3dd3cae859'

SONY_PUBLIC_SHA256 = '8281413b5607446939613e07d020b2c7d8ee2371349099de56bc8288f7be0a43'

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
