"""Integer color rendering through Metal; verified against CPU on each model."""
from functools import lru_cache
from pathlib import Path
import struct
import weakref
import numpy as np

MODELS = weakref.WeakKeyDictionary()


@lru_cache(maxsize=1)
def library():
    import torch
    return torch.mps.compile_shader(Path(__file__).with_name('native_color.metal').read_text())


class NativeGPU:
    def __init__(self, model):
        import torch
        from edit_color_pipeline import static_table
        self.torch = torch
        self.model = weakref.proxy(model)
        self.verified = False
        def tensor(array, dtype=torch.float32):
            return torch.as_tensor(np.array(array, copy=True), dtype=dtype, device='mps')
        self.tensor = tensor
        self.matrix = tensor(model.matrix_table.ravel())
        self.gamma = tensor(np.frombuffer(model.runtime, '<u2', 65536, 0x18f6), torch.int32)
        self.ygamma = tensor(np.frombuffer(model.runtime, '<u2', 32768, 0x318fc), torch.int32)
        self.angles = tensor(static_table(0x100237e00, 512, '<f4'))
        config = model.config
        ip = np.zeros(27, dtype=np.int32)
        ip[:5] = [struct.unpack_from('<H', config, offset)[0] for offset in (0x220, 0x222, 0, 2, 4)]
        ip[5] = bool(struct.unpack_from('<i', model.settings, 0x248)[0])
        ip[6] = model.area_controls is not None
        ip[7] = model.area_controls[64] if model.area_controls else 0
        controls = model.chroma_controls()
        ip[8:12] = [controls[key] for key in ('low_cutoff', 'high_cutoff', 'low_slope', 'high_slope')]
        cc1 = model.coefficients()
        mixed = (cc1[:4] & 65535) >> 2 & 511
        ip[16:20] = np.where(mixed > 255, mixed - 512, mixed)
        ip[20:24] = ((cc1[4:] & 65535) >> 3) & 255
        ip[24:27] = struct.unpack_from('<3h', model.runtime, 0x218f6)
        fp = np.zeros(24, dtype=np.float32)
        fp[:3] = struct.unpack_from('<3f', config, 0x214)
        level = int(struct.unpack_from('<h', model.settings, 0x2ac)[0] / 4)
        white = struct.unpack_from('<h', model.settings, 0x2b0)[0]
        fp[3] = np.float32(-level) * np.float32(63.998047)
        fp[4] = model._h(0x91962)
        fp[5] = model._f(0x91964)
        fp[6] = np.float32(1) / np.float32(512 - white + level)
        if model.area_controls:
            fp[8:] = np.frombuffer(model.area_controls[:64], '<f4')
        self.ip = tensor(ip, torch.int32)
        self.fp = tensor(fp)

    def render_tensor(self, values):
        torch = self.torch
        if isinstance(values, np.ndarray):
            if values.ndim != 3 or values.shape[2] != 3 or values.shape[1] < 5:
                raise ValueError('GPU native renderer expects HxWx3, width >=5')
            source = self.tensor(values, torch.int32)
        else:
            source = values
        count = source.numel() // 3
        output = torch.empty_like(source)
        library().native_color(source, output, self.matrix, self.gamma, self.ygamma,
            self.angles, self.ip, self.fp, count, source.shape[-2], threads=count)
        return output

    def verify(self, values):
        if self.verified:
            return
        a = np.asarray(values)
        indices = np.linspace(0, a.shape[0] * a.shape[1] - 1, min(128, a.shape[0] * a.shape[1]), dtype=int)
        rows, columns = indices // a.shape[1], indices % a.shape[1]
        probes = a[rows[:, None], np.clip(columns[:, None] + np.arange(-2, 3), 0, a.shape[1] - 1)]
        expected = self.model.color_only(probes)[:, 2]
        actual = self.render_tensor(probes).cpu().numpy()[:, 2]
        if not np.array_equal(expected, actual):
            raise ValueError(f'Metal integer verification failed: {np.count_nonzero(expected != actual)} channels')
        self.verified = True

    def render(self, values):
        self.verify(values)
        return self.render_tensor(values).cpu().numpy().astype('<u2')


def renderer(model):
    if model not in MODELS:
        MODELS[model] = NativeGPU(model)
    return MODELS[model]
