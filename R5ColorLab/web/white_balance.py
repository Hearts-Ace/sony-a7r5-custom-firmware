from compute_backend import render_native
from patch_sampling import center_mean
"""Experimental pre-ITP WB; measured downstream frontend residual is frozen.

Gain math is Edit-derived. Dynamic Vatr/SSCS response is NOT reconstructed.
No camera menu scale or firmware export equivalence is implied.
"""
import struct
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import numpy as np
from edit_raw_front import as_shot_wb, itp_flatfield

ZERO = dict(temperature_shift=0, tint=0)


def validate(value=None):
    result = dict(ZERO if value is None else value)
    if set(result) != set(ZERO):
        raise ValueError('无效白平衡参数')
    for key, limit in [('temperature_shift', 1000), ('tint', 50)]:
        v = result[key]
        if isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, float, np.integer, np.floating)) or not np.isfinite(v) or abs(v) > limit:
            raise ValueError('白平衡参数超出实验范围')
        result[key] = int(round(v))
    return result


def active(value):
    return any(validate(value).values())


def settings_for(model, value):
    value = validate(value)
    settings = bytearray(model.settings)
    struct.pack_into('<i', settings, 0x1e8, 1)
    struct.pack_into('<i', settings, 0x1f0, value['temperature_shift'])
    struct.pack_into('<i', settings, 0x1f4, value['tint'])
    return bytes(settings)


def inputs(model, measured, sensor_codes, value=None):
    value = validate(value)
    if not active(value):
        return measured
    # Apply the WB at the sensor/ITP stage. Preserve only the measured baseline
    # difference between ITP and downstream frontend, not its dynamic response.
    sensor = np.asarray(sensor_codes)
    baseline = itp_flatfield(sensor, model.raw, model.settings).astype(float)
    adjusted = itp_flatfield(sensor, model.raw, settings_for(model, value)).astype(float)
    return np.trunc(np.clip(np.asarray(measured, float) +
                            (adjusted-baseline)[:, None, :], 0, 16383)).astype('<u2')


def from_recipe(recipe):
    return validate(recipe.get('white_balance', {}).get('parameters'))


def render_pairs(model, pairs, recipe, index=slice(None)):
    if not active(from_recipe(recipe)):
        return center_mean(render_native(model,pairs['input'][index]))
    return center_mean(model.color_only(inputs(model, pairs['input'][index],
                                   pairs['sensor_codes'][index], from_recipe(recipe))))


def photo_gains(model, wb, value):
    """Use this photograph's as-shot WB with the reference calibration table."""
    if not active(value):
        return np.ones(3)
    raw = bytearray(model.raw)
    reference = np.array(struct.unpack_from('<4h', raw, 0x4a), float)
    wb = np.asarray(wb, float) / wb[1]
    channels = np.rint(reference[1] * wb).astype(int)
    struct.pack_into('<4h', raw, 0x4a, channels[0], channels[1], channels[1], channels[2])
    base = as_shot_wb(raw, model.settings).astype(float)[[0, 1, 3]]
    adjusted = as_shot_wb(raw, settings_for(model, value)).astype(float)[[0, 1, 3]]
    if np.any(base <= 0) or np.any(adjusted <= 0):
        raise ValueError('白平衡增益无效')
    return adjusted / base


def report(value, enabled):
    return dict(enabled=bool(enabled), parameters=validate(value), target_fixed=True,
                frontend_approximate=True, camera_apply_allowed=False,
                model='Edit-as-shot-WB+flatfield-ITP+frozen-measured-frontend-residual',
                limits=['Vatr/SSCS response to WB is frozen, not recomputed.',
                        'Edit units; camera AB/GM menu scale is uncalibrated.',
                        'WB is PC-only; native BIN/ARW export does not contain WB.'])
