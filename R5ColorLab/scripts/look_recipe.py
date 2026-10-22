"""Bounded development recipe codec. NOT a Sony LUT or installable payload.

The only native-shaped section is six Q10 block13 matrix coefficients. The
curve has an explicit PROVISIONAL axis, not a reverse-engineered CP Gamma
record. CC1 and all B/A1/A2 dispatch are deliberately absent. No device IO.
"""
import hashlib
import json
import math
from pathlib import Path
import struct
import zlib

MAGIC = b'R5LKDEV1'
HEADER = struct.Struct('<8sHHIII8s')
MAX_BYTES = 65536
DEV_ONLY = 1
POINTS = 129
TAGS = (b'META', b'B13Q', b'AXIS', b'CURV')


def _validate(metadata, q, axis, curve):
    if (not isinstance(metadata, dict)
            or metadata.get('schema') != 'r5-look-proxy/1'
            or metadata.get('camera_apply_allowed') is not False
            or metadata.get('cc1_policy') != 'preserve-not-fitted'
            or metadata.get('curve_encoding') != 'explicit-float-axis-NOT-CP-gamma'
            or metadata.get('model') != 'neutral-matrix-then-shared-curve-hypothesis'):
        raise ValueError('Unsupported or non-development recipe metadata')
    if len(q) != 6 or any(type(v) is not int or not -4096 <= v <= 4096 for v in q):
        raise ValueError('Expected six bounded signed Q10 matrix coefficients')
    if len(axis) != POINTS or len(curve) != POINTS:
        raise ValueError('Expected 129 axis/curve points')
    if not all(math.isfinite(v) for v in [*axis, *curve]):
        raise ValueError('Nonfinite curve data')
    if axis[0] != 0 or not 0 < axis[-1] <= 64 or any(a >= b for a, b in zip(axis, axis[1:])):
        raise ValueError('Invalid explicit curve axis')
    if any(not 0 <= v <= 1 for v in curve) or any(a > b for a, b in zip(curve, curve[1:])):
        raise ValueError('Curve must be monotone in 0..1')


def encode(metadata, q, axis, curve):
    q, axis, curve = list(q), list(axis), list(curve)
    _validate(metadata, q, axis, curve)
    sections = [json.dumps(metadata, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False).encode('utf8'),
                struct.pack('<6h', *q), struct.pack('<129f', *axis),
                struct.pack('<129f', *curve)]
    body = b''.join(struct.pack('<4sI', tag, len(data)) + data
                    for tag, data in zip(TAGS, sections))
    total = HEADER.size + len(body)
    if total > MAX_BYTES:
        raise ValueError('Development recipe exceeds 64 KiB')
    raw = HEADER.pack(MAGIC, 1, HEADER.size, DEV_ONLY, total,
                      zlib.crc32(body), bytes(8)) + body
    decode(raw)  # Float32 encoding must preserve all range/ordering invariants.
    return raw


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate metadata key')
        result[key] = value
    return result


def decode(raw):
    if not HEADER.size <= len(raw) <= MAX_BYTES:
        raise ValueError('Invalid development recipe size')
    magic, version, header, flags, total, crc, reserved = HEADER.unpack_from(raw)
    if (magic, version, header, flags, total, reserved) != (
            MAGIC, 1, HEADER.size, DEV_ONLY, len(raw), bytes(8)):
        raise ValueError('Unsupported development recipe header')
    if zlib.crc32(raw[header:]) != crc:
        raise ValueError('Development recipe CRC mismatch')
    sections, at = {}, header
    while at < len(raw):
        if len(raw) - at < 8:
            raise ValueError('Truncated section header')
        tag, size = struct.unpack_from('<4sI', raw, at)
        at += 8
        if tag not in TAGS or tag in sections or size > len(raw) - at:
            raise ValueError('Unknown, duplicate or truncated section')
        sections[tag], at = raw[at:at+size], at+size
    if set(sections) != set(TAGS) or any(len(sections[k]) != n for k, n in (
            (b'B13Q', 12), (b'AXIS', 516), (b'CURV', 516))):
        raise ValueError('Missing or invalid section')
    metadata = json.loads(sections[b'META'].decode('utf8'), object_pairs_hook=_unique,
                          parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
    q = list(struct.unpack('<6h', sections[b'B13Q']))
    axis = list(struct.unpack('<129f', sections[b'AXIS']))
    curve = list(struct.unpack('<129f', sections[b'CURV']))
    _validate(metadata, q, axis, curve)
    return dict(metadata=metadata, q=q, axis=axis, curve=curve,
                sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def read(path):
    # Bounded read even if supplied a very large file; no stat/read race.
    with Path(path).open('rb') as handle:
        raw = handle.read(MAX_BYTES + 1)
    return decode(raw)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    args = parser.parse_args()
    recipe = read(args.file)
    print(json.dumps({k: v for k, v in recipe.items() if k not in ('axis', 'curve')},
                     ensure_ascii=False, indent=2))
