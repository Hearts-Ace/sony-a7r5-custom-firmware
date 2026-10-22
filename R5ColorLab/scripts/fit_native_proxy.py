"""Offline S-Log3 cube -> native-shaped matrix + curve research fitter.

This is NOT the R5 pixel pipeline: exact CC1 pixel semantics, block13 hue /
illuminant selection, CP Gamma axes and ISP stage order remain unverified.
It cannot build/install firmware. Outputs .r5lookdev, rejected as live data.
Uses only numpy (workspace vendor/audit-python fallback).
"""
from pathlib import Path
import argparse
import hashlib
import json
import shlex
import sys

ROOT = Path(__file__).resolve().parents[3]
try:
    import numpy as np
except ImportError:
    import numpy as np

from look_recipe import encode, read

PRIMARIES = {
    'linear-bt709': ((.64, .33), (.30, .60), (.15, .06)),
    'sgamut3': ((.730, .280), (.140, .855), (.100, -.050)),
    'sgamut3cine': ((.766, .275), (.225, .800), (.089, -.087)),
}


def dot(a, b):
    # Explicit contraction avoids host Accelerate matmul status-flag warnings
    # observed even for finite, small values on this macOS/Numpy combination.
    # Do not silence floating-point warnings globally.
    return np.einsum('ij,jk->ik', a, b, optimize=False)


def rgb_to_xyz(primaries):
    xy = np.array(PRIMARIES[primaries])
    columns = np.stack([xy[:, 0]/xy[:, 1], np.ones(3),
                        (1-xy.sum(1))/xy[:, 1]])
    white = np.array([.3127/.3290, 1., (1-.3127-.3290)/.3290])
    return columns * np.linalg.solve(columns, white)[None, :]


def slog3(linear):
    """Sony S-Log3 code values /1023; scene 0.18 ->420/1023, 0 ->95/1023."""
    linear = np.asarray(linear, dtype=float)
    # Maximum only protects the unselected log branch from invalid values.
    logarithmic = (420 + 261.5*np.log10(np.maximum(linear+.01, 1e-20)/.19))/1023
    toe = (linear*(171.2102946929-95)/.01125 + 95)/1023
    return np.where(linear >= .01125, logarithmic, toe)


class Cube:
    """Strict standalone 3D cube, red fastest, trilinear interpolation."""
    def __init__(self, path):
        with Path(path).open('rb') as handle:
            raw = handle.read(64*1024*1024+1)
        if len(raw) > 64*1024*1024:
            raise ValueError('Cube exceeds 64 MiB')
        self.sha256 = hashlib.sha256(raw).hexdigest()
        size, values, seen = None, [], set()
        self.lo, self.hi = np.zeros(3), np.ones(3)
        for line in raw.decode('utf-8-sig').splitlines():
            parts = shlex.split(line, comments=True)
            if not parts:
                continue
            key = parts[0]
            if key in ('TITLE', 'LUT_3D_SIZE', 'DOMAIN_MIN', 'DOMAIN_MAX'):
                if key in seen or values:
                    raise ValueError('Duplicate or late cube header')
                seen.add(key)
                if key == 'TITLE':
                    if len(parts) != 2:
                        raise ValueError('Invalid TITLE')
                elif key == 'LUT_3D_SIZE':
                    if len(parts) != 2 or not 2 <= int(parts[1]) <= 65:
                        raise ValueError('Expected cube size 2..65')
                    size = int(parts[1])
                else:
                    if len(parts) != 4:
                        raise ValueError('Invalid cube domain')
                    setattr(self, 'lo' if key == 'DOMAIN_MIN' else 'hi',
                            np.array(parts[1:], dtype=float))
                continue
            if size is None or len(parts) != 3:
                raise ValueError('Only standalone 3D cube supported')
            values.append([float(v) for v in parts])
            if len(values) > size**3:
                raise ValueError('Extra cube rows')
        a = np.array(values, dtype=float)
        if (size is None or a.shape != (size**3, 3) or not np.isfinite(a).all()
                or not np.isfinite([self.lo, self.hi]).all()
                or np.any(self.hi <= self.lo)):
            raise ValueError('Invalid cube dimensions, numbers or domain')
        self.values = a.reshape(size, size, size, 3)
        self.size = size

    def sample(self, rgb):
        at = np.clip((rgb-self.lo)/(self.hi-self.lo), 0, 1)*(self.size-1)
        lo = np.minimum(np.floor(at).astype(int), self.size-2)
        f = at-lo
        result = np.zeros_like(at)
        for r in (0, 1):
            for g in (0, 1):
                for b in (0, 1):
                    weight = ((f[:, 0] if r else 1-f[:, 0])
                              * (f[:, 1] if g else 1-f[:, 1])
                              * (f[:, 2] if b else 1-f[:, 2]))
                    result += weight[:, None]*self.values[
                        lo[:, 2]+b, lo[:, 1]+g, lo[:, 0]+r]
        return result


