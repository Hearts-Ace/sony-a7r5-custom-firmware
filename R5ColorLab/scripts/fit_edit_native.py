"""Fit quantized CC1, 16-sector block13, and 128-knot Gamma to paired data.

Inputs are integer RGB AFTER Edit RAW decoding/WB/demosaic/SSCS, not sRGB or
unlabeled sensor RGB. Targets are explicit desired 14-bit encoded RGB. The
renderer is the measured COLOR SUBCHAIN; it does not pretend spatial NR,
sharpening, JPEG compression or a missing S-Log3 input bridge are identity.
"""
from pathlib import Path
import argparse
from functools import lru_cache
import hashlib
import json
import struct
from edit_parameter_context import ParameterContext, RuntimeColor, np, quantize_matrix_coefficients


def sha(data): return hashlib.sha256(data).hexdigest()


def metrics(predicted,target):
    delta=np.asarray(predicted,dtype=np.float64)-np.asarray(target,dtype=np.float64)
    return dict(mae_14bit_codes=float(np.mean(np.abs(delta))),
        rmse_14bit_codes=float(np.sqrt(np.mean(delta**2))),
        p95_abs_14bit_codes=float(np.percentile(np.abs(delta),95)),
        maximum_abs_14bit_codes=float(np.max(np.abs(delta))),pixels=int(delta.size//3))
