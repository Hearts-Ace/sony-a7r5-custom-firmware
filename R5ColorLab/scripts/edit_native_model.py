"""Bounded Edit-derived parameter stages, NOT a complete RAW renderer.

Pure PC calculations. Matrix expansion currently supports identity calibration
and no extra output-gamut matrix only. Gamma accepts an explicitly supplied
contrast table. Sources and instruction replay are recorded beside this module.
"""
from pathlib import Path
import sys
import struct
import numpy as np


def _integer_array(value, columns, low, high, name):
    a = np.asarray(value)
    if (a.ndim != 2 or a.shape[1] != columns or not np.all(np.isfinite(a))
            or np.any(a != np.trunc(a)) or np.any(a < low) or np.any(a > high)):
        raise ValueError(f'{name}: expected Nx{columns} integers in [{low},{high}]')
    return a.astype(np.int64)


def rgb_to_ycc(rgb, coefficients, luma_weights, keep_unclipped=False):
    """Edit photo task 0x1000eed30, including effective CC1 bit decoding.

    RGB is signed 16-bit after MainGamma. Coefficients are eight already
    selected RAW CC1 shorts, NOT the decoded coefficients of cc1_chroma.
    luma_weights are runtime signed shorts (RAW 7801 values << 7).
    Returns uint16 Y, Cr+32768, Cb+32768. Do not also apply cc1_chroma.
    """
    a = _integer_array(rgb, 3, -32768, 32767, 'RGB')
    c = _integer_array(np.asarray(coefficients)[None, :], 8, -32768, 32767, 'CC1')[0]
    weights = _integer_array(np.asarray(luma_weights)[None, :], 3, -32768, 32767, 'luma')[0]
    bits = (c[:4] & 65535) >> 2 & 511
    mixed = np.where(bits > 255, bits-512, bits)
    gains = ((c[4:] & 65535) >> 3 & 255).astype(np.float32)
    dr = a[:, 0]-a[:, 1]; db = a[:, 2]-a[:, 1]
    # FMADD performs one float32 rounding after the multiplication/addition.
    cb = (db+dr*np.where(dr >= 0, mixed[1], mixed[3])/256).astype(np.float32)
    cr = (dr+db*np.where(db >= 0, mixed[0], mixed[2])/256).astype(np.float32)
    cr = cr*np.float32(.5)*np.where(cr >= 0, gains[1], gains[3])*np.float32(1/64)
    cb = cb*np.float32(.5)*np.where(cb >= 0, gains[0], gains[2])*np.float32(1/64)
    if not keep_unclipped:
        cr = np.clip(cr, -8192, 8191); cb = np.clip(cb, -8192, 8191)
    y = (np.einsum('ij,j->i', a, weights, optimize=False) >> 13) & 65535
    cr = np.trunc(np.clip(cr+np.float32(32768), 0, 65535)).astype(np.int64)
    cb = np.trunc(np.clip(cb+np.float32(32768), 0, 65535)).astype(np.int64)
    return np.stack([y, cr, cb], axis=1).astype('<u2')


