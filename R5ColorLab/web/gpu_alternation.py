"""Metal value/gradient for frozen-PC Gamma/CC1/block13 block optimization.

The mathematical training objective matches fit_anchor_native.residual.
Integer candidate evaluation and grid compression remain unchanged.
"""
import time
import numpy as np
from apple_gpu import SmoothGPU


class BlockObjective:
    def __init__(self, smooth, target, weights, native_start, pc_bundle,
                 perceptual_weight, parameter_smoothing, device='mps', dtype=None):
        import torch
        self.torch = torch
        self.gpu = SmoothGPU(smooth, device=device, dtype=dtype)
        self.continuity = None
        if getattr(smooth, 'output_continuity', None) is not None:
            from output_continuity import TensorPenalty
            bank, probe_model, amount = smooth.output_continuity
            self.continuity_gpu = SmoothGPU(probe_model, device=device, dtype=dtype)
            self.continuity = TensorPenalty(bank, self.continuity_gpu, amount)
        tensor = self.gpu.tensor
        self.target = tensor(np.asarray(target) / 16383)
        self.weights = tensor(weights)
        self.native_start = tensor(native_start)
        self.perceptual_weight = perceptual_weight
        self.smoothing = parameter_smoothing / 100
        self.target_lab = self.gpu.lab(self.target).detach()
        self.curve = None
        if pc_bundle is not None:
            curve, grid = pc_bundle[:2]
            if curve.get('mode', 'tone-tint') not in ('tone-tint', 'rgb-independent'):
                raise ValueError('GPU block optimization supports tone-tint PC curves only')
            self.curve = {key: tensor(curve[key]) for key in
                ('axis', 'tone', 'tint', 'gray_axis', 'gray_chroma')}
            self.curve.update(radius=curve['gray_protection_radius'],
                transition=curve['gray_transition'], mode=curve.get('mode', 'tone-tint'))
            if self.curve['mode'] == 'rgb-independent':
                self.curve['rgb'] = tensor(curve['rgb'])
            self.grid = tensor(np.asarray(grid).reshape(405, 3) / 256)
        self.luma = tensor([.2126, .7152, .0722])
        self.coordinate_matrix = tensor([[.299, .587, .114],
            [-.299 / (2 * .886), -.587 / (2 * .886), .5],
            [.5, -.587 / (2 * .701), -.114 / (2 * .701)]])

    def corrected(self, rgb):
        if self.curve is None:
            return rgb
        torch = self.torch
        tensor = self.gpu.tensor
        curve = self.curve
        y = rgb @ self.luma
        interpolate = self.gpu.interp
        toned = rgb + (interpolate(y, curve['axis'], curve['tone']) - y)[:, None]
        tinted = toned + torch.stack([interpolate(y, curve['axis'], curve['tint'][:, c])
            for c in range(3)], dim=1)
        if curve['mode'] == 'rgb-independent':
            tinted = torch.stack([interpolate(rgb[:, c], curve['axis'], curve['rgb'][:, c])
                for c in range(3)], dim=1)
        locus = torch.stack([interpolate(y, curve['gray_axis'], curve['gray_chroma'][:, c])
            for c in range(3)], dim=1)
        # Vector norm has a defined zero subgradient on the protected gray locus.
        distance = torch.linalg.vector_norm(rgb - y[:, None] - locus, dim=1) / np.sqrt(3)
        u = ((distance - curve['radius']) / curve['transition']).clamp(0, 1)
        gate = u.square() * (3 - 2 * u)
        coords = tinted @ self.coordinate_matrix.T
        coords = (coords - tensor([16 / 255, 0, 0])) * tensor([255 / 219, 255 / 224, 255 / 224])
        position = coords * tensor([4, 8, 8]) + tensor([0, 4, 4])
        position = torch.minimum(position.clamp(min=0), tensor([4, 8, 8]))
        low = torch.minimum(position.long(), tensor([3, 7, 7], True))
        fractions = position - low
        correction = torch.zeros_like(rgb)
        for iy in (0, 1):
            for iu in (0, 1):
                for iv in (0, 1):
                    index = (low[:, 0] + iy) * 81 + (low[:, 1] + iu) * 9 + low[:, 2] + iv
                    weight = ((fractions[:, 0] if iy else 1 - fractions[:, 0]) *
                        (fractions[:, 1] if iu else 1 - fractions[:, 1]) *
                        (fractions[:, 2] if iv else 1 - fractions[:, 2]))
                    correction = correction + weight[:, None] * self.grid[index]
        return (tinted + correction * gate[:, None]).clamp(0, 1)

    def loss(self, vector):
        torch = self.torch
        predicted = self.corrected(self.gpu.render(vector) / 16383)
        rows = (predicted - self.target).square().mean(dim=1)
        if self.perceptual_weight:
            rows = rows + ((self.gpu.lab(predicted) - self.target_lab) / 100).square().sum(dim=1) * self.perceptual_weight
        loss = (rows * self.weights).mean()
        coefficients = vector[8:104].reshape(6, 16)
        hue = torch.roll(coefficients, 1, 1) - 2 * coefficients + torch.roll(coefficients, -1, 1)
        loss = loss + (hue.square().sum() + (vector[:8] - self.native_start[:8]).square().sum()) * .003**2 / len(rows)
        return loss + self.smoothing_loss(vector)

    def smoothing_loss(self, vector):
        torch = self.torch
        coefficients = vector[8:104].reshape(6, 16)
        hue = torch.roll(coefficients, 1, 1) - 2 * coefficients + torch.roll(coefficients, -1, 1)
        axis = self.gpu.axis / self.gpu.axis[-1]
        dx = torch.diff(axis)
        gamma = self.gpu.gamma(vector) * 16 / 262143
        curvature = torch.diff(torch.diff(gamma) / dx) * (dx[:-1] + dx[1:]) / 2
        loss = (hue.square().mean() * .02**2 + curvature.square().mean() * 16**2) * self.smoothing
        if self.continuity is not None:
            loss = loss + self.continuity.loss(self.continuity_gpu.render(vector) / 16383)
        return loss

    def value_gradient(self, vector, indices):
        v = self.gpu.tensor(vector).requires_grad_(True)
        loss = self.loss(v)
        loss.backward()
        value = float(loss.detach().cpu())
        gradient = v.grad.detach().cpu().numpy().astype(float)[indices]
        if not np.isfinite(value) or not np.isfinite(gradient).all():
            raise ValueError('Nonfinite GPU block objective or gradient')
        return value, gradient


