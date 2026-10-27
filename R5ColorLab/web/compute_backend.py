"""Eight bounded workers for independent native color batches.

Do not nest BLAS thread pools inside finite-difference workers. Sequential
coordinate-descent decisions keep their original order.
"""
from concurrent.futures import ThreadPoolExecutor
import numpy as np

WORKERS=8


def render_native(model, inputs):
    values=np.asarray(inputs)
    from gpu_runtime import available
    if available():
        from gpu_native import renderer
        return renderer(model).render(values)
    if len(values)<2048:return model.color_only(values)
    parts=np.array_split(values,WORKERS)
    with ThreadPoolExecutor(max_workers=WORKERS,thread_name_prefix='r5-native') as pool:
        return np.concatenate(list(pool.map(model.color_only,parts)))
