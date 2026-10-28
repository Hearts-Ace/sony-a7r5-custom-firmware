from compute_backend import render_native
from patch_sampling import center_mean
"""Reproducible search policy; adaptation never consumes validation/test arrays."""
import numpy as np
from training_policy import GROUPS, group_importance
from perceptual import to_lab, de2000

def pc_options(value=None):
    from grid_models import default_response
    result={'curve_mode':'tone-tint','grid_enabled':True,'response':default_response()}
    if value is not None:
        if not isinstance(value,dict) or set(value)-set(result):raise ValueError('未知 PC 曲线选项')
        result.update(value)
    if result['curve_mode'] not in ('tone-tint','qaq-grid') or type(result['grid_enabled']) is not bool:
        raise ValueError('无效 PC 曲线模式或网格开关')
    from residual_grid import response_json
    result['response']=response_json(result['response'])
    if result['curve_mode']=='qaq-grid' and not result['grid_enabled']:
        raise ValueError('QAQ方案必须启用网格')
    return result


def search_options(value=None):
    defaults=dict(starts=4, adaptive_rounds=3, perceptual_weight=.35, quantization_sweeps=1, parameter_smoothing=0, output_continuity=0, gamma_color_rounds=0, primary_tonal_weight=1.0, hue24_tonal_weight=1.0)
    if value is None:return defaults
    if not isinstance(value,dict) or set(value)-set(defaults):raise ValueError('未知优化器选项')
    result={**defaults,**value}
    for name,low,high in [('starts',2,12),('adaptive_rounds',0,8),('quantization_sweeps',0,3),('gamma_color_rounds',0,12)]:
        if type(result[name]) is not int or not low<=result[name]<=high:raise ValueError(name+' 超出允许范围')
    for name in ('primary_tonal_weight','hue24_tonal_weight'):
        if type(result[name]) not in (int,float) or not np.isfinite(result[name]) or not .05<=result[name]<=8:
            raise ValueError(name+' must be between 0.05 and 8')
    from parameter_smoothing import strength
    result['parameter_smoothing']=strength(result['parameter_smoothing'])
    result['output_continuity']=strength(result['output_continuity'])
    v=result['perceptual_weight']
    if type(v) not in (int,float) or not np.isfinite(v) or not 0<=v<=2:raise ValueError('感知权重需在0–2之间')
    return result


def adaptive_importance(base, errors):
    """Bounded sqrt error balancing relative to immutable user weights."""
    base=group_importance(base)
    names=tuple(base)
    e=np.array([errors[k] for k in names],dtype=float)
    if not np.isfinite(e).all() or np.any(e<0):raise ValueError('Invalid training group errors')
    ratio=np.clip(np.sqrt(np.maximum(e,1)/max(float(np.median(e)),1)),.5,2)
    return {k:float(np.clip(base[k]*ratio[i],.05,64)) for i,k in enumerate(names)}


def display_cost_rows(predicted, target, perceptual_weight=0):
    """Floating encoded RGB MSE plus continuous DE00; no 8-bit pre-rounding.

    Native candidates still come from the actual integer parameter renderer.
    Explicit uint8 display metrics remain in report_metrics.
    """
    from gpu_runtime import available
    if available() and len(predicted)>=1024:
        from gpu_color import display_cost_rows as gpu_cost
        return gpu_cost(predicted,target,perceptual_weight)
    p,t=[np.clip(np.asarray(v,dtype=float),0,1)*255 for v in (predicted,target)]
    cost=np.mean((p-t)**2,axis=1)
    if perceptual_weight:
        cost+=perceptual_weight*(2.55*de2000(to_lab(p),to_lab(t)))**2
    return cost


def smooth_loss_rows(predicted, target, perceptual_weight=0):
    """Differentiable RGB + Lab76 residual, no uint8 rounding during gradient fit."""
    p,t=np.clip(predicted,0,1),np.clip(target,0,1)
    parts=[(p-t)/np.sqrt(3)]
    if perceptual_weight:
        parts.append((to_lab(p*255)-to_lab(t*255))/100*np.sqrt(perceptual_weight))
    return np.concatenate(parts,axis=1)


