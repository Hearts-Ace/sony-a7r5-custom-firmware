"""Resident Metal grid operators and bounded accelerated gradient solves."""
from functools import lru_cache
import time
import numpy as np
from gpu_tensor import TensorTools, stencil_tensor, provisional_coordinates


@lru_cache(maxsize=4)
def edges(shape):
    indices = np.arange(int(np.prod(shape))).reshape(shape)
    return np.concatenate([np.stack((np.take(indices, range(shape[d] - 1), axis=d).ravel(),
        np.take(indices, range(1, shape[d]), axis=d).ravel()), axis=1) for d in range(3)])


def fit(base, target, mass, strength, *, gate=None, response=None, shape=(5, 9, 9),
        iterations=600, continuous=False):
    import torch
    tools = TensorTools()
    x, desired = tools.tensor(base), tools.tensor(target)
    weights = tools.tensor(np.asarray(mass) / np.sum(mass))
    n = int(np.prod(shape))
    paired = isinstance(response, dict)
    if paired:
        from measured_response import get
        model = get(response)
        if not hasattr(model, 'affine'):
            raise ValueError('Metal grid solve supports R5 paired response snapshots')
        affine = tools.tensor(model.affine)
        coordinates = x @ affine[:, :3].T + affine[:, 3]
        mixing = tools.tensor(model.response(np.asarray(base)) * 256)
    else:
        coordinates = provisional_coordinates(tools, x)
        mixing = tools.tensor(np.eye(3) if response is None else response).expand(len(x), 3, 3)
    indices, interpolation = stencil_tensor(tools, coordinates, shape)
    gates = tools.tensor(np.ones(len(x)) if gate is None else gate)
    neighbors = tools.tensor(edges(tuple(shape)), True)
    penalty = strength / n
    ridge = 0 if paired else 1e-10

    def predict(v):
        delta = (v[indices] * interpolation[:, :, None]).sum(dim=1) * gates[:, None]
        rgb = x + torch.einsum('nc,nco->no', delta, mixing)
        return rgb.clamp(0, 1) if paired else rgb

    def objective(v):
        error = ((predict(v) - desired).square().sum(dim=1) * weights).sum()
        neighbor = (v[neighbors[:, 0]] - v[neighbors[:, 1]]).square().sum() * penalty
        return error + neighbor + v.square().sum() * ridge

    # Gershgorin upper bound for the fixed interpolation normal operator.
    node_mass = torch.zeros(n, device='mps')
    node_mass.index_add_(0, indices.ravel(),
        (interpolation * (weights * gates.square())[:, None]).ravel())
    response_bound = mixing.abs().sum(dim=1).amax() * mixing.abs().sum(dim=2).amax()
    lipschitz = float((2 * (node_mass.max() * response_bound + 12 * penalty + ridge)).cpu())
    step = 1 / max(lipschitz, 1e-10)
    current = torch.zeros((n, 3), device='mps')
    extrapolated = current.clone()
    best = current.clone()
    best_loss = float(objective(current).cpu())
    before = best_loss
    last_check = best_loss
    momentum = 1.
    converged = False
    started = time.perf_counter()
    for iteration in range(iterations):
        value = extrapolated.detach().requires_grad_(True)
        loss = objective(value)
        gradient, = torch.autograd.grad(loss, value)
        with torch.no_grad():
            candidate = (value - step * gradient).clamp(-64 / 256, 63 / 256)
            new_momentum = (1 + np.sqrt(1 + 4 * momentum**2)) / 2
            extrapolated = candidate + (momentum - 1) / new_momentum * (candidate - current)
            current = candidate
            momentum = new_momentum
        if iteration % 25 == 24 or iteration == iterations - 1:
            score = float(objective(current).detach().cpu())
            if not np.isfinite(score):
                raise ValueError('Nonfinite Metal grid loss')
            if score < best_loss:
                best_loss = score
                best = current.clone()
            if score > last_check + max(1e-9, abs(last_check) * 1e-4):
                current = best.clone()
                extrapolated = current.clone()
                momentum = 1.
            elif iteration >= 124 and abs(score - last_check) <= max(1e-10, abs(last_check) * 1e-6):
                converged = True
                break
            last_check = score
    values = best.detach().cpu().numpy().astype(float)
    result = values if continuous else np.clip(np.rint(values * 256), -64, 63).astype(np.int8)
    return result, dict(backend='Apple Metal/MPS', solver='bounded FISTA; resident grid interpolation',
        iterations=iteration + 1, converged=converged, before=before, after=best_loss,
        seconds=time.perf_counter() - started, training_only=True, regularization=strength,
        shape=list(shape), clipping_in_objective=paired)
