"""Deterministic train-only representatives of the measured matrix hue domain.

No invented RGB/HSV chart, interpolation, extra RAW capture or split changes.
"""
import struct
import numpy as np


def select(arrays, model):
    x = arrays['input']
    rgb = x[:, 4].astype(float)/16383
    hue = model.sectors(x)[:, 4]
    knots = np.array(struct.unpack_from('<16H', model.config, 6))
    luminance = rgb @ (np.array([109, 366, 37])/512)
    saturation = np.ptp(rgb, axis=1)/np.maximum(np.max(rgb, axis=1), 1/16383)
    pool = (arrays['split'] == 'train') & (arrays['anchor_index'] < 0) & (saturation > .15)
    ids = np.full(len(x), -1, dtype=np.int32)
    records = []
    # Three measured representatives per knot plus one inter-knot midpoint.
    # Match locally available brightness quantiles, rather than promise an
    # unattainable uniform brightness/saturation grid from a finite capture.
    for kind, count in [('node', 3), ('transition', 1)]:
        for k, knot in enumerate(knots):
            following = int(knots[(k+1) % 16])
            target = int(knot) if kind == 'node' else (int(knot) + ((following-int(knot)) % 1024)//2) % 1024
            distance = np.abs((hue-target+512) % 1024-512)
            local = pool & (distance <= 48)
            if np.sum(local) < count:
                raise ValueError('现有实采训练色块不足以覆盖矩阵方向 %d' % k)
            levels = np.quantile(luminance[local], [.2, .5, .8]) if count == 3 else [np.median(luminance[local])]
            for level in levels:
                candidates = np.flatnonzero(local & (ids < 0))
                if not len(candidates):
                    raise ValueError('矩阵色相代表色重复或不足')
                score = (distance[candidates]/32)**2 + ((luminance[candidates]-level)/.08)**2
                i = int(candidates[np.argmin(score)])
                ids[i] = len(records)
                records.append(dict(index=len(records), source_row=i, kind=kind, node=k,
                                    target_sector=target, measured_sector=int(hue[i]),
                                    circular_error=int(distance[i]), luminance=float(luminance[i]),
                                    saturation=float(saturation[i])))
    return ids, dict(schema='r5-measured-sector16/1', records=records,
                     knots=knots.tolist(), samples=len(records), training_only=True,
                     source='existing measured random training patches; no split changes',
                     exact_knots=False, maximum_sector_error=max(r['circular_error'] for r in records))


def validate(arrays, model):
    if 'sector16_index' not in arrays:
        return None
    expected, audit = select(arrays, model)
    if not np.array_equal(arrays['sector16_index'], expected):
        raise ValueError('矩阵16色相训练来源或选择发生变化')
    return audit