def perturbed_starts(seed, count, lower, upper):
    rng=np.random.default_rng(20261021)
    result=[]
    for i in range(count):
        v=seed.copy()
        v[:8]+=rng.normal(0,.025,8)
        noise=rng.normal(0,.08,(6,16));noise=(np.roll(noise,1,1)+2*noise+np.roll(noise,-1,1))/4
        v[8:104]+=noise.ravel()
        g=rng.normal(0,.12,len(v)-104);g=np.convolve(g,np.ones(5)/5,mode='same')
        v[104:]+=g
        result.append(np.clip(v,lower+1e-5,upper-1e-5))
    return result


def refine_grid(grid, base, target, gate, weights, sweeps=1, perceptual_weight=0, response=None, progress=None, parameter_smoothing=0):
    """Signed-7-bit coordinate descent, train-only actual quantized display loss."""
    from gpu_runtime import available
    if available():
        from gpu_grid_refine import refine
        return refine(grid,base,target,gate,weights,sweeps,perceptual_weight,response,progress,parameter_smoothing)
    if isinstance(response,dict):
        from measured_response import get
        from parameter_smoothing import grid_cost
        model=get(response);_,ids,w=model.stencil(base)
        result=np.asarray(grid,dtype=int).copy();weights=np.asarray(weights)/np.sum(weights)
        predicted=model.predict(base,result);costs=display_cost_rows(predicted,target,perceptual_weight)
        penalty=lambda table:grid_cost(table,parameter_smoothing)
        before=float(costs@weights)+penalty(result);accepted=0
        for sweep in range(sweeps):
            changed=False
            for node in range(405):
                if progress and node%27==0:progress(sweep=sweep+1,total_sweeps=sweeps,point=node,total_points=405)
                rows=np.any((ids==node)&(w>0),axis=1)
                if not rows.any():continue
                for channel in range(3):
                    best=float(costs[rows]@weights[rows])+penalty(result);choice=None
                    for step in (-1,1):
                        if not -64<=result[node,channel]+step<=63:continue
                        trial=result.copy();trial[node,channel]+=step
                        prediction=model.predict(np.asarray(base)[rows],trial)
                        candidate=display_cost_rows(prediction,np.asarray(target)[rows],perceptual_weight)
                        score=float(candidate@weights[rows])+penalty(trial)
                        if score<best-1e-12:best=score;choice=(trial,candidate)
                    if choice is not None:
                        result,candidate=choice;costs[rows]=candidate;accepted+=1;changed=True
            if not changed:break
        return result.astype(np.int8),dict(before=before,after=float(costs@weights)+penalty(result),accepted=accepted,
            sweeps=sweeps,model_sha256=model.sha256,objective='measured response; quantized RGB and DE00')
    from pc_stages import grid_design
    from scipy import sparse
    design=grid_design(base,(5,9,9)).multiply(gate[:,None]).tocsc()
    design.eliminate_zeros()
    result=np.asarray(grid,dtype=int).copy()
    response=np.eye(3) if response is None else np.asarray(response)
    raw=base+(design@result/256)@response
    costs=display_cost_rows(raw,target,perceptual_weight)
    weights=np.asarray(weights)/np.sum(weights)
    from parameter_smoothing import grid_cost
    penalty=lambda g:grid_cost(g,parameter_smoothing)
    before=float(costs@weights)+penalty(result);accepted=0
    for sweep in range(sweeps):
        changed=False
        for j in range(405):
            if progress and j%27==0:progress(sweep=sweep+1,total_sweeps=sweeps,point=j,total_points=405)
            a,b=design.indptr[j:j+2];rows=design.indices[a:b];values=design.data[a:b]/256
            if not len(rows):continue
            for c in range(3):
                old=float(costs[rows]@weights[rows])+penalty(result);best=old;choice=None
                for step in (-1,1):
                    if not -64<=result[j,c]+step<=63:continue
                    proposal=raw[rows].copy();proposal+=step*values[:,None]*response[c]
                    score=display_cost_rows(proposal,target[rows],perceptual_weight)
                    trial=result.copy();trial[j,c]+=step
                    value=float(score@weights[rows])+penalty(trial)
                    if value<best-1e-12:best=value;choice=(step,proposal,score)
                if choice is not None:
                    step,proposal,score=choice;result[j,c]+=step;raw[rows]=proposal;costs[rows]=score;accepted+=1;changed=True
        if not changed:break
    return result.astype(np.int8),dict(before=before,after=float(costs@weights)+penalty(result),parameter_smoothing=parameter_smoothing,accepted=accepted,sweeps=sweeps,
                                      objective='train weighted uint8 RGB MSE + perceptual_weight*(2.55*DE00)^2',perceptual_weight=perceptual_weight)


