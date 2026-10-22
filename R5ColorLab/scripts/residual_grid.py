"""PC residual fitter; grid packing does NOT establish camera pixel semantics.

5x9x9 topology and 7-bit limits follow the upstream research format. Coordinates
and response here are an explicit provisional PC model, not recovered R5 ISP
equations. Standard trilinear interpolation and bounded least squares are
implemented independently. See README section 11 for upstream attribution.
"""
from edit_native_model import np

SHAPE = (5, 9, 9)
NODES = 405


def coordinates(rgb):
    """Provisional BT.601 limited-range coordinates, RGB code values in [0,1].

    Matches the explicitly provisional coordinate contract in the archived
    a7c2 looktool; it is not an sRGB/Rec.709 transfer-function conversion.
    """
    a = np.asarray(rgb, dtype=float)
    if a.ndim != 2 or a.shape[1] != 3 or not np.all(np.isfinite(a)):
        raise ValueError('Expected finite Nx3 RGB')
    matrix = np.array([[.299, .587, .114],
        [-.299/(2*.886), -.587/(2*.886), .5],
        [.5, -.587/(2*.701), -.114/(2*.701)]])
    ycc = np.einsum('ij,kj->ik', a, matrix, optimize=False)
    ycc[:, 0] -= 16/255
    return ycc*255/np.array([219, 224, 224])


def stencil(coords):
    c = np.asarray(coords, dtype=float)
    if c.ndim != 2 or c.shape[1] != 3 or not np.all(np.isfinite(c)):
        raise ValueError('Expected finite Nx3 grid coordinates')
    at = np.clip(c*np.array([4, 8, 8])+np.array([0, 4, 4]), 0, np.array(SHAPE)-1)
    low = np.minimum(np.floor(at).astype(int), np.array(SHAPE)-2)
    f = at-low
    indices, weights = [], []
    for y in (0, 1):
        for u in (0, 1):
            for v in (0, 1):
                indices.append((low[:, 0]+y)*81+(low[:, 1]+u)*9+low[:, 2]+v)
                weights.append((f[:, 0] if y else 1-f[:, 0])
                    *(f[:, 1] if u else 1-f[:, 1])*(f[:, 2] if v else 1-f[:, 2]))
    return np.stack(indices, axis=1), np.stack(weights, axis=1)


def response_matrix(value):
    if isinstance(value, dict):
        from measured_response import require
        return require(value)
    r = np.asarray(value, dtype=float)
    if r.shape != (3, 3) or not np.all(np.isfinite(r)) or np.linalg.cond(r) >= 30:
        raise ValueError('Explicit finite nonsingular 3x3 response, condition <30 required')
    return r


def coefficients(value):
    c = np.asarray(value)
    if (c.shape != (NODES, 3) or not np.all(np.isfinite(c))
            or np.any(c != np.trunc(c)) or np.any(c < -64) or np.any(c > 63)):
        raise ValueError('Expected 405x3 signed 7-bit integer coefficients')
    return c.astype(np.int8)


def evaluate(base, grid, response, coords=None, clip=True):
    if isinstance(response, dict):
        from measured_response import get
        if coords is not None:raise ValueError('Measured response owns its coordinates')
        return get(response).predict(base, coefficients(grid), clip=clip)
    b = np.asarray(base, dtype=float)
    ids, w = stencil(coordinates(b) if coords is None else coords)
    if b.shape != (len(ids), 3) or not np.all(np.isfinite(b)):
        raise ValueError('Expected finite base RGB matching coordinates')
    c = coefficients(grid).astype(float)/256
    delta = np.einsum('ij,ijk->ik', w, c[ids], optimize=False)
    result = b+np.einsum('ij,kj->ik', delta, response_matrix(response), optimize=False)
    return np.clip(result, 0, 1) if clip else result


def laplacian():
    result = np.zeros((NODES, NODES))
    for y in range(5):
        for u in range(9):
            for v in range(9):
                a = y*81+u*9+v
                for condition, step in [(y < 4, 81), (u < 8, 9), (v < 8, 1)]:
                    if not condition: continue
                    b = a+step
                    result[a, a] += 1; result[b, b] += 1
                    result[a, b] -= 1; result[b, a] -= 1
    return result


