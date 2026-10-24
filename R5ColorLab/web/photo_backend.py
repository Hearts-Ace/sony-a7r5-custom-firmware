"""Exact, bounded-memory TPS evaluation for photograph-sized batches.

Kept outside the calibrated model so its training/report identity is unchanged.
Only the distance/kernel evaluation backend changes; no sampled render LUT.
"""
import types
import numpy as np


def fast_forward(self, coordinates, derivative=False):
    if derivative:
        return self._photo_original_forward(coordinates, derivative=True)
    from scipy.spatial.distance import cdist
    from scipy.special import xlogy
    points = np.asarray(coordinates, float)
    result = np.empty((len(points), 3), dtype=float)
    for start in range(0, len(points), 1024):
        at = points[start:start+1024]
        kernel = cdist(at, self.x, 'sqeuclidean')
        xlogy(kernel, kernel, out=kernel)
        kernel *= .5
        result[start:start+len(at)] = (kernel @ self.a +
            np.c_[np.ones(len(at)), (at-self.shift)/self.norm] @ self.b)
    return result


def enable(response):
    """Enable only in the isolated photo worker, never in training/server."""
    import measured_response
    if not measured_response.is_measured(response):
        return
    model = measured_response.get(response)
    if hasattr(model, 'forward') and not hasattr(model, '_photo_original_forward'):
        model._photo_original_forward = model.forward
        model.forward = types.MethodType(fast_forward, model)