def ycc_to_rgb(ycc):
    """Edit task 0x1000fc164; integer division truncates toward zero."""
    a = _integer_array(ycc, 3, 0, 65535, 'YCC')
    y, cr, cb = a.T; cr = cr-32768; cb = cb-32768
    numerators = np.stack([y*10000+cr*14020,
        y*10000-cr*7141-cb*3441, y*10000+cb*17720], axis=1)
    values = np.sign(numerators)*(np.abs(numerators)//10000)
    return np.clip(values, 0, 16383).astype('<u2')


def cc1_chroma(coefficients, chroma, keep_unclipped=False):
    """0x1000bfe60 chroma kernel after effective 8-coefficient selection.

    Input/output are signed 16-bit chroma coordinates, NOT RGB. The complete
    surrounding chroma table and RGB/YCC stages are deliberately not implied.
    """
    c = np.asarray(coefficients)
    uv = np.asarray(chroma, dtype=np.float64)
    if c.shape != (8,) or not np.all(np.isfinite(c)) or np.any(c != np.trunc(c)) or np.any(c < -32768) or np.any(c > 32767):
        raise ValueError('Expected eight signed 16-bit coefficients')
    if uv.ndim != 2 or uv.shape[1] != 2 or not np.all(np.isfinite(uv)) or np.any(uv != np.trunc(uv)) or np.any(uv < -32768) or np.any(uv > 32767):
        raise ValueError('Expected Nx2 signed 16-bit chroma coordinates')
    u, v = uv.T
    p = u*.0235833125+v*.00303415625
    q = u*.0079583125+v*.01865915625
    mixed_p = p+np.where(q>=0,c[0],c[2])*q/1024
    mixed_q = q+np.where(p>=0,c[1],c[3])*p/1024
    gain_p = mixed_p*np.where(mixed_p>=0,c[5],c[7])/1024
    gain_q = mixed_q*np.where(mixed_q>=0,c[4],c[6])/1024
    if not keep_unclipped:
        # Assembly 0x1000bff78..90 clamps BOTH channels. Ghidra pseudocode
        # omitted one FMAXNM lower bound; the instruction replay catches it.
        gain_q = np.clip(gain_q,-128,127)
        gain_p = np.clip(gain_p,-128,127)
    out_u = (gain_q*.000037+gain_p*1.401988)*64
    out_v = (gain_q*1.771978+gain_p*.000135)*64
    return np.trunc(np.clip(np.stack([out_u,out_v],axis=1),-32768,32767)).astype('<i2')


def expand_gamma(axis, values, contrast=None):
    """Reconstruct 0x1000c82d4, including optional contrast and signed layout.

    Positive index i samples RAW x=128*i. Intermediate calculations are float32,
    conversion truncates toward zero, then ASR 2 and LSR 2 precede uint16 store.
    Return the complete 65536-entry storage; its zero pointer is entry 32768.
    """
    x = np.asarray(axis, dtype=np.int64)
    y = np.asarray(values, dtype=np.int64)
    if x.ndim != 1 or x.size < 2 or x.size > 128 or x.shape != y.shape:
        raise ValueError('Expected 2..128 equal-size parameter arrays')
    if x[0] != 0 or y[0] != 0 or np.any(np.diff(x) <= 0):
        raise ValueError('Only strictly increasing zero-origin axes are modeled')
    if np.any(x > 2147483647) or np.any(y < 0) or np.any(y > 2147483647):
        raise ValueError('Parameters outside supported signed int32 domain')
    sample = np.arange(1, 32768, dtype=np.int64)*128
    right = np.searchsorted(x, sample, side='right')
    left = np.maximum(0, right-1)
    right = np.minimum(right, len(x)-1)
    delta = x[right]-x[left]
    # Keep the operation order of FMUL / FDIV / FADD (not generic np.interp).
    val = y[left].astype(np.float32)-y[right].astype(np.float32)
    val *= (x[right]-sample).astype(np.float32)
    val /= np.where(delta == 0, 1, delta).astype(np.float32)
    val += y[right].astype(np.float32)
    val = np.where(delta == 0, y[left].astype(np.float32), val)
    v = np.trunc(val).astype(np.int64)
    shifted = (v >> 2).astype(np.uint32)
    if contrast is not None:
        table = np.asarray(contrast)
        if table.shape not in [(1024,),(1025,)] or not np.issubdtype(table.dtype,np.integer):
            raise ValueError('Contrast requires 1024 or 1025 integer entries')
        if np.any(table < 0) or np.any(table > 2147483647):
            raise ValueError('Contrast outside supported nonnegative int32 domain')
        index = np.minimum(v >> 8,1023)
        right = np.minimum(index+1,1023)
        lo,hi = table[index].astype(np.float32),table[right].astype(np.float32)
        fraction = (shifted.astype(np.int64)-(v >> 8)*64).astype(np.float32)
        fraction *= np.float32(1/64)
        mapped = ((hi-lo).astype(np.float64)*fraction.astype(np.float64)
                  + lo.astype(np.float64)).astype(np.float32)
        shifted = np.trunc(mapped).astype(np.uint32)
    positive = (shifted >> 2).astype('<u2')
    out = np.zeros(65536, dtype='<u2')
    out[32769:] = positive
    # Original loop includes the zero entry and reverses 32768 samples.
    out[:32768] = ((-out[32768:].astype(np.int64)[::-1]) & 65535).astype('<u2')
    return out


def _signed_field(v):
    """Preserve native bit decoding, including odd negative quantization."""
    return -(((v >> 2) & 0x3ffe) ^ 0x3fff)/1024 if v & 0x8000 else ((v >> 2) & 0x3fff)/1024


def decode_matrix16(payload):
    """Decode the full 276-byte 0x780F record to the native 552-byte config."""
    if len(payload) != 276:
        raise ValueError('0x780F must have exactly 276 bytes')
    w = struct.unpack('<69I', payload)
    cfg = bytearray(0x228)
    def h(at, value): struct.pack_into('<H', cfg, at, value)
    def f(at, value): struct.pack_into('<f', cfg, at, value)
    h(0, w[0] >> 24 & 1); h(2, w[0] >> 25 & 1); h(4, w[0] >> 23 & 1)
    angles = [(w[0] >> 11) & 1023, w[0] & 1023]
    for i in range(1, 5): angles.extend([w[i] >> 22, w[i] >> 11 & 1023, w[i] & 1023])
    angles.extend([w[5] >> 22, w[5] >> 11 & 1023])
    if any(a >= b for a, b in zip(angles, angles[1:])):
        raise ValueError('Unsupported unordered sector boundaries')
    for i, value in enumerate(angles): h(6+2*i, value)
    h(0x26, w[0] >> 26 & 3)
    for i, v in enumerate(struct.unpack_from('<96H', payload, 24)):
        # Each packed uint32 writes its upper half first, then lower half.
        f(0x28+4*(i ^ 1), _signed_field(v))
    for i in range(16):
        v = w[54+i//2]
        h(0x1e8+2*i, (v >> (18 if i % 2 == 0 else 2)) & 4095)
    f(0x208, _signed_field(w[62] >> 16)); f(0x20c, _signed_field(w[62] & 65535))
    f(0x210, _signed_field(w[63] >> 16))
    scales = [w[63] >> 8 & 255, w[63] & 255]
    for i in range(64, 67): scales.extend([w[i] >> 24, w[i] >> 16 & 255, w[i] >> 8 & 255, w[i] & 255])
    scales.extend([w[67] >> 24, w[67] >> 16 & 255])
    for i, value in enumerate(scales): f(0x1a8+4*i, value/128)
    for i, value in enumerate([w[67] & 65535, w[68] >> 16, w[68] & 65535]): f(0x214+4*i, value/32)
    h(0x220, w[0] >> 31); h(0x222, w[0] >> 30 & 1); h(0x224, w[0] >> 28 & 3)
    return bytes(cfg)


def expand_matrix16(config):
    """1024 x (9 linear + 9 quadratic), restricted builder context.

    Mirrors interpolation in 0x1000d77e4 for identity camera calibration and
    param9+0x44=3 (no additional output-gamut matrix). This is NOT CC1 processing.
    Algebraically equivalent float64 evaluation; instruction replay quantifies
    its float32/FMA residual. No hidden substitution for calibration is made.
    """
    if len(config) != 0x228: raise ValueError('Invalid matrix16 config')
    angles = np.array(struct.unpack_from('<16H', config, 6))
    coeff = np.array(struct.unpack_from('<96f', config, 0x28)).reshape(6,16)
    scales = np.array(struct.unpack_from('<16f', config, 0x1a8))
    norm = np.array(struct.unpack_from('<16H', config, 0x1e8))
    diag = struct.unpack_from('<3f', config, 0x208)
    mode = struct.unpack_from('<H', config, 0x26)[0]
    factor = 1/(4096*(2 << mode)) if mode < 3 else 1/65536
    out = np.empty((1024,18), dtype=np.float64)
    for sector in range(1024):
        right = int(np.searchsorted(angles, sector, side='right'))
        left = (right-1) % 16; right %= 16
        a, b = int(angles[left]), int(angles[right])
        if b <= a: b += 1024
        t = sector if sector >= a else sector+1024
        weight = np.array([b-t, t-a])*norm[left]*factor
        q = np.einsum('ij,j->i', coeff[:,[left,right]], weight, optimize=False)
        z = np.einsum('ij,j->i', coeff[:,[left,right]]*scales[[left,right]], weight, optimize=False)
        a,b,c,d,e,f = q
        linear = [a+b+diag[0],-a,-b,-c,c+d+diag[1],-d,-e,-f,e+f+diag[0]]
        a,b,c,d,e,f = z
        quadratic = [-a-b,a,b,c,-c-d,d,e,f,-e-f]
        out[sector] = linear+quadratic
    return out
