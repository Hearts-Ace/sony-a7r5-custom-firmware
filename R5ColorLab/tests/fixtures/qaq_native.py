"""Native-shaped 5x9x9 signed correction fit.

Packing shape/range follows instruction tests. Pixel coordinates and response
are a separately supplied, explicitly provisional model of the ISP.
"""
import itertools
import numpy as np
from .color import rows

NODES = 405
RAW_BYTES = 1215


def coordinates(rgb):
    kr, kb = .299, .114
    kg = 1-kr-kb
    matrix = np.array([[kr,kg,kb],[-kr/(2*(1-kb)),-kg/(2*(1-kb)),.5],[.5,-kg/(2*(1-kr)),-kb/(2*(1-kr))]])
    return (rows(rgb)@matrix.T-[16/255,0,0])*255/np.array([219,224,224])


def interpolation(rgb):
    at = np.clip(coordinates(rgb)*[4,8,8]+[0,4,4], [0,0,0], [4,8,8])
    lo = np.minimum(at.astype(int), [3,7,7])
    f = at-lo
    ids, weights = [], []
    for dy,dc1,dc2 in itertools.product((0,1),repeat=3):
        ids.append((lo[:,0]+dy)*81+(lo[:,1]+dc1)*9+lo[:,2]+dc2)
        weights.append(np.prod(np.where([dy,dc1,dc2], f, 1-f),axis=1))
    return np.stack(ids,axis=1), np.stack(weights,axis=1)


def validate_response(response):
    response = np.asarray(response,dtype=float)
    if response.shape != (3,3) or not np.isfinite(response).all() or np.linalg.cond(response) > 30:
        raise ValueError("Finite, invertible and well-conditioned 3x3 ISP response required")
    return response


def predict(source, coefficients, response):
    ids, weights = interpolation(source)
    delta = np.sum(np.asarray(coefficients)[ids]*weights[:,:,None],axis=1)/256
    return np.clip(rows(source)+delta@validate_response(response),0,1)


def encode(coefficients):
    a = np.asarray(coefficients)
    if a.shape != (405,3) or not np.isfinite(a).all() or np.any(a != np.rint(a)) or np.any((a < -64)|(a > 63)):
        raise ValueError("Expected 405x3 signed 7-bit integer corrections")
    return a.astype("i1").T.copy().tobytes()


def decode(raw):
    if len(raw) != RAW_BYTES:
        raise ValueError("Expected three 405-byte correction planes")
    result = np.frombuffer(raw,dtype="i1").reshape(3,405).T.astype(int)
    encode(result)  # also reject signed values outside the 7-bit range
    return result


def equations(source, target, response):
    source, target = rows(source), rows(target)
    if source.shape != target.shape or np.any((source < 0)|(source > 1)) or np.any((target < 0)|(target > 1)):
        raise ValueError("Matching 0..1 source/target RGB arrays required")
    ids, weights = interpolation(source)
    delta = (target-source)@np.linalg.inv(validate_response(response))*256
    h, rhs = np.zeros((405,405)), np.zeros((405,3))
    for i in range(8):
        np.add.at(rhs,ids[:,i],weights[:,i,None]*delta)
        for j in range(8):
            np.add.at(h,(ids[:,i],ids[:,j]),weights[:,i]*weights[:,j])
    return h,rhs


def smoothness():
    h = np.zeros((405,405))
    for y,c1,c2 in itertools.product(range(5),range(9),range(9)):
        i = y*81+c1*9+c2
        for condition,j in ((y<4,i+81),(c1<8,i+9),(c2<8,i+1)):
            if condition:
                h[i,i] += 1
                h[j,j] += 1
                h[i,j] -= 1
                h[j,i] -= 1
    return h


def constrained_fit(h, rhs, strength):
    if not np.isfinite(strength) or strength <= 0:
        raise ValueError("Positive finite smoothness required")
    a = h+strength*smoothness()+np.eye(405)*.001
    x = np.clip(np.linalg.solve(a,rhs),-64,63)
    residual = rhs-a@x
    update = float("inf")
    for epoch in range(300):
        update = 0.
        for i in range(405):
            dx = np.clip(x[i]+residual[i]/a[i,i],-64,63)-x[i]
            update = max(update,float(np.max(np.abs(dx))))
            x[i] += dx
            residual -= a[:,i,None]*dx[None,:]
        if update < .0001:
            break
    return np.rint(x).astype(int), {"epochs":epoch+1,"max_coordinate_update":update,"converged":update < .0001}


def metrics(actual, expected):
    e = np.abs(rows(actual)-rows(expected))
    return {"rgb_mae":float(e.mean()),"abs_rgb_p95":float(np.quantile(e,.95)),"max_channel_error":float(e.max())}


def fit_reference(render, response, *, seed=201, count=12000, strengths=(.1,1.,10.)):
    if count < 512:
        raise ValueError("At least 512 training samples required")
    rng = np.random.default_rng(seed)
    gray = np.repeat(np.linspace(.01,.99,512)[:,None],3,axis=1)
    training = np.concatenate([rng.uniform(.015,.985,(count,3)),np.tile(gray,(4,1))])
    validation = rng.uniform(.015,.985,(2048,3))
    testing = rng.uniform(.015,.985,(4096,3))
    h,rhs = equations(training,render(training),response)
    target = render(validation)
    trials = []
    for strength in strengths:
        coefficients, convergence = constrained_fit(h,rhs,strength)
        score = metrics(predict(validation,coefficients,response),target)
        trials.append((score["rgb_mae"],strength,coefficients,convergence))
    _, strength, coefficients, convergence = min(trials,key=lambda item:item[0])
    test_target = render(testing)
    predicted = predict(testing,coefficients,response)
    result = {"seed":seed,"counts":{"train":len(training),"selection":len(validation),"test":len(testing)},
              "selected_smoothness":strength,"convergence":convergence,"synthetic_holdout":metrics(predicted,test_target),
              "no_effect_baseline":metrics(testing,test_target),"bounded_coefficients":int(np.count_nonzero((coefficients == -64)|(coefficients == 63))),
              "coefficient_min":int(coefficients.min()),"coefficient_max":int(coefficients.max()),
              "actual_camera_accuracy_verified":False,"pixel_model":"BT.601 limited-range coordinate hypothesis + supplied 3x3 ISP response"}
    return encode(coefficients), result