def fit(base, target, response, strength=.01, coords=None, iterations=1000):
    """Bounded projected least squares, then 7-bit quantization.

    Smoothness is per neighboring coefficient. All matrices remain explicit;
    evaluate() is the only prediction path. Target excursions are retained as
    errors. No training/validation/test pooling occurs here.
    """
    b, t = np.asarray(base, dtype=float), np.asarray(target, dtype=float)
    if (b.ndim != 2 or b.shape[1] != 3 or t.shape != b.shape or len(b) < 2
            or not np.all(np.isfinite([b, t])) or strength < 0):
        raise ValueError('Finite matching Nx3 samples and nonnegative strength required')
    r = response_matrix(response)
    ids, w = stencil(coordinates(b) if coords is None else coords)
    if len(ids) != len(b): raise ValueError('Coordinate count differs')
    h = np.zeros((NODES, NODES)); rhs = np.zeros((NODES, 3))
    for i in range(8):
        np.add.at(rhs, ids[:, i], w[:, i, None]*(t-b))
        for j in range(8): np.add.at(h, (ids[:, i], ids[:, j]), w[:, i]*w[:, j])
    # Normalize data by sample count; regularization is independent of batch size.
    h /= len(b); rhs /= len(b)
    smooth = laplacian()*strength/NODES+np.eye(NODES)*1e-9
    rr = np.einsum('ki,kj->ij', r, r, optimize=False)
    desired = np.einsum('ij,jk->ik', rhs, r, optimize=False)
    lipschitz = np.max(np.sum(np.abs(h), axis=1))*np.max(np.linalg.eigvalsh(rr))
    lipschitz += np.max(np.sum(np.abs(smooth), axis=1))
    x = np.zeros((NODES, 3)); z = x.copy(); momentum = 1.
    for step in range(iterations):
        hx = np.einsum('ij,jk->ik', h, z, optimize=False)
        gradient = np.einsum('ij,jk->ik', hx, rr, optimize=False)-desired
        gradient += np.einsum('ij,jk->ik', smooth, z, optimize=False)
        candidate = np.clip(z-gradient/lipschitz, -64/256, 63/256)
        next_momentum = (1+np.sqrt(1+4*momentum**2))/2
        z = candidate+(momentum-1)/next_momentum*(candidate-x)
        change = np.max(np.abs(candidate-x)); x = candidate; momentum = next_momentum
        if change < 1e-7: break
    quantized = np.clip(np.rint(x*256), -64, 63).astype(np.int8)
    return quantized, dict(iterations=step+1, regularization=float(strength),
        converged=bool(change < 1e-7), max_coefficient_step=float(change*256),
        iteration_limit=int(iterations),
        coefficient_min=int(quantized.min()), coefficient_max=int(quantized.max()),
        limit_fraction=float(np.mean((quantized == -64) | (quantized == 63))),
        coordinate_model='provisional-bt601-limited' if coords is None else 'explicit-supplied',
        response=r.tolist(), objective='pre-output-clip-RGB-MSE-plus-neighbor-smoothness')


def pack(grid):
    """1215 bytes, channel planes; range checked, never an installable file."""
    return coefficients(grid).T.copy().tobytes()


def unpack(data):
    if len(data) != 1215: raise ValueError('Expected 1215 bytes')
    return coefficients(np.frombuffer(data, dtype=np.int8).reshape(3, NODES).T).copy()


def collision_bound(base, target, bits=14):
    """MSE lower bound for any deterministic post-native correction.

    Quantized equal base colors are indistinguishable. This is exact only for
    the chosen quantization and sample set, not an unseen-scene guarantee.
    """
    b, t = np.asarray(base), np.asarray(target)
    if b.shape != t.shape or b.ndim != 2 or b.shape[1] != 3 or not np.all(np.isfinite([b, t])):
        raise ValueError('Finite matching Nx3 arrays required')
    if not 1 <= bits <= 16: raise ValueError('Expected 1..16 bits')
    _, inverse, counts = np.unique(np.rint(np.clip(b, 0, 1)*(2**bits-1)).astype(int),
        axis=0, return_inverse=True, return_counts=True)
    sums = np.zeros((len(counts), 3)); np.add.at(sums, inverse, t)
    mean = sums/counts[:, None]
    return dict(bits=bits, collision_sample_fraction=float(np.mean(counts[inverse] > 1)),
        irreducible_sample_mse=float(np.mean((t-mean[inverse])**2)))


def response_json(value):
    result=response_matrix(value)
    return result if isinstance(result,dict) else result.tolist()