class Reference:
    def __init__(self, cube, gamut):
        self.cube = cube
        self.transform = np.linalg.solve(rgb_to_xyz(gamut), rgb_to_xyz('linear-bt709'))

    def encoded(self, rgb):
        return slog3(dot(rgb, self.transform.T))

    def __call__(self, rgb):
        # Preserve cube outputs, including excursions. The proxy output is
        # bounded to 0..1, so any excursions remain an explicit fitting error.
        return self.cube.sample(self.encoded(rgb))


def matrix(q):
    a, b, c, d, e, f = np.asarray(q)/1024
    return np.array([[1+a+b, -a, -b], [-c, 1+c+d, -d], [-e, -f, 1+e+f]])


def predict(rgb, q, axis, curve):
    return np.interp(dot(rgb, matrix(q).T), axis, curve)


def isotonic(values, weights):
    blocks = []
    for i, (v, w) in enumerate(zip(values, weights)):
        blocks.append([i, i+1, float(v*w), float(w)])
        while len(blocks) > 1 and blocks[-2][2]/blocks[-2][3] > blocks[-1][2]/blocks[-1][3]:
            right, left = blocks.pop(), blocks.pop()
            blocks.append([left[0], right[1], left[2]+right[2], left[3]+right[3]])
    result = np.empty(len(values))
    for lo, hi, value, weight in blocks:
        result[lo:hi] = value/weight
    return np.clip(result, 0, 1)


def curve_fit(x, target, axis):
    x, y = np.clip(x.ravel(), axis[0], axis[-1]), target.ravel()
    lo = np.minimum(np.searchsorted(axis, x, side='right')-1, len(axis)-2)
    f = (x-axis[lo])/(axis[lo+1]-axis[lo])
    h, rhs = np.eye(len(axis))*.0001, np.zeros(len(axis))
    # Linear interpolation least squares, projected to a monotone curve.
    for a, wa in ((lo, 1-f), (lo+1, f)):
        np.add.at(rhs, a, wa*y)
        for b, wb in ((lo, 1-f), (lo+1, f)):
            np.add.at(h, (a, b), wa*wb)
    start = np.linalg.solve(h, rhs)
    result = isotonic(start, np.diag(h))
    # Projected gradient refines the weighted PAVA initial projection.
    step = 1/max(np.sum(np.abs(h), axis=1))
    for _ in range(80):
        new = isotonic(result-step*(np.einsum('ij,j->i', h, result)-rhs), np.ones(len(axis)))
        if np.max(np.abs(new-result)) < 1e-7:
            break
        result = new
    return result


def fit(rgb, target, scene_max, iterations=18):
    # Explicit research axis; not the undocumented native CP Gamma x grid.
    axis = np.linspace(0, 1, 129)**3*scene_max
    q, best, history = np.zeros(6), None, []
    for _ in range(iterations):
        mixed = dot(rgb, matrix(q).T)
        curve = curve_fit(mixed, target, axis)
        result = np.interp(mixed, axis, curve)
        loss = float(np.mean((result-target)**2))
        history.append(loss)
        if best is None or loss < best[0]:
            best = (loss, q.copy(), curve.copy())
        # Six neutral-preserving channel mixing variables, units Q10.
        jac = np.zeros((len(rgb), 3, 6))
        for ch, (j, k) in enumerate(((1, 2), (0, 2), (0, 1))):
            jac[:, ch, ch*2] = (rgb[:, ch]-rgb[:, j])/1024
            jac[:, ch, ch*2+1] = (rgb[:, ch]-rgb[:, k])/1024
        idx = np.clip(np.searchsorted(axis, mixed, side='right')-1, 0, 127)
        slope = (curve[idx+1]-curve[idx])/(axis[idx+1]-axis[idx])
        slope[(mixed <= axis[0]) | (mixed >= axis[-1])] = 0
        design = (jac*slope[:, :, None]).reshape(-1, 6)
        rhs = (target-result).ravel()
        delta = np.linalg.solve(dot(design.T, design)+np.eye(6)*1e-6,
                                np.einsum('ij,i->j', design, rhs))
        accepted = False
        for scale in (1., .5, .25, .125, .0625):
            candidate = np.clip(q+delta*scale, -4096, 4096)
            error = np.mean((predict(rgb, candidate, axis, curve)-target)**2)
            if error < loss:
                q, accepted = candidate, True
                break
        if not accepted or np.max(np.abs(delta))*scale < .1:
            break
    _, q, _ = best
    q = np.rint(q).astype(int)
    curve = curve_fit(dot(rgb, matrix(q).T), target, axis)
    return q, axis, curve, history