def refine_native(ctx, parameters, inputs, target, weights, pc_bundle, sweeps=1, perceptual_weight=0, progress=None, parameter_smoothing=0, output_penalty=None):
    """Exact integer CC1, all 96 block13 coefficients and 127 nonzero Gamma nodes.

    PC is frozen during moves and rebuilt when the resulting candidate is assessed.
    Every accepted move strictly lowers the same train-only quantized objective.
    """
    import struct
    import pc_stages
    from edit_native_model import decode_matrix16
    from edit_parameter_context import quantize_matrix_coefficients
    def copy(p):return {k:(v.copy() if isinstance(v,np.ndarray) else v) for k,v in p.items()}
    def cost(p):
        rgb=center_mean(render_native(ctx.build(**p),inputs))/16383
        if pc_bundle is not None:rgb=pc_stages.render(rgb,pc_bundle[0],pc_bundle[1])
        from parameter_smoothing import native_cost
        return (float(display_cost_rows(rgb,target,perceptual_weight)@weights/np.sum(weights))
            +(native_cost(p,ctx.axis,parameter_smoothing) if parameter_smoothing else 0)
            +(output_penalty(p) if output_penalty is not None else 0))
    current=copy(parameters)
    original_cost=cost(current)
    # 4.18 serializes Gamma ordinates and the last four CC1 values at half
    # the RAW units. Optimize the values reconstructed from that export.
    current['gamma_y']=np.minimum(262142,2*((current['gamma_y']+1)//2))
    current['cc1'][4:]=2*np.minimum(1023,(current['cc1'][4:]+1)//2)
    best=cost(current);before=best;accepted=0;calls=2
    for sweep in range(sweeps):
        changed=False
        for family,count in [('cc1',8),('matrix',96),('gamma_y',127)]:
            for index in range(count):
                if progress and index%8==0:progress(sweep=sweep+1,total_sweeps=sweeps,point=index,total_points=count,family=family)
                winner=None;score=best
                for sign in (-1,1):
                    proposal=copy(current)
                    if family=='cc1':
                        proposal['cc1'][index]+=sign*(4 if index<4 else 8)
                        if not (-1024<=proposal['cc1'][index]<=1023 if index<4 else 0<=proposal['cc1'][index]<=2047):continue
                    elif family=='gamma_y':
                        at=index+1;proposal['gamma_y'][at]+=sign*(16 if sweep==0 else 2)
                        y=proposal['gamma_y']
                        if y[at]<y[at-1] or y[at]>262143 or (at<127 and y[at]>y[at+1]):continue
                    else:
                        coeff=np.array(struct.unpack_from('<96f',decode_matrix16(current['matrix_payload']),0x28)).reshape(6,16)
                        coeff.flat[index]+=sign*(2 if coeff.flat[index]<0 else 1)/1024
                        if np.abs(coeff).max()>8191/1024:continue
                        proposal['matrix_payload'],_=quantize_matrix_coefficients(current['matrix_payload'],coeff)
                        if proposal['matrix_payload']==current['matrix_payload']:continue
                    value=cost(proposal);calls+=1
                    if value<score-1e-12:score=value;winner=proposal
                if winner is not None:current=winner;best=score;accepted+=1;changed=True
        if not changed:break
    return current,dict(original_before_export_roundtrip=original_cost,before=before,after=best,accepted=accepted,evaluations=calls,sweeps=sweeps,
                        objective='train weighted floating RGB MSE + continuous DE00 squared on integer native outputs; frozen PC',
                        output_continuity=output_penalty is not None,
                        gamma_zero_fixed=True,gamma_monotone=True,export_roundtrip='4.18 half-unit Gamma and CC1 gains')
