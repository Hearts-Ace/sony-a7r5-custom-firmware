"""GPU frozen-PC rendering, paired R5 response and floating color metrics."""
import numpy as np
from gpu_tensor import TensorTools, stencil_tensor, provisional_coordinates, de2000_tensor
from gpu_alternation import BlockObjective


class FrozenPC:
    def __init__(self, curve, grid, device='mps', dtype=None):
        self.gpu = TensorTools(device, dtype)
        self.torch = self.gpu.torch
        tensor = self.gpu.tensor
        self.mode = curve.get('mode', 'tone-tint')
        self.response = curve.get('response')
        self.grid = tensor(np.asarray(grid).reshape(405, 3) / 256)
        self.luma = tensor([.2126, .7152, .0722])
        self.coordinate_matrix = tensor([[.299, .587, .114],
            [-.299 / (2 * .886), -.587 / (2 * .886), .5],
            [.5, -.587 / (2 * .701), -.114 / (2 * .701)]])
        if self.mode != 'qaq-grid':
            self.curve = {key: tensor(curve[key]) for key in ('axis', 'tone', 'tint', 'gray_axis', 'gray_chroma')}
            self.curve.update(radius=curve['gray_protection_radius'], transition=curve['gray_transition'], mode=self.mode)
            if self.mode == 'rgb-independent':
                self.curve['rgb'] = tensor(curve['rgb'])

    def corrected(self, rgb):
        if self.mode == 'qaq-grid':
            if isinstance(self.response, dict):
                return paired_tensor(self.gpu, rgb, self.grid * 256, self.response)
            indices, weights = stencil_tensor(self.gpu, provisional_coordinates(self.gpu, rgb))
            delta = (self.grid[indices] * weights[:, :, None]).sum(dim=1)
            return (rgb + delta @ self.gpu.tensor(self.response)).clamp(0, 1)
        return BlockObjective.corrected(self, rgb)


def paired_tensor(tools, rgb, grid, response):
    from measured_response import get
    model = get(response)
    if not hasattr(model, 'affine'):
        raise ValueError('GPU paired renderer requires the R5 affine response snapshot')
    affine = tools.tensor(model.affine)
    coordinates = rgb @ affine[:, :3].T + affine[:, 3]
    indices, weights = stencil_tensor(tools, coordinates)
    delta = (grid[indices] * weights[:, :, None]).sum(dim=1)
    matrix = tools.tensor(model.weights[:3]).expand(len(rgb), 3, 3)
    if model.smooth:
        matrix = matrix + tools.torch.einsum('nj,cjo->nco', rgb - .5,
            tools.tensor(model.weights[3:].reshape(3, 3, 3)))
    return (rgb + tools.torch.einsum('nc,nco->no', delta, matrix / 256)).clamp(0, 1)


def paired_numpy(rgb, grid, response, exact_display=False):
    tools = TensorTools()
    original = np.asarray(rgb)
    output = paired_tensor(tools, tools.tensor(original), tools.tensor(grid), response).detach().cpu().numpy().astype(float)
    if exact_display:
        # Only pixels close enough to an 8-bit rounding boundary need a float64
        # response recheck; native integer rendering itself is bit-exact.
        code = np.clip(output, 0, 1) * 255 + .5
        boundary = np.any(np.abs(code - np.rint(code)) < .002, axis=1)
        if np.any(boundary):
            from measured_response import get
            output[boundary] = get(response).predict_cpu(original[boundary], grid)
    return output


def pc_numpy(rgb, curve, grid):
    engine = FrozenPC(curve, grid)
    return engine.corrected(engine.gpu.tensor(rgb)).detach().cpu().numpy().astype(float)


def display_cost_rows(predicted, target, perceptual_weight):
    tools = TensorTools()
    p, t = [tools.tensor(value).clamp(0, 1) for value in (predicted, target)]
    rows = (p - t).square().mean(dim=1) * 255**2
    if perceptual_weight:
        delta = de2000_tensor(tools, tools.lab(p), tools.lab(t))
        rows = rows + perceptual_weight * (2.55 * delta).square()
    return rows.detach().cpu().numpy().astype(float)