def samples(seed, count, scene_max):
    rng = np.random.default_rng(seed)
    # Explicit synthetic distribution, not a claim about scene frequencies.
    uniform = rng.uniform(0, scene_max, (count//2, 3))
    chroma = rng.uniform(0, 1, (count-count//2, 3))
    chroma /= np.maximum(chroma.max(1, keepdims=True), 1e-12)
    exposure = np.exp(rng.uniform(np.log(1e-4), np.log(scene_max), (len(chroma), 1)))
    return np.concatenate([uniform, chroma*exposure])


def metrics(actual, target):
    e = np.abs(actual-target)
    return dict(rgb_mae=float(e.mean()), rgb_rmse=float(np.sqrt(np.mean(e**2))),
                channel_abs_p95=float(np.quantile(e, .95)), max_channel_abs=float(e.max()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cube', type=Path)
    parser.add_argument('--input-gamut', choices=('sgamut3', 'sgamut3cine'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scene-max', type=float, default=4.)
    parser.add_argument('--count', type=int, default=8000)
    parser.add_argument('--seed', type=int, default=20261019)
    args = parser.parse_args()
    if not 1 <= args.scene_max <= 16 or not 1024 <= args.count <= 100000:
        parser.error('scene-max 1..16 and count 1024..100000 required')
    if args.output.suffix != '.r5lookdev':
        parser.error('Output must use .r5lookdev; not a native .LUT')
    if args.output.resolve() == args.cube.resolve():
        parser.error('Output must not overwrite input')
    report_path = args.output.with_suffix('.metrics.json')
    if args.output.exists() or report_path.exists():
        parser.error('Output or metrics already exists; choose a new output path')
    cube = Cube(args.cube)
    render = Reference(cube, args.input_gamut)
    training = samples(args.seed, args.count, args.scene_max)
    gray = np.repeat(np.geomspace(1e-5, args.scene_max, 513)[:, None], 3, axis=1)
    # Fixed gray emphasis in training; untouched random holdout is separate.
    training = np.concatenate([training, np.tile(gray, (3, 1))])
    target = render(training)
    q, axis, curve, history = fit(training, target, args.scene_max)
    metadata = dict(schema='r5-look-proxy/1', camera_apply_allowed=False,
        model='neutral-matrix-then-shared-curve-hypothesis',
        input_working_space='linear-bt709-D65-scene-relative',
        scene_max=args.scene_max, source_encoding='S-Log3-code-values-div1023',
        source_gamut=args.input_gamut, source_file=args.cube.name,
        source_sha256=cube.sha256, source_cube_size=cube.size,
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        codec_sha256=hashlib.sha256(Path(__file__).with_name('look_recipe.py').read_bytes()).hexdigest(),
        numpy_version=np.__version__,
        target_encoding='cube-output-as-authored-no-assumed-display-gamma',
        cube_interpolation='trilinear-domain-clamp',
        cc1_policy='preserve-not-fitted',
        block13_policy='single-neutral-preserving-six-coefficient-proxy-only',
        curve_encoding='explicit-float-axis-NOT-CP-gamma',
        missing_native_model=['CC1-pixel-equations', 'block13-sector-and-B-A1-A2-selection',
            'CP-Gamma-axis-scale-tail', 'ISP-stage-order-and-clipping', 'per-body-calibration'])
    raw = encode(metadata, q.tolist(), axis.tolist(), curve.tolist())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create prevents accidental overwrite of an earlier result.
    with args.output.open('xb') as handle:
        handle.write(raw)
    decoded = read(args.output)
    holdout = samples(args.seed+1, 4096, args.scene_max)
    expected = render(holdout)
    fitted = predict(holdout, decoded['q'], decoded['axis'], decoded['curve'])
    baseline_curve = curve_fit(training, target, axis)
    no_matrix = predict(holdout, np.zeros(6), axis, baseline_curve)
    encoded_input = render.encoded(holdout)
    report = dict(schema='r5-look-proxy-fit-report/1', camera_io=False,
        camera_apply_allowed=False, source_sha256=cube.sha256,
        recipe_sha256=decoded['sha256'], recipe_bytes=len(raw),
        model=metadata, matrix_q10=decoded['q'], matrix=matrix(decoded['q']).tolist(),
        seed=args.seed, training_count=len(training), holdout_count=len(holdout),
        training_mse_by_iteration=history,
        synthetic_holdout=metrics(fitted, expected),
        shared_curve_only_baseline=metrics(no_matrix, expected),
        neutral_ramp=metrics(predict(gray, decoded['q'], decoded['axis'], decoded['curve']), render(gray)),
        outside_cube_input_domain_sample_fraction=float(np.mean(np.any(
            (encoded_input < cube.lo) | (encoded_input > cube.hi), axis=1))),
        target_outside_0_1_channel_fraction=float(np.mean((expected < 0) | (expected > 1))),
        limits=['Synthetic linear-BT709 input, NOT native R5 input or ST inversion.',
            'Global matrix/curve proxy, NOT complete CC1/block13/Gamma fitting.',
            'No native gamma serialization, SD camera loader or on-camera equivalence.',
            'RGB-domain errors only; no assumed Rec.709 display EOTF or camera DeltaE.'])
    with report_path.open('x', encoding='utf8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps({k: report[k] for k in ('recipe_bytes', 'matrix_q10',
        'synthetic_holdout', 'shared_curve_only_baseline', 'camera_apply_allowed')}, indent=2))


if __name__ == '__main__':
    main()
