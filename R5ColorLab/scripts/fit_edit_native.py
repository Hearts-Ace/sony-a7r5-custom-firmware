"""Fit quantized CC1, 16-sector block13, and 128-knot Gamma to paired data.

Inputs are integer RGB AFTER Edit RAW decoding/WB/demosaic/SSCS, not sRGB or
unlabeled sensor RGB. Targets are explicit desired 14-bit encoded RGB. The
renderer is the measured COLOR SUBCHAIN; it does not pretend spatial NR,
sharpening, JPEG compression or a missing S-Log3 input bridge are identity.
"""
from pathlib import Path
import argparse
from functools import lru_cache
import hashlib
import json
import struct
from edit_parameter_context import ParameterContext, RuntimeColor, np, quantize_matrix_coefficients


def sha(data): return hashlib.sha256(data).hexdigest()


def metrics(predicted,target):
    delta=np.asarray(predicted,dtype=np.float64)-np.asarray(target,dtype=np.float64)
    return dict(mae_14bit_codes=float(np.mean(np.abs(delta))),
        rmse_14bit_codes=float(np.sqrt(np.mean(delta**2))),
        p95_abs_14bit_codes=float(np.percentile(np.abs(delta),95)),
        maximum_abs_14bit_codes=float(np.max(np.abs(delta))),pixels=int(delta.size//3))


class NativeFit:
    def __init__(self,context):
        self.context=context
        cfg=context.base.config
        coeff=np.array(struct.unpack_from('<96f',cfg,0x28)).reshape(6,16)
        c=context.cc1
        bits=(c[:4]&65535)>>2&511
        mixed=np.where(bits>255,bits-512,bits)
        gains=(c[4:]&65535)>>3&255
        self.initial=np.concatenate([mixed,gains,np.rint(coeff.reshape(-1)*1024),np.zeros(8)])
        self.lower=np.concatenate([np.full(4,-256),np.zeros(4),np.full(96,-8191),np.full(8,-4096)])
        self.upper=np.concatenate([np.full(4,255),np.full(4,255),np.full(96,8191),np.full(8,4096)])
        self.step=np.concatenate([np.full(4,4),np.full(4,2),np.full(96,4),np.full(8,64)])
        # PC search basis only: the actual native curve always remains the
        # original 128 nonuniform x coordinates and integer y ordinates.
        self.gamma_nodes=np.linspace(0,127,9)
        self.evaluations=0

    def parameters(self,vector):
        v=np.clip(np.rint(np.asarray(vector,dtype=np.float64)),self.lower,self.upper)
        if v.shape != (112,) or not np.all(np.isfinite(v)): raise ValueError('Invalid fitting vector')
        coeff=v[8:104].reshape(6,16)/1024
        payload,decoded=quantize_matrix_coefficients(self.context.payload,coeff)
        cc=np.empty(8,dtype=np.int64)
        cc[:4]=v[:4].astype(np.int64)*4+(self.context.cc1[:4]&3)
        cc[4:]=v[4:8].astype(np.int64)*8+(self.context.cc1[4:]&7)
        correction=np.interp(np.arange(128),self.gamma_nodes,np.r_[0,v[104:]])*16
        y=np.maximum.accumulate(np.clip(np.rint(self.context.gamma_y+correction),0,262143)).astype(np.int32)
        y[0]=0
        return dict(matrix_payload=payload,cc1=cc,gamma_y=y)

    def render(self,vector,image):
        p=self.parameters(vector)
        self.evaluations+=1
        return self.context.build(**p).color_only(image)

    def solve(self,train,target,valid,valid_target,sweeps=6):
        if not 1 <= sweeps <= 24: raise ValueError('Expected 1..24 sweeps')
        vector=self.initial.copy()
        def loss(v):
            delta=self.render(v,train).astype(np.float64)-target
            return float(np.mean(delta**2))
        score=loss(vector)
        initial_valid=metrics(self.render(vector,valid),valid_target)
        best=(initial_valid['rmse_14bit_codes'],vector.copy(),0)
        history=[]
        for sweep in range(sweeps):
            factor=2**(sweep//2)
            step=np.maximum(np.rint(self.step/factor),1)
            changed=0
            for i in range(len(vector)):
                old=vector[i]; winner=old; winner_score=score
                for sign in [-1,1]:
                    candidate=np.clip(old+sign*step[i],self.lower[i],self.upper[i])
                    if candidate==old: continue
                    vector[i]=candidate
                    s=loss(vector)
                    if s < winner_score:
                        winner,winner_score=candidate,s
                vector[i]=winner
                changed+=int(winner!=old);score=winner_score
            validation=metrics(self.render(vector,valid),valid_target)
            if validation['rmse_14bit_codes'] < best[0]:
                best=(validation['rmse_14bit_codes'],vector.copy(),sweep+1)
            row=dict(sweep=sweep+1,changed_coordinates=changed,train_mse_codes=score,
                validation=validation,minimum_step=float(np.min(step)),evaluations=self.evaluations)
            history.append(row)
            print(json.dumps(row),flush=True)
            if changed==0 and np.all(step==1): break
        return best[1],dict(history=history,selected_sweep=best[2],evaluations=self.evaluations,
            termination='bounded quantized coordinate search; no global-optimum claim',
            initial_validation=initial_valid)


def validate_pair(image,target):
    a,b=np.asarray(image),np.asarray(target)
    if (a.ndim!=3 or a.shape[2]!=3 or a.shape[1]<5 or a.shape!=b.shape
            or not np.all(np.isfinite(a)) or not np.all(np.isfinite(b))
            or np.any(a!=np.trunc(a)) or np.any(a<0) or np.any(a>32767)
            or np.any(b<0) or np.any(b>16383)):
        raise ValueError('Expected matching HxWx3 native integer inputs and 14-bit RGB targets')
    return a.astype('<u2'),b.astype(np.float64)


def select_pc_residual(base,target,valid,valid_target):
    """Optional research grid, explicitly PC output correction only."""
    from residual_grid import fit,evaluate,pack,unpack
    a=np.asarray(base).reshape(-1,3)/16383
    b=np.asarray(target).reshape(-1,3)/16383
    v=np.asarray(valid).reshape(-1,3)/16383
    vt=np.asarray(valid_target).reshape(-1,3)
    rows=[];best=None
    for strength in [.001,.03,1.]:
        grid,info=fit(a,b,np.eye(3),strength=strength)
        grid=unpack(pack(grid))
        score=metrics(evaluate(v,grid,np.eye(3))*16383,vt)
        rows.append(dict(solver=info,validation=score))
        if best is None or score['rmse_14bit_codes'] < best[0]:
            best=(score['rmse_14bit_codes'],grid,info)
    baseline=metrics(np.asarray(valid).reshape(-1,3),vt)
    use=best[0] < baseline['rmse_14bit_codes']
    if not use: best=(baseline['rmse_14bit_codes'],np.zeros((405,3),dtype=np.int8),{})
    return dict(payload_hex=pack(best[1]).hex(),response=np.eye(3).tolist(),
        coordinate_model='provisional-bt601-limited',stage='after-color-subchain-PC-only',
        camera_semantics_verified=False,selection=dict(candidates=rows,accepted=use,
            native_validation=baseline,selected_solver=best[2]))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('pairs',type=Path,help='NPZ: train/valid/test_input and corresponding _target arrays')
    ap.add_argument('--capture',type=Path,required=True)
    ap.add_argument('--context',type=int,required=True)
    ap.add_argument('--target-description',required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--sweeps',type=int,default=6)
    ap.add_argument('--residual-pc',action='store_true',help='Explicit provisional PC grid, not R5 grid semantics')
    args=ap.parse_args()
    if args.output.exists(): raise ValueError('New output required')
    from replay_edit_parameter_context import ParameterReplay
    engine=ParameterReplay()
    builder=lru_cache(maxsize=128)(engine.matrix_bytes)
    measured=RuntimeColor.from_capture(args.capture,args.context)
    context=ParameterContext(measured,builder)
    fitter=NativeFit(context)
    with np.load(args.pairs,allow_pickle=False) as arrays:
        data={key:validate_pair(arrays[key+'_input'],arrays[key+'_target']) for key in ['train','valid','test']}
    fitted,info=fitter.solve(*data['train'],*data['valid'],sweeps=args.sweeps)
    params=fitter.parameters(fitted)
    result=dict(schema='r5-edit-native-color-fit/1',complete_edit_fitter=False,camera_apply_allowed=False,
        renderer='measured-Edit-color-subchain-with-native-matrix-builder',
        target_description=args.target_description,input_domain='Edit post-SSCS/pre-matrix integer RGB',
        output_domain='14-bit encoded RGB after recovered color-only subchain',
        source=dict(capture_report_sha256=sha((args.capture/'report.json').read_bytes()),
            context=args.context,runtime_sha256=sha(measured.runtime),raw_sha256=sha(measured.raw),
            settings_sha256=sha(measured.settings),pairs_sha256=sha(args.pairs.read_bytes())),
        parameters=dict(matrix_780f_hex=params['matrix_payload'].hex(),cc1_direct_raw=params['cc1'].tolist(),
            gamma_7806_y=params['gamma_y'].tolist(),gamma_7805_x=context.axis.tolist()),
        fitting=info,heldout=dict(before=metrics(fitter.render(fitter.initial,data['test'][0]),data['test'][1]),
            after=metrics(fitter.render(fitted,data['test'][0]),data['test'][1])),
        scripts={p.name:sha(p.read_bytes()) for p in [Path(__file__),Path(__file__).with_name('edit_parameter_context.py'),
            Path(__file__).with_name('edit_color_pipeline.py'),Path(__file__).with_name('edit_native_model.py')]},
        limitations=['Target pairs must explicitly supply the target; no assumed S-Log3 bridge.',
            'Color subchain only; spatial NR/sharpening/final JPEG not included.',
            'AreaComp included only when measured controls exist in the source capture.',
            'Validation selects checkpoint; test arrays are never used to fit or select.',
            'Native 96 matrix fields + eight effective CC1 + eight search controls for 128-knot Gamma.',
            'PC-only result, not a camera SD file or a complete RAW-to-JPEG fitter.'])
    if args.residual_pc:
        result['pc_residual']=select_pc_residual(fitter.render(fitted,data['train'][0]),data['train'][1],
            fitter.render(fitted,data['valid'][0]),data['valid'][1])
        from residual_grid import evaluate,unpack
        corrected=evaluate(fitter.render(fitted,data['test'][0]).reshape(-1,3)/16383,
            unpack(bytes.fromhex(result['pc_residual']['payload_hex'])),np.eye(3))*16383
        result['heldout']['native_plus_pc_residual']=metrics(corrected,data['test'][1].reshape(-1,3))
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    from edit_native_recipe import read,render
    _,decoded=read(args.output,args.capture,args.context,builder)
    expected=(corrected.reshape(data['test'][0].shape) if args.residual_pc
        else fitter.render(fitted,data['test'][0]))
    if not np.array_equal(render(decoded,data['test'][0]),expected):
        raise AssertionError('Native recipe read-back prediction changed')
    print(json.dumps(result['heldout'],indent=2))


if __name__=='__main__': main()
