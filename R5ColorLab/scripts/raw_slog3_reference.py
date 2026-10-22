"""Explicit sensor RGB -> S-Log3 -> cube reference, without photo fitting.

Sensor RGB denotes black-subtracted, white-normalized camera channels before
white balance. A uniform Bayer patch has this RGB independent of demosaic.
This module does not pretend that arbitrary Edit stage codes have this domain.
"""
from pathlib import Path
import json
import numpy as np
from fit_native_proxy import Cube, slog3


def multiply(rgb, matrix):
    return np.einsum('...j,ij->...i',rgb,matrix,optimize=False)


def tetrahedral(cube, rgb):
    """Red-fastest .cube storage; all six tetrahedra, including boundaries."""
    x=np.asarray(rgb,dtype=np.float64)
    if x.ndim!=2 or x.shape[1]!=3 or not np.isfinite(x).all():
        raise ValueError('Finite Nx3 RGB required')
    at=np.clip((x-cube.lo)/(cube.hi-cube.lo),0,1)*(cube.size-1)
    lo=np.minimum(np.floor(at).astype(int),cube.size-2)
    f=at-lo;order=np.argsort(-f,axis=1,kind='stable')
    frac=np.take_along_axis(f,order,axis=1)
    weights=np.stack([1-frac[:,0],frac[:,0]-frac[:,1],frac[:,1]-frac[:,2],frac[:,2]],axis=1)
    vertices=np.repeat(lo[:,None,:],4,axis=1)
    rows=np.arange(len(x))
    for k in range(1,4):
        vertices[:,k]=vertices[:,k-1]
        vertices[rows,k,order[:,k-1]]+=1
    values=cube.values[vertices[:,:,2],vertices[:,:,1],vertices[:,:,0]]
    return np.sum(values*weights[:,:,None],axis=1)


class RawSLog3Reference:
    def __init__(self, profile, cube, gamut, mode='raw-alchemy-v0.6.2', exposure_ev=0):
        if gamut not in ['S-Gamut3','S-Gamut3.Cine'] or mode not in ['raw-alchemy-v0.6.2','raw-alchemy-v0.6.2-fused','analytic-unclipped']:
            raise ValueError('Explicit gamut and reference mode required')
        if profile['schema']!='camera-RAW-SLog3-reference-profile/1':raise ValueError('Unknown profile')
        self.profile=profile;self.cube=cube;self.gamut=gamut;self.mode=mode
        self.ev=float(exposure_ev)
        if not np.isfinite(self.ev):raise ValueError('Finite exposure required')
        self.cam=np.asarray(profile['camera_to_working'],dtype=float)
        self.to_log=np.asarray(profile['working_to_log'][gamut],dtype=float)
        self.wb=np.asarray(profile['camera_wb_rgb'],dtype=float)
        self.log_axis=np.linspace(0,16,16384)
        self.log_values=slog3(self.log_axis).astype(np.float32)
        if self.cam.shape!=(3,3) or self.to_log.shape!=(3,3) or self.wb.shape!=(3,):
            raise ValueError('Incomplete profile matrices')
        if not all(np.isfinite(x).all() for x in [self.cam,self.to_log,self.wb]):
            raise ValueError('Nonfinite profile')

    def stages(self, sensor):
        sensor=np.asarray(sensor,dtype=float)
        if sensor.ndim!=2 or sensor.shape[1]!=3 or not np.isfinite(sensor).all():
            raise ValueError('Finite normalized sensor Nx3 required')
        wb=sensor*self.wb
        working=multiply(wb,self.cam)
        # This upper clip is part of Raw Alchemy canonical decode, before EV.
        # The analytic mode deliberately keeps excursions and is a different
        # target, not a claim to reproduce the app or Sony camera S-Log3.
        decoded=np.minimum(working,1) if self.mode!='analytic-unclipped' else working
        graded=decoded*(2**self.ev)
        # Installed grade_log_dyn.onnx executes highlight/shadow and saturation/
        # contrast even with neutral feeds. Clip_3 and Clip_4 clamp working RGB
        # to zero BEFORE mat_b. The unfused per-op path skips neutral controls;
        # keep its historical mode distinct rather than silently rewriting it.
        if self.mode=='raw-alchemy-v0.6.2-fused':graded=np.maximum(graded,0)
        log_linear=multiply(graded,self.to_log)
        if self.mode!='analytic-unclipped':
            encoded=np.interp(np.maximum(log_linear,1e-6),self.log_axis,self.log_values)
        else:encoded=slog3(log_linear)
        restored=tetrahedral(self.cube,encoded)
        return dict(sensor=sensor,white_balanced=wb,working_unclipped=working,
            working=decoded,graded_working=graded,log_linear=log_linear,slog3=encoded,
            lut_output_unclipped=restored,output=np.clip(restored,0,1))

    def __call__(self,sensor):return self.stages(sensor)['output']


def sensor_test_set(seed,count,wb):
    """Independent synthetic colors + explicit exposure/hue/neutral anchors."""
    rng=np.random.default_rng(seed)
    uniform=rng.uniform(0,1,(count//2,3))
    colors=rng.uniform(0,1,(count-count//2,3))
    colors/=np.maximum(colors.max(axis=1,keepdims=True),1e-12)
    levels=np.exp(rng.uniform(np.log(1e-6),np.log(1),len(colors)))
    random=np.concatenate([uniform,colors*levels[:,None]])
    return random


def anchors(wb):
    """Source-domain anchors; neutrals are defined after camera white balance."""
    levels=np.r_[0,np.geomspace(1e-6,1,97)]
    neutral=np.minimum(levels[:,None]/np.asarray(wb),1)
    corners=np.array([[r,g,b] for r in [0,1] for g in [0,1] for b in [0,1]],float)
    return np.concatenate([neutral,corners])
