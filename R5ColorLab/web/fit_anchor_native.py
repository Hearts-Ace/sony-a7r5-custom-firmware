from compute_backend import render_native
from patch_sampling import center_mean
"""Web anchored adapter, derived from preserved historical fitter. Synthetic complete-chain native parameter fitting, no residual or extra matrix.

Actual Edit supplies the synthetic RAW frontend and full output oracle. A
continuous relaxation initializes native CC1/block13/Gamma, then actual integer
parameters are evaluated separately. Test colors never select parameters.
"""
from pathlib import Path
import argparse,hashlib,json,struct,sys,time
import numpy as np
from training_policy import group_importance, composite_score
from optimizer_policy import pc_options, search_options, adaptive_importance, smooth_loss_rows, display_cost_rows, perturbed_starts, refine_native
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from edit_parameter_context import ParameterContext,RuntimeColor,np,quantize_matrix_coefficients
ROOT=Path(__file__).resolve().parents[1]
from scipy.optimize import least_squares, minimize
import white_balance as wb
import tonal_sampling
from scipy.special import softmax
from fit_edit_native import metrics
from edit_native_model import decode_matrix16
from parameter_smoothing import native_rows, native_cost, pc_cost

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

class SmoothNative:
 def __init__(self,ctx,x):
  self.ctx=ctx;self.x=np.asarray(x,dtype=float);cfg=ctx.base.config
  self.knots=np.arange(128)
  self.axis=ctx.axis/128.;self.controls=self.axis[self.knots]
  self.s=ctx.base.sectors(x).astype(int)
  angles=np.array(struct.unpack_from('<16H',cfg,6));right=np.searchsorted(angles,self.s,side='right');self.left=(right-1)%16;self.right=right%16
  a=angles[self.left].astype(float);b=angles[self.right].astype(float);b=np.where(b<=a,b+1024,b);t=np.where(self.s>=a,self.s,self.s+1024)
  norms=np.array(struct.unpack_from('<16H',cfg,0x1e8));mode=struct.unpack_from('<H',cfg,0x26)[0];factor=1/(4096*(2<<mode)) if mode<3 else 1/65536
  self.wl=(b-t)*norms[self.left]*factor;self.wr=(t-a)*norms[self.left]*factor
  self.scales=np.array(struct.unpack_from('<16f',cfg,0x1a8));self.diag=struct.unpack_from('<3f',cfg,0x208)
  self.threshold=np.array(struct.unpack_from('<3f',cfg,0x214));self.quadratic=bool(struct.unpack_from('<H',cfg,0x222)[0])
  self.weights=np.array(struct.unpack_from('<3h',ctx.base.runtime,0x218f6))/8192
  self.chroma=ctx.base.chroma_controls();self.area=np.frombuffer(ctx.base.area_controls,dtype='<f4',count=16).astype(float)
  self.ytable=np.frombuffer(ctx.base.runtime,dtype='<u2',count=32768,offset=0x318fc).astype(float)
  self.pivot=struct.unpack_from('<h',ctx.base.runtime,0x91962)[0];self.ygain=struct.unpack_from('<f',ctx.base.runtime,0x91964)[0]
  if any(struct.unpack_from('<h',ctx.base.settings,k)[0] for k in [0x2ac,0x2b0]):raise ValueError('Neutral levels required')
 def gamma(self,v):
  yi=np.r_[0,np.cumsum(softmax(v[104:])[:-1])]*16383
  return np.interp(self.axis,self.controls,yi)
 def params(self,v):
  payload,_=quantize_matrix_coefficients(self.ctx.payload,v[8:104].reshape(6,16))
  cc=np.r_[np.rint(v[:4]*256).astype(int)*4+(self.ctx.cc1[:4]&3),np.rint(v[4:8]*64).astype(int)*8+(self.ctx.cc1[4:]&7)]
  cc[:4]=np.clip(cc[:4],-1024,1023);cc[4:]=np.clip(cc[4:],0,2047)
  y=np.maximum.accumulate(np.rint(self.gamma(v)*16)).astype(int);y[0]=0
  return dict(matrix_payload=payload,cc1=cc,gamma_y=y)
 def render(self,v):
  c=v[8:104].reshape(6,16)
  q=c[:,self.left].transpose(1,2,0)*self.wl[:,:,None]+c[:,self.right].transpose(1,2,0)*self.wr[:,:,None]
  z=c[:,self.left].transpose(1,2,0)*(self.wl*self.scales[self.left])[:,:,None]+c[:,self.right].transpose(1,2,0)*(self.wr*self.scales[self.right])[:,:,None]
  r,g,b=self.x.transpose(2,0,1);a,bb,cc,d,e,f=q.transpose(2,0,1)
  linear=np.stack([(a+bb+self.diag[0])*r-a*g-bb*b,-cc*r+(cc+d+self.diag[1])*g-d*b,-e*r-f*g+(e+f+self.diag[0])*b],axis=-1)
  if self.quadratic:
   a,bb,cc,d,e,f=z.transpose(2,0,1);r,g,b=r*r,g*g,b*b
   n=np.stack([(-a-bb)*r+a*g+bb*b,cc*r+(-cc-d)*g+d*b,e*r+f*g+(-e-f)*b],axis=-1)/16384
   linear+=np.where(n>=0,np.maximum(n-self.threshold,0),0)
  rgb=np.interp(np.clip(linear,0,16383),self.axis,self.gamma(v)).reshape(-1,3)
  dr=rgb[:,0]-rgb[:,1];db=rgb[:,2]-rgb[:,1]
  cr=(dr+db*np.where(db>=0,v[0],v[2]));cb=(db+dr*np.where(dr>=0,v[1],v[3]))
  cr=np.clip(cr*.5*np.where(cr>=0,v[5],v[7]),-8192,8191);cb=np.clip(cb*.5*np.where(cb>=0,v[4],v[6]),-8192,8191)
  y=rgb@self.weights
  c=self.area;x1,y1=c[0]+cr,c[1]+cb;x2,y2=c[2]+cr,c[3]+cb
  u=np.minimum(np.maximum(y1*c[6]+x1*c[4],0),np.maximum(c[7]*y1+c[5]*x1,0))
  vv=np.minimum(np.maximum(y2*c[10]+x2*c[8],0),np.maximum(c[11]*y2+c[9]*x2,0))
  if self.ctx.base.area_controls[64]:u=np.minimum(u,vv);vv=0
  cr=cr+u*c[12]+vv*c[14];cb=cb+u*c[13]+vv*c[15]
  c=self.chroma;amount=np.where(y<c['low_cutoff'],(c['low_cutoff']-y)*c['low_slope'],np.maximum(y-c['high_cutoff'],0)*c['high_slope'])
  factor=np.clip(255-amount/4096,0,255)/256;cr*=factor;cb*=factor
  y=np.interp(np.maximum(y,0),np.arange(32768),self.ytable);y=(y-self.pivot)*self.ygain+self.pivot;y=np.clip(y,0,16383)
  out=np.stack([y+cr*1.402,y-cr*.7141-cb*.3441,y+cb*1.772],axis=-1)
  return center_mean(np.clip(out,0,16383).reshape(self.x.shape))

