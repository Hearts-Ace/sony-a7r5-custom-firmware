"""Synthetic complete-chain native parameter fitting, no residual or extra matrix.

Actual Edit supplies the synthetic RAW frontend and full output oracle. A
continuous relaxation initializes native CC1/block13/Gamma, then actual integer
parameters are evaluated separately. Test colors never select parameters.
"""
from pathlib import Path
import argparse,hashlib,json,struct,sys,time
import numpy as np
from edit_parameter_context import ParameterContext,RuntimeColor,np,quantize_matrix_coefficients
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor/fit_eval_python312'))
from scipy.optimize import least_squares
from scipy.special import softmax
from fit_edit_native import metrics
from edit_native_model import decode_matrix16

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

class SmoothNative:
 def __init__(self,ctx,x):
  self.ctx=ctx;self.x=np.asarray(x,dtype=float);cfg=ctx.base.config
  self.knots=np.unique(np.r_[0,np.arange(4,117,4),120,127]).astype(int)
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
  yi=np.r_[0,np.cumsum(softmax(v[104:]))]*16383
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
  return np.clip(out,0,16383).reshape(self.x.shape)[:,4]

def vector_for(ctx):
 c=np.array(struct.unpack_from('<96f',ctx.base.config,0x28));bits=(ctx.cc1[:4]&65535)>>2&511;m=np.where(bits>255,bits-512,bits)/256;g=((ctx.cc1[4:]&65535)>>3&255)/64
 knots=np.unique(np.r_[0,np.arange(4,117,4),120,127]).astype(int)
 increments=np.maximum(np.diff(ctx.gamma_y[knots]/16),.01)
 return np.r_[m,g,c,np.log(increments)]

def report_metrics(p,t):
 r=metrics(p,t);r.update(mae_8bit=r['mae_14bit_codes']/64,rmse_8bit=r['rmse_14bit_codes']/64,p95_8bit=r['p95_abs_14bit_codes']/64);return r

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('pairs',type=Path);ap.add_argument('--capture',type=Path,required=True);ap.add_argument('--context',type=int,default=4);ap.add_argument('--gamut',type=int,choices=[0,1],required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--evaluations',type=int,default=80);ap.add_argument('--target-description');a=ap.parse_args();a.output.mkdir(exist_ok=False)
 p=np.load(a.pairs);x=p['input'];t=p[str(a.gamut)+'_target'];split=p['split'];ctx=ParameterContext(RuntimeColor.from_capture(a.capture,a.context));start=vector_for(ctx)
 train=np.flatnonzero(split=='train');valid=np.flatnonzero(split=='valid');test=np.flatnonzero(split=='test')
 # Training subset is deterministic and selected without looking at targets.
 train=train[::2];models={k:SmoothNative(ctx,x[v]) for k,v in [('train',train),('valid',valid),('test',test)]}
 smooth=models['train'];lb=np.r_[np.full(4,-.999),np.full(4,.05),np.full(96,-6),np.full(len(start)-104,-14)]
 ub=np.r_[np.full(4,.996),np.full(4,3.98),np.full(96,6),np.full(len(start)-104,15)]
 calls=0;history=[];best=[float('inf'),start.copy(),'initial']
 def assess(v,label):
  params=smooth.params(v);native=ctx.build(**params).color_only(x[valid])[:,4]
  score=report_metrics(native,t[valid]);history.append(dict(label=label,validation=score));print(json.dumps(history[-1]),flush=True)
  if score['rmse_8bit']<best[0]:best[:]=[score['rmse_8bit'],v.copy(),label]
 def residual(v):
  nonlocal calls;calls+=1
  data=(smooth.render(v)-t[train]).ravel()/16383
  c=v[8:104].reshape(6,16);reg=(np.roll(c,1,axis=1)-2*c+np.roll(c,-1,axis=1)).ravel()*.003
  return np.r_[data,reg,(v[:8]-start[:8])*.003]
 assess(start,'baseline')
 baseline_relax=report_metrics(models['valid'].render(start),ctx.base.color_only(x[valid])[:,4])
 # Starting curve is a train-only monotone shared curve; all 128 native knots
 # remain on their original x coordinates. Positive increments avoid collapse.
 from fit_native_proxy import curve_fit
 z=ctx.base.matrix16(x[train])[:,4];curve=curve_fit(z/16383,t[train]/16383,ctx.axis/128/16383)
 yi=np.maximum.accumulate(np.maximum(curve,0))*16383;inc=np.maximum(np.diff(yi[smooth.knots]),1.)
 seed=start.copy();seed[104:]=np.log(inc);assess(seed,'monotone-seed')
 for label,initial in [('original',start),('monotone',seed)]:
  begin=time.time();r=least_squares(residual,np.clip(initial,lb+1e-5,ub-1e-5),bounds=(lb,ub),max_nfev=a.evaluations,ftol=2e-5,xtol=2e-5,gtol=1e-6,diff_step=1e-4,verbose=0)
  assess(r.x,label);history[-1].update(seconds=time.time()-begin,nfev=r.nfev,status=int(r.status),cost=float(r.cost))
 fitted=best[1];params=smooth.params(fitted);model=ctx.build(**params)
 exact_before=ctx.base.color_only(x[test])[:,4];exact_after=model.color_only(x[test])[:,4]
 result=dict(schema='r5-edit-native-color-fit/1',complete_edit_fitter=False,camera_apply_allowed=False,renderer='measured-Edit-color-subchain-with-native-matrix-builder',input_domain='Edit post-SSCS/pre-matrix integer RGB',output_domain='14-bit encoded RGB',target_description=a.target_description or ['integer RAW -> RawAlchemy S-Gamut3 S-Log3 cube','integer RAW -> RawAlchemy S-Gamut3.Cine S-Log3 cube'][a.gamut],
  additional_compensation_matrix_enabled=False,compensation_grid_enabled=False,photo_pixels_used_for_fitting=False,
  source=dict(capture_report_sha256=sha(a.capture/'report.json'),context=a.context,runtime_sha256=hashlib.sha256(ctx.base.runtime).hexdigest(),raw_sha256=hashlib.sha256(ctx.base.raw).hexdigest(),settings_sha256=hashlib.sha256(ctx.base.settings).hexdigest(),pairs_sha256=sha(a.pairs)),
  parameters=dict(matrix_780f_hex=params['matrix_payload'].hex(),cc1_direct_raw=params['cc1'].tolist(),gamma_7806_y=params['gamma_y'].tolist(),gamma_7805_x=ctx.axis.tolist()),
  fitting=dict(training_samples=len(train),validation_samples=len(valid),test_samples=len(test),history=history,selected=best[2],calls=calls,baseline_relaxation_error=baseline_relax,monotone_positive_increment_Gamma=True),
  heldout=dict(before=report_metrics(exact_before,t[test]),after=report_metrics(exact_after,t[test]),relaxation_vs_quantized=report_metrics(models['test'].render(fitted),exact_after)),
  full_chain_status='Synthetic RAW native frontend/JPEG oracle connected; fitted original Edit JPEG must be verified independently.',
  limitations=['Continuous model only initializes; heldout results use integer model.','Spatial/final native stages evaluated through original Edit exports, not assumed identity.','No global optimum or arbitrary LUT exact-representation claim.'])
 (a.output/'recipe.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');np.savez(a.output/'fit_state.npz',vector=fitted,start=start,test_prediction=exact_after)
 print(json.dumps(result['heldout'],indent=2),flush=True)
if __name__=='__main__':main()
