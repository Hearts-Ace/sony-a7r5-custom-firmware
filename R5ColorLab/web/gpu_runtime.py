"""Explicit per-process Metal policy; existing CPU jobs keep their environment."""
import os
from functools import lru_cache


@lru_cache(maxsize=1)
def available():
    if os.environ.get('R5_GPU_TRAINING', '0').lower() in ('0', 'false', 'cpu', 'off'):
        return False
    try:
        import torch
        return torch.backends.mps.is_available()
    except ImportError:
        return False


def policy():
    return dict(requested=os.environ.get('R5_GPU_TRAINING', '0'),
        available=available(), backend='Apple Metal/MPS' if available() else 'CPU 8 threads')