def vector_for(ctx):
 c=np.array(struct.unpack_from('<96f',ctx.base.config,0x28));bits=(ctx.cc1[:4]&65535)>>2&511;m=np.where(bits>255,bits-512,bits)/256;g=((ctx.cc1[4:]&65535)>>3&255)/64
 knots=np.arange(128)
 increments=np.maximum(np.diff(ctx.gamma_y[knots]/16),.01)
 return np.r_[m,g,c,np.log(np.r_[increments,max(16383-ctx.gamma_y[-1]/16,.01)])]

def report_metrics(p,t):
 r=metrics(p,t)
 a,b=[np.floor(np.clip(v/16383,0,1)*255+.5) for v in (np.asarray(p),np.asarray(t))]
 delta=a-b
 r.update(mae_8bit=float(np.abs(delta).mean()),rmse_8bit=float(np.sqrt(np.mean(delta*delta))),p95_8bit=float(np.percentile(np.abs(delta),95)),encoding_8bit='clip and round uint8 on both outputs; no black subtraction')
 return r

def training_plan(split,anchor_ids,importance=None,sector_ids=None,tonal_ids=None,random_selection=None,sample_kind=None,track_options=None):
 importance=group_importance(importance)
 train=np.flatnonzero(split=='train'); mandatory=np.flatnonzero(anchor_ids>=0)
 if len(mandatory) not in (260,284) or set(anchor_ids[mandatory])!=set(range(len(mandatory))) or not np.all(split[mandatory]=='train'):
  raise ValueError('Missing or leaked anchor cohort')
 sector_ids=np.full(len(split),-1) if sector_ids is None else np.asarray(sector_ids)
 sector=np.flatnonzero(sector_ids>=0)
 if len(sector) and (len(mandatory)!=284 or len(sector)!=64 or set(sector_ids[sector])!=set(range(64)) or not np.all(split[sector]=='train') or not np.all(anchor_ids[sector]<0)):raise ValueError('Invalid sector16 cohort')
 sector=sector[np.argsort(sector_ids[sector])]
 random_train=train[(anchor_ids[train]<0)&(sector_ids[train]<0)]
 if random_selection is None:random_train=random_train[::2]
 else:
  selected=np.asarray(random_selection,dtype=int)
  if len(selected)!=len(np.unique(selected)) or not np.isin(selected,random_train).all():raise ValueError('Invalid train-only precision sample selection')
  random_train=np.sort(selected)
 if not len(random_train):raise ValueError('Missing random training cohort')
 train=np.r_[random_train,mandatory[np.argsort(anchor_ids[mandatory])],sector]
 weights=np.full(len(train),importance["random"],dtype=float)
 weights[len(random_train):len(random_train)+4]=len(random_train)/4*importance["primaries"]
 weights[len(random_train)+4:len(random_train)+260]=len(random_train)/256*importance["gray"]
 if len(mandatory)==284:weights[len(random_train)+260:len(random_train)+284]=len(random_train)/24*importance["colorchecker24"]
 if len(sector):weights[-len(sector):]=len(random_train)/len(sector)*importance.get('sector16',1)
 if tonal_ids is not None:
  bins=np.asarray(tonal_ids)
  if bins.shape!=split.shape or not np.isin(bins,[0,1,2]).all():raise ValueError('Invalid baseline luminance strata')
  n=len(random_train)
  for sl in [slice(0,n),slice(n,n+4),slice(n+4,n+260),slice(n+260,n+len(mandatory)),slice(n+len(mandatory),None)]:
   weights[sl]*=tonal_sampling.balanced_weights(bins[train[sl]])
 if sample_kind is not None:
  from precision_sampling import track_multipliers
  n=len(random_train);mass=weights[:n].sum()
  weights[:n]*=track_multipliers(np.asarray(sample_kind)[random_train],track_options)
  weights[:n]*=mass/weights[:n].sum()
 weights/=weights.mean()
 return train,mandatory,random_train,weights

def select_balanced(candidates):
 if not candidates:raise ValueError('Candidates required')
 return min(candidates,key=lambda c:(c['color'],c['gray']))


