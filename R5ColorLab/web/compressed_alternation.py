"""Optimize native parameters through a frozen, exported R5 grid on the GPU."""
import numpy as np
from gpu_alternation import BlockObjective, solve_round


class CompressedGridObjective(BlockObjective):
    """The exact packed-grid response, without PC tone/tint/gray gates.

    Gradients include moving interpolation coordinates and the RGB-dependent
    paired response. The grid coefficients stay fixed during native updates.
    """
    def __init__(self, smooth, target, weights, native_start, grid, response,
                 perceptual_weight=.35, parameter_smoothing=30, device='mps', dtype=None):
        super().__init__(smooth, target, weights, native_start, None,
            perceptual_weight, parameter_smoothing, device=device, dtype=dtype)
        from residual_grid import pack, unpack
        self.packed_grid = self.gpu.tensor(unpack(pack(grid)))
        self.response = response

    def corrected(self, rgb):
        from gpu_color import paired_tensor
        return paired_tensor(self.gpu, rgb, self.packed_grid, self.response)


def residual(smooth, target, weights, native_start, grid, response, vector,
             perceptual_weight=.35, parameter_smoothing=30):
    """Float64 reference loss for the two native block acceptance checks."""
    from measured_response import get
    from optimizer_policy import smooth_loss_rows
    from parameter_smoothing import native_rows
    predicted = get(response).predict_cpu(smooth.render(vector)/16383, grid)
    data = smooth_loss_rows(predicted, np.asarray(target)/16383, perceptual_weight)
    coefficients = vector[8:104].reshape(6,16)
    hue = np.roll(coefficients,1,axis=1)-2*coefficients+np.roll(coefficients,-1,axis=1)
    smoothing = native_rows(coefficients, smooth.gamma(vector)*16,
        smooth.ctx.axis, parameter_smoothing)*np.sqrt(len(weights))
    return np.r_[(data*np.sqrt(weights)[:,None]).ravel(), hue.ravel()*.003,
        (vector[:8]-native_start[:8])*.003, smoothing]


def optimize_native(smooth, target, weights, native_start, grid, response, vector,
                    lower, upper, evaluations, round_index, progress=None,
                    perceptual_weight=.35, parameter_smoothing=30):
    from gpu_runtime import available
    if not available(): raise RuntimeError('Compressed native alternation requires Apple Metal/MPS')
    objective = CompressedGridObjective(smooth, target, weights, native_start, grid,
        response, perceptual_weight, parameter_smoothing)
    reference = lambda values: residual(smooth,target,weights,native_start,grid,
        response,values,perceptual_weight,parameter_smoothing)
    # Retain the existing one-time loss agreement gate and per-block CPU
    # float acceptance. All optimizer gradients themselves are GPU autograd.
    rows = reference(vector)
    expected = float(rows@rows)/len(weights)
    actual, _ = objective.value_gradient(vector, slice(None))
    if abs(actual-expected)>max(1e-8,abs(expected)*1e-4):
        raise ValueError(f'Compressed-grid GPU loss mismatch: {actual} vs {expected}')
    updated, audit = solve_round(objective,vector,reference,lower,upper,
        evaluations,round_index,progress)
    return updated, dict(blocks=audit, gpu_loss_gate=dict(gpu=actual,cpu=expected),
        objective='native -> actual packed grid -> Fuji target',
        coordinate_gradients=True, response_gradients=True,
        backend='Apple Metal/MPS')
