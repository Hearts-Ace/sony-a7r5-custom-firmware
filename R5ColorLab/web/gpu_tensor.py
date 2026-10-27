"""Shared Metal tensor interpolation and continuous display color losses."""
import numpy as np
from apple_gpu import SmoothGPU


class TensorTools:
    interp = SmoothGPU.interp
    lab = SmoothGPU.lab

    def __init__(self, device='mps', dtype=None):
        import torch
        self.torch = torch
        self.device = device
        self.dtype = torch.float32 if dtype is None else dtype

    def tensor(self, values, integer=False):
        return self.torch.as_tensor(np.array(values, copy=True), device=self.device,
            dtype=self.torch.int64 if integer else self.dtype)


def stencil_tensor(tools, coordinates, shape=(5, 9, 9)):
    torch = tools.torch
    shape = np.asarray(shape)
    position = (coordinates + tools.tensor([0, .5, .5])) * tools.tensor(shape - 1)
    position = torch.minimum(position.clamp(min=0), tools.tensor(shape - 1))
    low = torch.minimum(position.long(), tools.tensor(shape - 2, True))
    f = position - low
    indices, weights = [], []
    for y in (0, 1):
        for u in (0, 1):
            for v in (0, 1):
                indices.append(((low[:, 0] + y) * int(shape[1]) + low[:, 1] + u) * int(shape[2]) + low[:, 2] + v)
                weights.append((f[:, 0] if y else 1 - f[:, 0]) *
                    (f[:, 1] if u else 1 - f[:, 1]) * (f[:, 2] if v else 1 - f[:, 2]))
    return torch.stack(indices, dim=1), torch.stack(weights, dim=1)


def provisional_coordinates(tools, rgb):
    matrix = tools.tensor([[.299, .587, .114],
        [-.299 / (2 * .886), -.587 / (2 * .886), .5],
        [.5, -.587 / (2 * .701), -.114 / (2 * .701)]])
    return (rgb @ matrix.T - tools.tensor([16 / 255, 0, 0])) * tools.tensor([255 / 219, 255 / 224, 255 / 224])


def de2000_tensor(tools, first, second):
    t = tools.torch
    l1, a1, b1 = first.unbind(1)
    l2, a2, b2 = second.unbind(1)
    c1, c2 = t.hypot(a1, b1), t.hypot(a2, b2)
    cm = (c1 + c2) / 2
    g = .5 * (1 - t.sqrt(cm**7 / (cm**7 + 25**7)))
    ap1, ap2 = (1 + g) * a1, (1 + g) * a2
    cp1, cp2 = t.hypot(ap1, b1), t.hypot(ap2, b2)
    hp1 = t.remainder(t.atan2(b1, ap1) * (180 / np.pi), 360)
    hp2 = t.remainder(t.atan2(b2, ap2) * (180 / np.pi), 360)
    hp1, hp2 = t.where(cp1 == 0, 0, hp1), t.where(cp2 == 0, 0, hp2)
    dl, dc = l2 - l1, cp2 - cp1
    dh = hp2 - hp1
    dh = t.where(cp1 * cp2 == 0, 0, t.where(dh > 180, dh - 360, t.where(dh < -180, dh + 360, dh)))
    d_h = 2 * t.sqrt(cp1 * cp2) * t.sin(dh * (np.pi / 360))
    lm, cm = (l1 + l2) / 2, (cp1 + cp2) / 2
    hm = t.where(cp1 * cp2 == 0, hp1 + hp2,
        t.where(t.abs(hp1 - hp2) <= 180, (hp1 + hp2) / 2,
            t.where(hp1 + hp2 < 360, (hp1 + hp2 + 360) / 2, (hp1 + hp2 - 360) / 2)))
    radians = np.pi / 180
    term = 1 - .17 * t.cos((hm - 30) * radians) + .24 * t.cos(2 * hm * radians)
    term = term + .32 * t.cos((3 * hm + 6) * radians) - .20 * t.cos((4 * hm - 63) * radians)
    sl = 1 + .015 * (lm - 50)**2 / t.sqrt(20 + (lm - 50)**2)
    sc, sh = 1 + .045 * cm, 1 + .015 * cm * term
    rt = -2 * t.sqrt(cm**7 / (cm**7 + 25**7)) * t.sin(60 * t.exp(-((hm - 275) / 25)**2) * radians)
    return t.sqrt(((dl / sl)**2 + (dc / sc)**2 + (d_h / sh)**2 + rt * (dc / sc) * (d_h / sh)).clamp(min=0))