def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('pairs',type=Path);ap.add_argument('--capture',type=Path,required=True);ap.add_argument('--context',type=int,default=4);ap.add_argument('--gamut',type=int,choices=[0,1],required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--evaluations',type=int,default=80);ap.add_argument('--pc-compensation',action='store_true');ap.add_argument('--white-balance',action='store_true');ap.add_argument('--target-description');ap.add_argument('--group-weights',type=json.loads);ap.add_argument('--search-options',type=json.loads);ap.add_argument('--pc-options',type=json.loads);ap.add_argument('--fast',action='store_true',help='GPU coarse candidate, bounded CPU stages; full holdout evaluation');ap.add_argument('--refine-from',type=Path,help='Continue the identical completed job with block alternation only');a=ap.parse_args();importance=group_importance(a.group_weights);options=search_options(a.search_options);pc_policy=pc_options(a.pc_options);current_importance=importance.copy();adaptive_history=[];a.output.mkdir(exist_ok=False)
 from training_progress import TrainingProgress
 progress=TrainingProgress(a.output.parent/'training_progress.json',options['starts']+4+(2 if a.pc_compensation else 0)+options['adaptive_rounds'],gradient_workers=8)
 progress.value['total_rounds'] += 6 if a.white_balance else 0
 progress.value['total_rounds'] += 2*options['gamma_color_rounds']
 if a.refine_from:
  progress.value['total_rounds']=2*options['gamma_color_rounds']
  if not options['gamma_color_rounds'] or a.white_balance:
   raise ValueError('Continuation requires block alternation and fixed white balance')
 progress.update(stage='载入训练数据',state='running')
 p=np.load(a.pairs);x=p['input'];t=p[str(a.gamut)+'_target'];split=p['split'];ctx=ParameterContext(RuntimeColor.from_capture(a.capture,a.context));start=vector_for(ctx)
 train=np.flatnonzero(split=='train');valid=np.flatnonzero(split=='valid');test=np.flatnonzero(split=='test')
 tonal_ids=p['baseline_tonal_index'] if 'baseline_tonal_index' in p else None
 tonal_audit=tonal_sampling.validate(dict(p),ctx.base)
 # Preserve all mandatory anchors; subsample only the random cohort.
 sector_ids=p['sector16_index'] if 'sector16_index' in p else None
 if sector_ids is not None:
  import sector16
  sector_audit=sector16.validate(p,ctx.base);importance.setdefault('sector16',1.0);current_importance=importance.copy()
 else:sector_audit=None;importance.pop('sector16',None);current_importance=importance.copy()
 precision='design_srgb' in p and 'sample_kind' in p
 sampling_audit=None;random_selection=None
 if precision:
  import precision_sampling
  if not a.refine_from and not a.fast:progress.value['total_rounds'] += 3
  random_selection=(np.flatnonzero((split=='train')&(p['anchor_index']<0)&(sector_ids<0)) if a.refine_from else precision_sampling.coarse(p))
  sampling_audit=dict(policy='H24/S8/Y16 stratified coarse; complete train tonal tracks; all-train refinement; train-only hard mining',coarse_random_samples=len(random_selection),stages=[])
 train,mandatory,random_train,group_weights=training_plan(split,p['anchor_index'],importance,sector_ids,tonal_ids,random_selection,p.get('sample_kind'),options)
 def validation_mean(cost):
  from precision_sampling import track_mean_cost
  return track_mean_cost(cost,tonal_ids[valid] if tonal_ids is not None else None,p['sample_kind'][valid] if 'sample_kind' in p else None,options)
 # Group totals follow user importance, independent of cohort size.
 models={k:SmoothNative(ctx,x[v]) for k,v in [('train',train),('valid',valid),('test',test)]}
 wb_value=wb.ZERO.copy(); current_x=x
 smooth=models['train'];lb=np.r_[np.full(4,-.999),np.full(4,.05),np.full(96,-6),np.full(len(start)-104,-14)]
 ub=np.r_[np.full(4,.996),np.full(4,3.98),np.full(96,6),np.full(len(start)-104,15)]
 calls=0;history=[];candidates=[];active_pc=None;gpu_audit=dict(enabled=False,reason='not run')
 import pc_stages
 gray_mask=(p['anchor_index'][train]>=4)&(p['anchor_index'][train]<260)
 def corrected(rgb,bundle=None):
  return pc_stages.render(rgb/16383,bundle[0],bundle[1])*16383 if bundle is not None else rgb
 gray_indices=train[len(random_train)+4:len(random_train)+260]
 gray_model=SmoothNative(ctx,x[gray_indices])
 continuity_bank=None;continuity_model=None
 if options['output_continuity']:
  from output_continuity import ProbeBank
  continuity_bank=ProbeBank()
  continuity_model=SmoothNative(ctx,continuity_bank.inputs(ctx.base))
  smooth.output_continuity=(continuity_bank,continuity_model,options['output_continuity'])
 def set_wb(value):
  nonlocal wb_value,current_x,smooth,gray_model,models,continuity_model
  wb_value=wb.validate(value)
  current_x=wb.inputs(ctx.base,x,p['sensor_codes'],wb_value)
  models={k:SmoothNative(ctx,current_x[v]) for k,v in [('train',train),('valid',valid),('test',test)]}
  smooth=models['train'];gray_model=SmoothNative(ctx,current_x[gray_indices])
  if continuity_bank is not None:
   continuity_model=SmoothNative(ctx,continuity_bank.inputs(ctx.base,wb_value))
   smooth.output_continuity=(continuity_bank,continuity_model,options['output_continuity'])

 def exact_continuity(params,report=False):
  if continuity_bank is None:return None if report else 0.
  prediction=center_mean(render_native(ctx.build(**params),continuity_model.x))/16383
  return (continuity_bank.report(prediction,options['output_continuity']) if report
          else continuity_bank.cost(prediction,options['output_continuity']))

 def assess(v,label,params_override=None,quantize=False):
  progress.update(stage='整数候选评估与 PC 重建' if a.pc_compensation else '整数候选评估',candidate=label)
  params=params_override or smooth.params(v);exact=ctx.build(**params)
  bundles=[None]
  if a.pc_compensation:
   training=center_mean(render_native(exact,current_x[train]))/16383
   bundles=[pc_stages.fit_training(training,t[train]/16383,gray_mask,group_weights,strategy=strategy,quantization_sweeps=options["quantization_sweeps"] if quantize else 0,perceptual_weight=options["perceptual_weight"],curve_mode=pc_policy["curve_mode"],response=pc_policy["response"],parameter_smoothing=options['parameter_smoothing'])
            for strategy in (('direct',) if pc_policy['curve_mode']=='qaq-grid' else (('direct','dense-compressed') if pc_policy['grid_enabled'] else ('none',)))]
  for bundle in bundles:
   candidate_label=label+(' / '+bundle[2]['strategy'] if bundle else '')
   native=corrected(center_mean(render_native(exact,current_x[valid])),bundle)
   score=report_metrics(native,t[valid]);history.append(dict(label=candidate_label,validation=score,white_balance=wb_value.copy()));print(json.dumps(history[-1]),flush=True)
   anchor_pred=corrected(center_mean(render_native(exact,current_x[train[len(random_train):]])),bundle)
   anchor_target=t[train[len(random_train):]]
   primary=report_metrics(anchor_pred[:4],anchor_target[:4]);gray=report_metrics(anchor_pred[4:260],anchor_target[4:260])
   validation_cost=display_cost_rows(native/16383,t[valid]/16383,0)
   balanced_validation_rgb=np.sqrt(validation_mean(validation_cost))
   group_scores=[balanced_validation_rgb,primary['rmse_8bit'],gray['rmse_8bit']]
   if len(mandatory)==284:
    cc24=report_metrics(anchor_pred[260:284],anchor_target[260:284]);group_scores.append(cc24['rmse_8bit']);history[-1]['colorchecker24_training']=cc24
   if sector_audit:
    sector_metrics=report_metrics(anchor_pred[len(mandatory):],anchor_target[len(mandatory):]);group_scores.append(sector_metrics['rmse_8bit']);history[-1]['sector16_training']=sector_metrics
   if tonal_ids is not None:
    anchor_cost=display_cost_rows(anchor_pred/16383,anchor_target/16383,0)
    anchor_bins=tonal_ids[train[len(random_train):]]
    slices=[slice(0,4),slice(4,260)]+([slice(260,284)] if len(mandatory)==284 else [])+([slice(len(mandatory),None)] if sector_audit else [])
    group_scores=[balanced_validation_rgb]+[np.sqrt(tonal_sampling.mean_cost(anchor_cost[sl],anchor_bins[sl])) for sl in slices]
   selection_rgb=composite_score(group_scores,importance)
   from perceptual import compare
   perceptual_groups=[float(np.sqrt(validation_mean(display_cost_rows(native/16383,t[valid]/16383,options['perceptual_weight']))))]
   for sl in [slice(0,4),slice(4,260)]+([slice(260,284)] if len(mandatory)==284 else [])+([slice(len(mandatory),None)] if sector_audit else []):
    perceptual_groups.append(float(np.sqrt(tonal_sampling.mean_cost(display_cost_rows(anchor_pred[sl]/16383,anchor_target[sl]/16383,options['perceptual_weight']),tonal_ids[train[len(random_train):]][sl] if tonal_ids is not None else None))))
   selection=composite_score(perceptual_groups,importance)
   smoothing_cost=native_cost(params,ctx.axis,options['parameter_smoothing'])+pc_cost(bundle,options['parameter_smoothing'])
   continuity_report=exact_continuity(params,report=True)
   continuity_cost=continuity_report['objective_cost_8bit_squared'] if continuity_report else 0.
   selection=float(np.sqrt(selection**2+smoothing_cost+continuity_cost))
   if continuity_report is not None:history[-1]['output_continuity']=continuity_report
   history[-1]['parameter_smoothing_cost_8bit_squared']=smoothing_cost
   history[-1].update(selection_rgb_score=selection_rgb,perceptual_validation=compare(t[valid]/16383,native/16383),training_group_weights=current_importance.copy())
   history[-1].update(primary_training=primary,gray_training=gray,selection_score=selection,candidate_domain='combined-PC' if a.pc_compensation else 'native')
   history[-1]['pc_grid_fitting']=bundle[2] if bundle else None
   native_gray=report_metrics(center_mean(render_native(exact,current_x[gray_indices])),t[gray_indices])['rmse_8bit']
   candidates.append(dict(gray=gray['rmse_8bit'],native_gray=native_gray,color=selection,vector=v.copy(),label=candidate_label,pc=bundle,params=params,importance=current_importance.copy(),wb=wb_value.copy()))
 def regularization(v):
  rows=native_rows(v[8:104],smooth.gamma(v)*16,ctx.axis,options['parameter_smoothing'])
  if continuity_bank is not None:
   rows=np.r_[rows,continuity_bank.rows(continuity_model.render(v)/16383,options['output_continuity'])]
  return rows*np.sqrt(len(train))
 def residual(v):
  nonlocal calls;calls+=1
  data=(smooth_loss_rows(corrected(smooth.render(v),active_pc)/16383,t[train]/16383,options["perceptual_weight"])*np.sqrt(group_weights)[:,None]).ravel()
  c=v[8:104].reshape(6,16);reg=(np.roll(c,1,axis=1)-2*c+np.roll(c,-1,axis=1)).ravel()*.003
  return np.r_[data,reg,(v[:8]-start[:8])*.003,regularization(v)]
 def make_gpu(mode='joint',fixed=None,indices=slice(None),reference=None):
  from gpu_optimizer import StageObjective
  return StageObjective(smooth,gray_model,t[train],t[gray_indices],group_weights,start,active_pc,
      options['perceptual_weight'],options['parameter_smoothing'],mode=mode,fixed=fixed,indices=indices,reference=reference)
 if a.refine_from:
  source=a.refine_from.resolve()
  previous=json.loads((source/'fit/recipe.json').read_text())
  identity=previous['source']
  if identity['pairs_sha256']!=sha(a.pairs) or identity['capture_report_sha256']!=sha(a.capture/'report.json') or identity['context']!=a.context:
   raise ValueError('Refinement requires identical pairs and native capture')
  if previous.get('white_balance',{}).get('enabled'):
   raise ValueError('White balance refinement is not supported by this continuation')
  if previous['fitting']['group_total_weights']!=importance or previous['fitting']['search_options']['parameter_smoothing']!=options['parameter_smoothing']:
   raise ValueError('Refinement must preserve cohort weights and smoothing')
  warm=np.load(source/'fit/fit_state.npz')['vector']
  baseline_relax=report_metrics(models['valid'].render(start),center_mean(render_native(ctx.base,x[valid])))
  prior=previous['parameters']
  native=dict(matrix_payload=bytes.fromhex(prior['matrix_780f_hex']),cc1=np.array(prior['cc1_direct_raw']),gamma_y=np.array(prior['gamma_7806_y']))
  assess(warm,'previous-AS-exact-integer',params_override=native)
  assess(warm,'previous-AS-continuous-seed')
 else:
  assess(start,'baseline')
  baseline_relax=report_metrics(models['valid'].render(start),center_mean(render_native(ctx.base,x[valid])))
  # Starting curve is a train-only monotone shared curve; all 128 native knots
  # remain on their original x coordinates. Positive increments avoid collapse.
  from fit_native_proxy import curve_fit
  z=center_mean(ctx.base.matrix16(x[gray_indices]));curve=curve_fit(z/16383,t[gray_indices]/16383,ctx.axis/128/16383)
  yi=np.maximum.accumulate(np.maximum(curve,0))*16383;inc=np.maximum(np.diff(yi[smooth.knots]),1.)
  seed=start.copy();seed[104:]=np.log(np.r_[inc,max(16383-yi[-1],1.)]);assess(seed,'monotone-seed')
  # Tone-first block: optimize Gamma only, match encoded gray luma, leave
  # CC1 and block13 fixed; common gamma is still a native shared curve.
  monotone_seed=seed.copy()
  from apple_gpu import initialize
  progress.update(stage='Apple GPU 起点预优化',iteration=0)
  gpu_seed,gpu_audit=initialize(smooth,monotone_seed,t[train],group_weights,lb,ub,
      steps=(600 if a.fast else min(600,a.evaluations)),perceptual_weight=options['perceptual_weight'],
      parameter_smoothing=options['parameter_smoothing'],progress=progress.update)
  tone_seed=seed.copy()
  def tone_residual(g):
   v=tone_seed.copy();v[104:]=g
   pred=gray_model.render(v)
   return np.r_[((pred-t[gray_indices])@pc_stages.LUMA)/16383,
                np.diff(g,n=2)*.0002,regularization(v)]
  tone_fit=progress.solve(least_squares,'灰阶明暗 Gamma',tone_residual,np.clip(seed[104:],lb[104:]+1e-5,ub[104:]-1e-5),
   bounds=(lb[104:],ub[104:]),max_nfev=a.evaluations,ftol=2e-5,xtol=2e-5,gtol=1e-6,diff_step=1e-4,gpu_objective=lambda:make_gpu('tone',tone_seed,slice(104,None)))
  seed[104:]=tone_fit.x;assess(seed,'native-gray-tone-gamma-only')
  if not a.fast or gpu_seed is None:
   # Train-only preconditioning avoids fitting gray from an arbitrary color matrix.
   precondition=progress.solve(least_squares,'搜索起点 1',residual,np.clip(seed,lb+1e-5,ub-1e-5),bounds=(lb,ub),
    max_nfev=a.evaluations,ftol=2e-5,xtol=2e-5,gtol=1e-6,diff_step=1e-4,gpu_objective=lambda:make_gpu())
   assess(precondition.x,'train-precondition-tone')
   # Keep a second train-only initialization from the original monotone seed.
   # A specialized luma optimum can be a poor color initialization.
   original_precondition=progress.solve(least_squares,'搜索起点 2',residual,np.clip(monotone_seed,lb+1e-5,ub-1e-5),bounds=(lb,ub),
    max_nfev=a.evaluations,ftol=2e-5,xtol=2e-5,gtol=1e-6,diff_step=1e-4,gpu_objective=lambda:make_gpu())
   assess(original_precondition.x,'train-precondition')
   starts=[precondition,original_precondition]
  else:
   starts=[]
  if gpu_seed is not None:
   # One bounded correction of the additional GPU start, not a duplicate of
   # every CPU stage. Keep both exact candidates so correction cannot regress
   # the final native-integer selection.
   assess(gpu_seed,'Metal-direct-candidate')
   progress.value['total_rounds']+=1
   correction_started=time.perf_counter()
   gpu_fit=progress.solve(least_squares,'GPU 起点浮点校正（最多32次评估）',residual,gpu_seed,bounds=(lb,ub),
    max_nfev=min(32,a.evaluations),ftol=2e-5,xtol=2e-5,gtol=1e-6,diff_step=1e-4)
   gpu_audit.update(cpu_float64_refit=True,cpu_correction_seconds=time.perf_counter()-correction_started,
       cpu_correction_evaluations=int(gpu_fit.nfev),cpu_correction_limit=min(32,a.evaluations))
   assess(gpu_fit.x,'Metal-initialized-CPU-corrected');starts.append(gpu_fit)
  for i,trial in enumerate(perturbed_starts(monotone_seed,0 if a.fast and gpu_seed is not None else max(0,options['starts']-2),lb,ub)):
   solved=progress.solve(least_squares,'搜索起点 '+str(i+3),residual,trial,bounds=(lb,ub),max_nfev=a.evaluations,ftol=2e-5,xtol=2e-5,gtol=1e-6,diff_step=1e-4,gpu_objective=lambda:make_gpu())
   assess(solved.x,'multi-start-'+str(i+3));starts.append(solved)
  precondition=min(starts,key=lambda result:np.sum(residual(result.x)**2))
  reference_colors=smooth.render(precondition.x)
  def gray_residual(v):
   nonlocal calls;calls+=1
   return np.r_[(gray_model.render(v)-t[gray_indices]).ravel()/16383,
                 (v[:104]-start[:104])*.0001,
                 (smooth.render(v)-reference_colors).ravel()/16383*.5,regularization(v)]
  # Gray stage preserves the train-only initialized color response to avoid unconstrained hue collapse.
  initial=select_balanced(candidates)['vector']
  begin=time.time();gray_fit=progress.solve(least_squares,'灰阶候选微调',gray_residual,np.clip(initial,lb+1e-5,ub-1e-5),
   bounds=(lb,ub),max_nfev=a.evaluations,ftol=2e-5,xtol=2e-5,gtol=1e-6,diff_step=1e-4,gpu_objective=lambda:make_gpu('gray',reference=reference_colors))
  assess(gray_fit.x,'gray-refinement-candidate');history[-1].update(seconds=time.time()-begin,nfev=gray_fit.nfev)
  # Chroma block: freeze Gamma; fit CC1 and block13 against target
  # chroma while retaining gray-luma and initialized color response.
  chroma_seed=gray_fit.x.copy()
  def chroma_residual(c):
   v=chroma_seed.copy();v[:104]=c
   pred=smooth.render(v);delta=(pred-t[train])/16383
   dy=delta@pc_stages.LUMA;chroma=delta-dy[:,None]
   gy=(gray_model.render(v)-t[gray_indices])@pc_stages.LUMA/16383
   return np.r_[(chroma*np.sqrt(group_weights)[:,None]).ravel(),gy,
                (pred-reference_colors).ravel()/16383*.1,(c-start[:104])*.0001,regularization(v)]
  chroma_fit=progress.solve(least_squares,'CC1 / block13 色彩',chroma_residual,np.clip(chroma_seed[:104],lb[:104]+1e-5,ub[:104]-1e-5),
   bounds=(lb[:104],ub[:104]),max_nfev=a.evaluations,ftol=2e-5,xtol=2e-5,gtol=1e-6,diff_step=1e-4,gpu_objective=lambda:make_gpu('chroma',chroma_seed,slice(0,104),reference_colors))
  chroma_seed[:104]=chroma_fit.x;assess(chroma_seed,'native-chroma-cc1-block13-gamma-frozen')
  joint_seed=select_balanced(candidates)
  active_pc=joint_seed['pc']
  begin=time.time();joint_fit=progress.solve(least_squares,'联合优化',residual,np.clip(joint_seed['vector'],lb+1e-5,ub-1e-5),
   bounds=(lb,ub),max_nfev=a.evaluations,ftol=2e-5,xtol=2e-5,gtol=1e-6,diff_step=1e-4,gpu_objective=lambda:make_gpu())
  assess(joint_fit.x,'weighted-joint');history[-1].update(seconds=time.time()-begin,nfev=joint_fit.nfev)
  # Evaluate integer-quantized blends with the fixed user scoring rule.
  for alpha in [.75,.5,.25,.125,.0625]:
   assess(joint_seed['vector']+alpha*(joint_fit.x-joint_seed['vector']),'joint-blend-'+str(alpha))
 # Precision-first: complete training population, followed by two hard-region
 # passes. Validation chooses candidates; the complete test set is untouched.
 if precision and not a.refine_from and not a.fast:
  random_selection=np.flatnonzero((split=='train')&(p['anchor_index']<0)&(sector_ids<0))
  train,mandatory,random_train,group_weights=training_plan(split,p['anchor_index'],importance,sector_ids,tonal_ids,random_selection,p.get('sample_kind'),options)
  gray_mask=(p['anchor_index'][train]>=4)&(p['anchor_index'][train]<260)
  gray_indices=train[len(random_train)+4:len(random_train)+260]
  strata=precision_sampling.bins(p['design_srgb'][train])
  for precision_round in range(3):
   chosen=select_balanced(candidates);set_wb(chosen['wb']);active_pc=chosen['pc']
   _,_,_,group_weights=training_plan(split,p['anchor_index'],importance,sector_ids,tonal_ids,random_selection,p.get('sample_kind'),options)
   if precision_round:
    pred=corrected(center_mean(render_native(ctx.build(**chosen['params']),current_x[train])),active_pc)/16383
    errors=display_cost_rows(pred,t[train]/16383,options['perceptual_weight'])
    hard=precision_sampling.hard_weights(errors,strata)
    n=len(random_train)
    for sl in [slice(0,n),slice(n,n+4),slice(n+4,n+260),slice(n+260,n+len(mandatory))]+([slice(n+len(mandatory),None)] if sector_audit else []):
     old_mass=group_weights[sl].sum();group_weights[sl]*=hard[sl]
     group_weights[sl]*=old_mass/group_weights[sl].sum()
   update=progress.solve(least_squares,'全量精训' if precision_round==0 else '高误差分层补训 '+str(precision_round),residual,np.clip(chosen['vector'],lb+1e-5,ub-1e-5),bounds=(lb,ub),max_nfev=a.evaluations,ftol=1e-7,xtol=1e-7,gtol=1e-8,diff_step=1e-4,gpu_objective=lambda:make_gpu())
   assess(update.x,'precision-full-'+str(precision_round))
   sampling_audit['stages'].append(dict(round=precision_round,training_samples=len(train),random_samples=len(random_train),hard_mining=bool(precision_round),nfev=update.nfev))
 # Alternate native parameters against frozen train-only compensation,
 # then rebuild compensation from exact integer outputs for assessment.
 if a.pc_compensation and not a.refine_from:
  for round_index in range(2):
   chosen=select_balanced(candidates);active_pc=chosen['pc']
   update=progress.solve(least_squares,'原生与 PC 交替 '+str(round_index+1),residual,np.clip(chosen['vector'],lb+1e-5,ub-1e-5),bounds=(lb,ub),
    max_nfev=a.evaluations,ftol=2e-5,xtol=2e-5,gtol=1e-6,diff_step=1e-4,gpu_objective=lambda:make_gpu())
   assess(update.x,'integrated-native-PC-alternation-'+str(round_index+1))
 # Alternate Gamma and CC1/block13 with one common weighted objective.
 # Full training data, fixed PC inside each round; exact assessment rebuilds PC.
 alternation_history=[]
 if options['gamma_color_rounds']:
  from native_alternation import solve_round
  for round_index in range(options['gamma_color_rounds']):
   chosen=select_balanced(candidates);set_wb(chosen['wb']);active_pc=chosen['pc']
   current_importance=importance.copy()
   _,_,_,group_weights=training_plan(split,p['anchor_index'],importance,sector_ids,tonal_ids,random_selection,p.get('sample_kind'),options)
   updated,blocks=solve_round(chosen['vector'],residual,lb,ub,
    lambda stage,*args,**kwargs:progress.solve(least_squares,stage,*args,**kwargs),
    a.evaluations,round_index+1,gpu_factory=lambda frozen,indices:make_gpu(fixed=frozen,indices=indices))
   assess(updated,'gamma-cc1-block13-alternation-'+str(round_index+1))
   alternation_history.append(dict(round=round_index+1,blocks=blocks,
    exact_selection_score=history[-1]['selection_score'],pc_rebuilt=bool(a.pc_compensation)))
 # WB outer block and native inner block share fixed targets and train-only PC.
 if a.white_balance:
  for wb_round in range(3):
   chosen=select_balanced(candidates);set_wb(chosen['wb']);active_pc=chosen['pc']
   exact=ctx.build(**chosen['params'])
   progress.update(stage='白平衡联合搜索 '+str(wb_round+1),round=progress.value['round']+1,state='running',evaluations=0,iteration=0,max_evaluations=max(60,a.evaluations*12))
   wb_calls=[0]
   def wb_cost(z):
    value=wb.validate(dict(temperature_shift=z[0],tint=z[1]))
    front=wb.inputs(ctx.base,x[train],p['sensor_codes'][train],value)
    prediction=corrected(center_mean(render_native(exact,front)),active_pc)/16383
    costs=display_cost_rows(prediction,t[train]/16383,options['perceptual_weight'])
    wb_calls[0]+=1
    if wb_calls[0]%5==0:progress.update(evaluations=wb_calls[0])
    penalty=0.
    if continuity_bank is not None:
     probes=continuity_bank.inputs(ctx.base,value)
     penalty=continuity_bank.cost(center_mean(render_native(exact,probes))/16383,options['output_continuity'])
    return float(costs@group_weights/group_weights.sum())+penalty+0.01*((value['temperature_shift']/1000)**2+(value['tint']/50)**2)
   solved=minimize(wb_cost,[wb_value['temperature_shift'],wb_value['tint']],method='Powell',bounds=[(-1000,1000),(-50,50)],options=dict(maxiter=max(2,a.evaluations),maxfev=max(60,a.evaluations*12),xtol=.5,ftol=1e-5))
   set_wb(dict(temperature_shift=solved.x[0],tint=solved.x[1]));assess(chosen['vector'],'WB-search-'+str(wb_round+1),params_override=chosen['params'])
   chosen=select_balanced(candidates);set_wb(chosen['wb']);active_pc=chosen['pc']
   updated=progress.solve(least_squares,'白平衡与原生联合 '+str(wb_round+1),residual,np.clip(chosen['vector'],lb+1e-5,ub-1e-5),bounds=(lb,ub),max_nfev=a.evaluations,ftol=2e-5,xtol=2e-5,gtol=1e-6,diff_step=1e-4,gpu_objective=lambda:make_gpu())
   assess(updated.x,'WB-native-PC-joint-'+str(wb_round+1))
 # Dynamic weights derive only from exact training errors, never validation/test.
 for round_index in range(0 if a.refine_from else options['adaptive_rounds']):
  chosen=select_balanced(candidates);set_wb(chosen['wb']);active_pc=chosen['pc']
  predicted=corrected(center_mean(render_native(ctx.build(**chosen['params']),current_x[train])),active_pc)/16383
  costs=display_cost_rows(predicted,t[train]/16383,options['perceptual_weight'])
  n=len(random_train);slices=[slice(0,n),slice(n,n+4),slice(n+4,n+260),slice(n+260,n+len(mandatory))]+([slice(n+len(mandatory),None)] if sector_audit else [])
  errors={name:float(np.sqrt(tonal_sampling.mean_cost(costs[sl],tonal_ids[train[sl]] if tonal_ids is not None else None))) if len(costs[sl]) else 0 for name,sl in zip(('random','primaries','gray','colorchecker24','sector16'),slices)}
  current_importance=adaptive_importance(importance,errors)
  _,_,_,group_weights=training_plan(split,p['anchor_index'],current_importance,sector_ids,tonal_ids,random_selection,p.get('sample_kind'),options)
  adaptive_history.append(dict(round=round_index+1,training_errors=errors,weights=current_importance.copy()))
  update=progress.solve(least_squares,'动态权重 '+str(round_index+1),residual,np.clip(chosen['vector'],lb+1e-5,ub-1e-5),bounds=(lb,ub),max_nfev=a.evaluations,ftol=2e-5,xtol=2e-5,gtol=1e-6,diff_step=1e-4,gpu_objective=lambda:make_gpu())
  assess(update.x,'adaptive-round-'+str(round_index+1))
 # Exact quantized neighborhood search, then refit PC and compare with all originals.
 quantization_audit=None
 if options['quantization_sweeps']:
  chosen=select_balanced(candidates);set_wb(chosen['wb']);current_importance=chosen['importance'].copy()
  _,_,_,group_weights=training_plan(split,p['anchor_index'],current_importance,sector_ids,tonal_ids,random_selection,p.get('sample_kind'),options)
  refined,quantization_audit=refine_native(ctx,chosen['params'],current_x[train],t[train]/16383,group_weights,chosen['pc'],options['quantization_sweeps'],options['perceptual_weight'],progress=lambda **v:progress.update(stage='量化后原生参数微调',**v),parameter_smoothing=options['parameter_smoothing'],output_penalty=exact_continuity if continuity_bank is not None else None)
  assess(chosen['vector'],'integer-refinement',params_override=refined)
  if a.pc_compensation:
   assess(chosen['vector'],'integer-refinement-PC',params_override=refined,quantize=True)
   assess(chosen['vector'],'PC-integer-refinement',params_override=chosen['params'],quantize=True)
 chosen=select_balanced(candidates);set_wb(chosen['wb'])
 best=[chosen['color'],chosen['vector'],chosen['label']]
 fitted=best[1];params=chosen["params"];model=ctx.build(**params)
 exact_before=center_mean(render_native(ctx.base,x[test]));exact_after=center_mean(render_native(model,current_x[test]))
 result=dict(white_balance=wb.report(wb_value,a.white_balance),schema='r5-edit-native-color-fit/1',complete_edit_fitter=False,camera_apply_allowed=False,renderer='measured-Edit-color-subchain-with-native-matrix-builder',input_domain='Edit post-SSCS/pre-matrix integer RGB',output_domain='14-bit encoded RGB',target_description=a.target_description or ['integer RAW -> RawAlchemy S-Gamut3 S-Log3 cube','integer RAW -> RawAlchemy S-Gamut3.Cine S-Log3 cube'][a.gamut],
  additional_compensation_matrix_enabled=False,compensation_grid_enabled=False,photo_pixels_used_for_fitting=False,
  source=dict(capture_report_sha256=sha(a.capture/'report.json'),context=a.context,runtime_sha256=hashlib.sha256(ctx.base.runtime).hexdigest(),raw_sha256=hashlib.sha256(ctx.base.raw).hexdigest(),settings_sha256=hashlib.sha256(ctx.base.settings).hexdigest(),pairs_sha256=sha(a.pairs)),
  parameters=dict(matrix_780f_hex=params['matrix_payload'].hex(),cc1_direct_raw=params['cc1'].tolist(),gamma_7806_y=params['gamma_y'].tolist(),gamma_7805_x=ctx.axis.tolist()),
  fitting=dict(tonal_balance=tonal_audit,training_pipeline=(['experimental-WB-native-PC-alternation'] if a.white_balance else [])+['native-gray-tone-gamma-only','native-color-initialization','native-gray-refinement','native-chroma-cc1-block13-gamma-frozen','native-joint','multi-start','train-only-dynamic-weight','exact-integer-refinement']+(['native-PC-alternation','exact-integer-PC-refit'] if a.pc_compensation else []),search_options=options,pc_options=pc_policy,adaptive_history=adaptive_history,quantization_refinement=quantization_audit,selected_training_weights=chosen["importance"],selected_pc_quantization_sweeps=chosen["pc"][2].get("quantization_sweeps",0) if chosen["pc"] else 0,pc_compensation_training=a.pc_compensation,pc_grid_strategy=chosen["pc"][2]["strategy"] if chosen["pc"] else None,candidate_domain='combined-PC' if a.pc_compensation else 'native',gamma_optimized_points=128,gamma_fixed_zero=True,gamma_final_ordinate_fixed=False,native_point128_policy="separate export endpoint, absent from RAW context",anchor_training_samples=len(mandatory),sector16_training_samples=sector_audit['samples'] if sector_audit else 0,sector16=sector_audit,colorchecker24_training_samples=max(0,len(mandatory)-260),gray_training_samples=256,primary_training_samples=4,random_training_samples=len(random_train),loss_groups='user cohort total squared weights; specialized stages are optional candidates',group_total_weights=importance,selection='fixed user-weighted composite of uint8 RGB MSE + perceptual_weight*(2.55*DE00)^2; training adaptation cannot change ranking rule; independent test excluded; optional parameter smoothness penalty',gray_priority=False,training_samples=len(train),validation_samples=len(valid),test_samples=len(test),history=history,selected=best[2],calls=calls,baseline_relaxation_error=baseline_relax,monotone_positive_increment_Gamma=True),
  anchor_training=dict(before=report_metrics(center_mean(render_native(ctx.base,x[mandatory])),t[mandatory]),after=report_metrics(center_mean(render_native(model,current_x[mandatory])),t[mandatory])),
  heldout=dict(before=report_metrics(exact_before,t[test]),after=report_metrics(exact_after,t[test]),relaxation_vs_quantized=report_metrics(models['test'].render(fitted),exact_after)),
  full_chain_status=('Experimental WB uses flatfield ITP plus frozen measured frontend residual; Vatr/SSCS WB response is approximate.' if a.white_balance else 'New synthetic RAW frontend measured before matrix; verified original ST color subchain reused; new chart full JPEG not verified.'),
  limitations=['Continuous model only initializes; heldout results use integer model.','New capture contributes only pre-matrix input, never its current-look output.','New chart full JPEG and photographs require independent Edit validation.','No global optimum or arbitrary LUT exact-representation claim.'])
 result['fitting']['gamma_color_alternation']=alternation_history
 if continuity_bank is not None:
  result['fitting']['output_continuity']=exact_continuity(params,report=True)
  result['fitting']['training_pipeline'].append('native-output-continuity')
 if a.refine_from:
  result['fitting']['continued_from']=dict(job=str(a.refine_from),recipe_sha256=sha(a.refine_from/'fit/recipe.json'))
  result['fitting']['training_pipeline']=['previous-exact-native-seed','gamma-cc1-block13-alternation','exact-integer-refinement']
 elif alternation_history:result['fitting']['training_pipeline'].append('gamma-cc1-block13-alternation')
 result['fitting']['precision_sampling']=sampling_audit
 result['fitting']['convergence']=progress.convergence
 result['fitting']['gradient_workers']=progress.gradient_workers
 result['fitting']['speed_priority']=a.fast
 if a.fast and sampling_audit:sampling_audit['policy']='speed priority: complete tonal tracks + H/S/Y coarse; no full-training hard-mining; complete heldout evaluation'
 result['fitting']['gpu_initialization']=gpu_audit
 result['fitting']['compute_backend']=__import__('gpu_runtime').policy()
 result['source']['dataset_id']=str(p['dataset_id']) if 'dataset_id' in p else 'legacy'
 result['source']['patch_sampling']=__import__('patch_sampling').POLICY
 if result['source']['dataset_id']==__import__('baseline').V45_ID:
  result['full_chain_status']='v4.5 5300K WB-compensated RAW -> simulated ITP/SSCS, original verified PT downstream context retained. New full Edit context has not been independently captured. Spatial and photograph frontend remain approximate.'
 else:
  result['full_chain_status']='Source-bound native integer color subchain. Unity-WB chart uses simulated ITP/SSCS inputs verified against independent Edit PT capture. Spatial processing and photograph frontend remain outside this validation.'
 result['fitting']['selection']='Fixed weighted floating RGB MSE + continuous DE00 on integer native outputs; full validation; full independent test excluded from all optimization and selection'
 if continuity_bank is not None:result['fitting']['selection']+='; output-space continuity penalty on fixed target-independent probes'
 (a.output/'recipe.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');np.savez(a.output/'fit_state.npz',vector=fitted,start=start,test_prediction=exact_after)
 progress.update(stage='原生拟合完成',state='done')
 print(json.dumps(result['heldout'],indent=2),flush=True)
if __name__=='__main__':main()
