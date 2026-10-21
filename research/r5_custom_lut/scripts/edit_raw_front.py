"""Explicit RAW-code front for Edit's verified RGGB/as-shot flatfield branch.

This is not a demosaicer for textured photographs and deliberately does not
skip scene-dependent Vatr or claim its output is matrix-task input.
"""
import math
import struct
from edit_native_model import np, _integer_array


def short(value):
    return (int(value)+32768) % 65536 - 32768


def as_shot_wb(raw, settings):
    if len(raw) < 0x1400 or len(settings) < 0x2b2:
        raise ValueError('Incomplete RAW/settings context')
    if struct.unpack_from('<4i', raw, 0x84) != (0, 1, 1, 2):
        raise ValueError('Only verified RGGB channel mapping is supported')
    if struct.unpack_from('<i', settings, 0x1e8)[0] != 1:
        raise ValueError('Only as-shot WB is implemented; no implicit fallback')
    wb4 = struct.unpack_from('<4h', raw, 0x4a)
    if wb4[1] != wb4[2]:
        raise ValueError('Unequal green WB requires a separate field model')
    values = [wb4[0], wb4[1], wb4[3]]
    tables = [struct.unpack_from('<3h', raw, o) for o in
              [0xf46, 0xf4c, 0xf52, 0xf5e, 0xf6a]]
    red = values[0]
    # Native 13d240: piecewise calibrated Kelvin estimate, including end
    # extrapolation. All divisions below truncate toward zero, not floor.
    anchors = [2500, 3200, 4500, 6000, 8500]
    if red < tables[0][0]:
        delta = tables[1][0]-tables[0][0]
        cct = 2500 if delta == 0 else 2500-math.trunc((tables[0][0]-red)*700.0/delta)
    elif red >= tables[4][0]:
        delta = tables[4][0]-tables[3][0]
        cct = 8500 if delta == 0 else 8500+math.trunc((red-tables[4][0])*2500.0/delta)
    else:
        index = next(i for i in range(4) if red < tables[i+1][0])
        delta = tables[index+1][0]-tables[index][0]
        cct = anchors[index+1] if delta == 0 else anchors[index]+math.trunc(
            (red-tables[index][0])*(anchors[index+1]-anchors[index])/delta)
    index = 0 if cct < 3200 else 1 if cct < 4500 else 2 if cct < 6000 else 3
    shift = struct.unpack_from('<i', settings, 0x1f0)[0]
    factor = shift * [1/700, 1/1300, 1/1500, 1/2500][index]
    values = [short(v+short(math.trunc(factor*(tables[index+1][c]-tables[index][c]))))
              for c, v in enumerate(values)]
    ev = struct.unpack_from('<i', settings, 0x1f8)[0]
    scale = struct.unpack_from('<I', raw, 0x9d8)[0]/256 * math.pow(2, ev/300)
    scaled = [math.trunc(v*scale) for v in [values[0], values[1], values[1], values[2]]]
    tint = struct.unpack_from('<i', settings, 0x1f4)[0]
    adjustment = math.pow(2, abs(tint*.01)*0.6780719051126377)
    if tint < 0:
        adjustment = 2-adjustment
    scaled[0] = math.trunc(adjustment*scaled[0])
    scaled[3] = math.trunc(adjustment*scaled[3])
    return np.array([short(v) for v in scaled], dtype='<i2')


def itp_flatfield(sensor_codes, raw, settings):
    """Uniform Bayer field → ITP RGB, before Vatr and SSCS, native code units.

    The first verified branch requires equal green black levels and gains.
    Do not pass normalized floats, linear709, or completed ST image values.
    """
    codes = _integer_array(sensor_codes, 3, 0, 16383, 'sensor RAW codes')
    wb = as_shot_wb(raw, settings).astype(np.float32)
    black = np.array(struct.unpack_from('<4H', raw, 0x38), dtype=np.int64)
    if black[1] != black[2] or wb[1] != wb[2]:
        raise ValueError('Green phase mismatch is outside verified flatfield scope')
    scale = struct.unpack_from('<H', raw, 0x40)[0]
    gains = np.float32(scale)*np.float32(1/32768)*wb
    gains = gains*np.float32(1/16)
    out = (codes-black[[0,1,3]]).astype(np.float32)*gains[[0,1,3]]
    return np.trunc(np.clip(out, 0, 16383)).astype('<u2')
