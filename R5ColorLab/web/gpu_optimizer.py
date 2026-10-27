"""GPU objectives for every floating native-fit stage, with CPU loss gates."""
import time
import numpy as np
from gpu_alternation import BlockObjective
from apple_gpu import SmoothGPU


class StageObjective(BlockObjective):
    def __init__(self, smooth, gray_model, target, gray_target, weights, native_start,
                 pc_bundle, perceptual_weight, parameter_smoothing, *, mode='joint',
                 fixed=None, indices=slice(None), reference=None, device='mps', dtype=None):
        super().__init__(smooth, target, weights, native_start, pc_bundle if mode == 'joint' else None,
            perceptual_weight, parameter_smoothing, device=device, dtype=dtype)
        self.mode = mode
        self.fixed = self.gpu.tensor(native_start if fixed is None else fixed)
        self.indices = indices
        self.gray_gpu = SmoothGPU(gray_model, device=device, dtype=dtype) if mode != 'joint' else None
        self.gray_target = self.gpu.tensor(np.asarray(gray_target) / 16383)
        self.reference = self.gpu.tensor(np.asarray(reference) / 16383) if reference is not None else None
        self.normalization = len(weights)

    def stage_loss(self, values):
        torch = self.torch
        full = self.fixed.clone()
        full[self.indices] = values
        if self.mode == 'joint':
            return super().loss(full)
        gray_delta = self.gray_gpu.render(full) / 16383 - self.gray_target
        if self.mode == 'tone':
            loss = (gray_delta @ self.luma).square().sum()
            loss = loss + torch.diff(full[104:], n=2).square().sum() * .0002**2
        elif self.mode == 'gray':
            predicted = self.gpu.render(full) / 16383
            loss = gray_delta.square().sum()
            loss = loss + (full[:104] - self.native_start[:104]).square().sum() * .0001**2
            loss = loss + (predicted - self.reference).square().sum() * .5**2
        elif self.mode == 'chroma':
            predicted = self.gpu.render(full) / 16383
            delta = predicted - self.target
            chroma = delta - (delta @ self.luma)[:, None]
            loss = (chroma.square().sum(dim=1) * self.weights).sum()
            loss = loss + (gray_delta @ self.luma).square().sum()
            loss = loss + (predicted - self.reference).square().sum() * .1**2
            loss = loss + (full[:104] - self.native_start[:104]).square().sum() * .0001**2
        else:
            raise ValueError('Unknown GPU objective stage')
        return loss / self.normalization + self.smoothing_loss(full)

    def value_gradient_stage(self, values):
        tensor = self.gpu.tensor(values).requires_grad_(True)
        value = self.stage_loss(tensor)
        value.backward()
        scalar = float(value.detach().cpu())
        gradient = tensor.grad.detach().cpu().numpy().astype(float)
        if not np.isfinite(scalar) or not np.isfinite(gradient).all():
            raise ValueError('Nonfinite GPU training value or gradient')
        return scalar, gradient


def minimize_stage(factory, residual, initial, options, progress):
    from scipy.optimize import minimize, OptimizeResult
    objective = factory()
    seed = np.asarray(initial, float)
    normalization = objective.normalization
    before_rows = residual(seed)
    before = float(before_rows @ before_rows)
    value, initial_gradient = objective.value_gradient_stage(seed)
    expected = before / normalization
    if abs(value - expected) > max(1e-8, abs(expected) * 1e-4):
        raise ValueError(f'GPU loss gate failed: {value} versus {expected}')
    lower, upper = options['bounds']
    lower = np.broadcast_to(lower, seed.shape)
    upper = np.broadcast_to(upper, seed.shape)
    limit = options.get('max_nfev', 200)
    calls = 0
    best = seed.copy()
    best_value = value
    best_gradient = initial_gradient
    started = time.perf_counter()

    class BudgetReached(Exception):
        pass

    def value_gradient(values):
        nonlocal calls, best, best_value, best_gradient
        if calls >= limit:
            raise BudgetReached()
        result = objective.value_gradient_stage(values)
        calls += 1
        if result[0] < best_value:
            best = values.copy()
            best_value = result[0]
            best_gradient = result[1].copy()
        if calls % 10 == 0:
            progress.update(evaluations=calls, gpu_loss=result[0])
        return result

    def callback(values):
        progress.update(iteration=progress.value['iteration'] + 1, evaluations=calls)

    progress.update(gpu_backend='Apple Metal/MPS', gpu_loss=value,
        gradient_method='autograd; one shared forward/backward pass')
    try:
        result = minimize(value_gradient, seed, jac=True, method='L-BFGS-B',
            bounds=list(zip(lower, upper)), callback=callback,
            options=dict(maxfun=limit, maxiter=limit, maxls=15,
                ftol=min(options.get('ftol', 1e-7), 1e-7), gtol=options.get('gtol', 1e-8), maxcor=20))
        success = bool(result.success)
        message = str(result.message)
        status = 2 if success else (0 if result.status == 1 else -1)
    except BudgetReached:
        success = False
        status = 0
        message = 'GPU objective evaluation budget reached'
    after_rows = residual(best)
    after = float(after_rows @ after_rows)
    accepted = bool(np.isfinite(after) and after < before)
    if not accepted:
        best, after = seed, before
    return OptimizeResult(x=best, cost=after / 2, optimality=float(np.max(np.abs(best_gradient))),
        nfev=calls, success=success, status=status, message=message, backend='Apple Metal/MPS',
        cpu_objective_before=before, cpu_objective_after=after, cpu_objective_accepted=accepted,
        seconds=time.perf_counter() - started)
