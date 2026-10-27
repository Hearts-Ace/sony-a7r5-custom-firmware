"""Pinned R5 paired-capture response; linear in table coefficients at fixed RGB."""
import numpy as np
from scipy import sparse
from scipy.optimize import least_squares

class PairedModel:
    def __init__(self,value,digest):
        self.value=dict(value,metadata=dict(model='ILCE-7RM5',physical_scope=value.get('scope','paired image capture')))
        self.sha256=digest;self.proxy=False
        self.affine=np.asarray(value['coordinate_affine'],float)
        self.weights=np.asarray(value['response_weights'],float)
        self.smooth=value['smooth'];self.validation=value['report']
        if self.affine.shape!=(3,4) or self.weights.shape!=((12,3) if self.smooth else (3,3)) or not np.isfinite(self.affine).all() or not np.isfinite(self.weights).all():raise ValueError('Invalid paired response model')
    def coordinates(self,rgb):
        return np.asarray(rgb)@self.affine[:,:3].T+self.affine[:,3]
    def stencil(self,rgb):
        from residual_grid import stencil
        c=self.coordinates(rgb);ids,w=stencil(c);return c,ids,w
    def response(self,rgb):
        x=np.asarray(rgb,float)
        r=np.broadcast_to(self.weights[:3],(len(x),3,3)).copy()
        if self.smooth:r+=np.einsum('nj,cjo->nco',x-.5,self.weights[3:].reshape(3,3,3))
        return r/256
    def predict(self,rgb,table,clip=True):
        from gpu_runtime import available
        if available() and clip and len(rgb)>=512:
            from gpu_color import paired_numpy
            from measured_response import default_response,previous_r5_response
            identity=default_response() if self.sha256==default_response()['sha256'] else previous_r5_response()
            return paired_numpy(rgb,table,identity)
        return self.predict_cpu(rgb,table,clip)
    def predict_cpu(self,rgb,table,clip=True):
        x=np.asarray(rgb,float);_,ids,w=self.stencil(x)
        d=(np.asarray(table)[ids]*w[...,None]).sum(1)
        out=x+np.einsum('nc,nco->no',d,self.response(x))
        return np.clip(out,0,1) if clip else out
    def probes(self,count,seed=20261022):
        # Compression also needs extrapolation colors: explicitly not additional camera evidence.
        return np.random.default_rng(seed).uniform(.015,.985,(count,3))
    def fit(self,base,target,weights,strength=.01):
        from gpu_runtime import available
        if available():
            from gpu_grid import fit
            from measured_response import default_response,previous_r5_response
            identity=default_response() if self.sha256==default_response()['sha256'] else previous_r5_response()
            result,audit=fit(base,target,weights,strength,response=identity)
            audit.update(model_sha256=self.sha256,physical_scope=self.value['metadata']['physical_scope'],
                calibration_validation=self.validation,new_scene_camera_verified=False)
            return result,audit
        from pc_stages import neighbor_design
        x=np.asarray(base,float);target=np.asarray(target,float);weights=np.asarray(weights,float)
        if x.shape!=target.shape or weights.shape!=(len(x),) or np.any(weights<=0):raise ValueError('Invalid paired training samples')
        _,ids,w=self.stencil(x);r=self.response(x);mass=np.sqrt(weights/weights.sum())
        rows=[];cols=[];data=[]
        for c in range(3):
            for o in range(3):
                rows.append(np.repeat(np.arange(len(x))*3+o,8));cols.append((ids*3+c).ravel())
                data.append((w*r[:,c,o,None]*mass[:,None]).ravel())
        design=sparse.coo_matrix((np.concatenate(data),(np.concatenate(rows),np.concatenate(cols))),shape=(len(x)*3,1215)).tocsr()
        regularizer=sparse.kron(neighbor_design((5,9,9)),sparse.eye(3),format='csr')*np.sqrt(strength/405)/256
        def loss(v):
            raw=x+(design@v).reshape(-1,3)/mass[:,None]
            return np.r_[((np.clip(raw,0,1)-target)*mass[:,None]).ravel(),regularizer@v]
        def jac(v):
            raw=x+(design@v).reshape(-1,3)/mass[:,None]
            return sparse.vstack([design.multiply(((raw>0)&(raw<1)).ravel()[:,None]),regularizer],format='csr')
        zero=np.zeros(1215)
        result=least_squares(loss,zero,jac=jac,bounds=(-64,63),tr_solver='lsmr',max_nfev=60,ftol=1e-6)
        v=result.x if np.isfinite(result.fun).all() and np.linalg.norm(result.fun)<=np.linalg.norm(loss(zero)) else zero
        table=np.clip(np.rint(v.reshape(405,3)),-64,63).astype(np.int8)
        return table,dict(model_sha256=self.sha256,regularization=strength,training_only=True,evaluations=result.nfev,converged=bool(result.success),calibration_validation=self.validation,physical_scope=self.value['metadata']['physical_scope'],new_scene_camera_verified=False)
