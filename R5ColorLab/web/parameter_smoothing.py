"""Train-time parameter regularization, never a spatial image blur."""
import numpy as np

def strength(value):
    if type(value) not in (int,float) or not np.isfinite(value) or not 0 <= value <= 100:
        raise ValueError('参数平滑强度需在0–100之间')
    return float(value)

def multiplier(value):
    return 1 + strength(value)/5

def native_rows(coefficients, gamma, axis, value):
    """Normalized residuals: periodic hue curvature and nonuniform Gamma slope changes.

    Zero disables the NEW penalty; historical matrix prior stays in the fitter.
    Correct for unequal abscissa spacing so a straight response has zero cost.
    """
    amount=strength(value)/100
    c=np.asarray(coefficients,dtype=float).reshape(6,16)
    y=np.asarray(gamma,dtype=float)/262143
    x=np.asarray(axis,dtype=float)/float(np.asarray(axis)[-1])
    dx=np.diff(x)
    if np.any(dx<=0) or len(x)!=len(y):raise ValueError('Invalid Gamma axes')
    curvature=np.diff(np.diff(y)/dx)*(dx[:-1]+dx[1:])/2
    hue=np.roll(c,1,axis=1)-2*c+np.roll(c,-1,axis=1)
    # Equal total mass per parameter family, independent of node count.
    return np.r_[hue.ravel()*.02/np.sqrt(hue.size),curvature*16/np.sqrt(len(curvature))]*np.sqrt(amount)

def native_cost(parameters, axis, value):
    if not strength(value):return 0.0
    from edit_native_model import decode_matrix16
    import struct
    c=np.array(struct.unpack_from('<96f',decode_matrix16(parameters['matrix_payload']),0x28))
    rows=native_rows(c,parameters['gamma_y'],axis,value)
    return float(rows@rows*255**2)


def grid_cost(grid,value):
    amount=strength(value)
    if not amount:return 0.0
    g=np.asarray(grid,dtype=float).reshape(5,9,9,3)/256
    total=sum(float(np.sum(np.diff(g,axis=d)**2))for d in range(3))
    return total*(.01*multiplier(amount))*255**2/(405*3)


def pc_cost(bundle,value):
    if bundle is None or not strength(value):return 0.0
    curve,grid=bundle[:2]
    cost=grid_cost(grid,value)
    if curve.get('mode','tone-tint')=='tone-tint':
        for key in ('tone','tint'):
            d2=np.diff(np.asarray(curve[key]),n=2,axis=0)
            cost+=float(np.sum(d2*d2))*.002*multiplier(value)*255**2/3
    return cost