def solve_round(objective, vector, residual, lower, upper, evaluations, round_index, progress=None):
    """GPU analytic gradients, CPU bound solver, then CPU objective acceptance.

    The caller still runs native integer assessment and rebuilds PC. No target
    or validation changes, and no float32 candidate bypasses CPU loss acceptance.
    """
    from scipy.optimize import minimize
    current = np.clip(np.asarray(vector, float), lower + 1e-5, upper - 1e-5)
    audit = []
    for name, indices in (('Gamma', slice(104, None)), ('CC1 / block13', slice(0, 104))):
        frozen = current.copy()
        rows = residual(frozen)
        before = float(rows @ rows)
        calls = 0
        started = time.perf_counter()
        stage = f'Gamma 与色彩交替 {round_index}：{name}（Metal梯度）'
        if progress:
            progress(stage=stage, state='running', iteration=0, evaluations=0,
                max_evaluations=evaluations, gpu_backend='Apple Metal/MPS')

        def objective_block(values):
            nonlocal calls
            trial = frozen.copy()
            trial[indices] = values
            result = objective.value_gradient(trial, indices)
            calls += 1
            if progress and calls % 10 == 0:
                progress(evaluations=calls, gpu_loss=result[0])
            return result

        result = minimize(objective_block, frozen[indices], jac=True, method='L-BFGS-B',
            bounds=list(zip(lower[indices], upper[indices])),
            options=dict(maxiter=evaluations, maxfun=evaluations, ftol=1e-7, gtol=1e-8, maxls=12))
        trial = frozen.copy()
        trial[indices] = result.x
        rows = residual(trial)
        after = float(rows @ rows)
        accepted = bool(np.isfinite(after) and after < before)
        if accepted:
            current = trial
        audit.append(dict(block=name, before=before, after=after, accepted=accepted,
            nfev=int(result.nfev), converged=bool(result.success), backend='Apple Metal/MPS',
            message=str(result.message), seconds=time.perf_counter() - started,
            cpu_objective_acceptance=True))
        if progress:
            progress(evaluations=int(result.nfev), state='round_done', gpu_backend=None)
    return current, audit
