"""Optional Metal/autograd initializer. CPU float64 and native integer stages
remain authoritative; no GPU result bypasses the normal candidate evaluation.
"""
import numpy as np


class SmoothGPU:
    def __init__(self, smooth, device='mps', dtype=None):
        import torch
        self.torch=torch
        self.device=device
        def tensor(x,integer=False):
            return torch.as_tensor(np.array(x,copy=True),device=device,
                dtype=torch.int64 if integer else (torch.float32 if dtype is None else dtype))
        self.tensor=tensor
        for key in ('x','axis','wl','wr','scales','diag','threshold','weights','area','ytable'):
            setattr(self,key,tensor(getattr(smooth,key)))
        self.left=tensor(smooth.left,True);self.right=tensor(smooth.right,True)
        self.quadratic=smooth.quadratic;self.chroma=smooth.chroma
        self.area_selector=bool(smooth.ctx.base.area_controls[64])
        self.pivot=smooth.pivot;self.ygain=smooth.ygain

    def gamma(self,v):
        t=self.torch
        return t.cat([v.new_zeros(1),t.cumsum(t.softmax(v[104:],dim=0),dim=0)[:-1]])*16383

    def interp(self,values,axis,ordinates):
        t=self.torch
        # searchsorted is piecewise constant, interpolation keeps the useful
        # derivative with respect to both sample values and Gamma ordinates.
        at=t.searchsorted(axis.contiguous(),values.contiguous()).clamp(1,len(axis)-1)
        fraction=((values-axis[at-1])/(axis[at]-axis[at-1])).clamp(0,1)
        return ordinates[at-1]*(1-fraction)+ordinates[at]*fraction

    def render(self,v):
        t=self.torch;c=v[8:104].reshape(6,16)
        q=c[:,self.left].permute(1,2,0)*self.wl[:,:,None]+c[:,self.right].permute(1,2,0)*self.wr[:,:,None]
        r,g,b=self.x.unbind(-1);a,bb,cc,d,e,f=q.unbind(-1)
        linear=t.stack([(a+bb+self.diag[0])*r-a*g-bb*b,-cc*r+(cc+d+self.diag[1])*g-d*b,-e*r-f*g+(e+f+self.diag[0])*b],dim=-1)
        if self.quadratic:
            z=c[:,self.left].permute(1,2,0)*(self.wl*self.scales[self.left])[:,:,None]+c[:,self.right].permute(1,2,0)*(self.wr*self.scales[self.right])[:,:,None]
            a,bb,cc,d,e,f=z.unbind(-1);r,g,b=r*r,g*g,b*b
            n=t.stack([(-a-bb)*r+a*g+bb*b,cc*r+(-cc-d)*g+d*b,e*r+f*g+(-e-f)*b],dim=-1)/16384
            linear=linear+t.where(n>=0,(n-self.threshold).clamp(min=0),0)
        rgb=self.interp(linear.clamp(0,16383),self.axis,self.gamma(v)).reshape(-1,3)
        dr=rgb[:,0]-rgb[:,1];db=rgb[:,2]-rgb[:,1]
        cr=dr+db*t.where(db>=0,v[0],v[2]);cb=db+dr*t.where(dr>=0,v[1],v[3])
        cr=(cr*.5*t.where(cr>=0,v[5],v[7])).clamp(-8192,8191)
        cb=(cb*.5*t.where(cb>=0,v[4],v[6])).clamp(-8192,8191)
        y=rgb@self.weights
        c=self.area;x1,y1=c[0]+cr,c[1]+cb;x2,y2=c[2]+cr,c[3]+cb
        u=t.minimum((y1*c[6]+x1*c[4]).clamp(min=0),(c[7]*y1+c[5]*x1).clamp(min=0))
        vv=t.minimum((y2*c[10]+x2*c[8]).clamp(min=0),(c[11]*y2+c[9]*x2).clamp(min=0))
        if self.area_selector:u=t.minimum(u,vv);vv=t.zeros_like(vv)
        cr=cr+u*c[12]+vv*c[14];cb=cb+u*c[13]+vv*c[15]
        c=self.chroma
        amount=t.where(y<c['low_cutoff'],(c['low_cutoff']-y)*c['low_slope'],(y-c['high_cutoff']).clamp(min=0)*c['high_slope'])
        factor=(255-amount/4096).clamp(0,255)/256;cr=cr*factor;cb=cb*factor
        at=y.clamp(0,len(self.ytable)-1);lo=at.long();hi=(lo+1).clamp(max=len(self.ytable)-1);w=at-lo
        y=self.ytable[lo]*(1-w)+self.ytable[hi]*w
        y=((y-self.pivot)*self.ygain+self.pivot).clamp(0,16383)
        out=t.stack([y+cr*1.402,y-cr*.7141-cb*.3441,y+cb*1.772],dim=-1)
        return out.clamp(0,16383).reshape(self.x.shape)[:,2:7].mean(dim=1)

    def lab(self,x):
        t=self.torch
        x=t.where(x<=.04045,x/12.92,((x+.055)/1.055).clamp(min=0)**2.4)
        matrix=self.tensor([[.4124564,.3575761,.1804375],[.2126729,.7151522,.0721750],[.0193339,.1191920,.9503041]])
        xyz=(x@matrix.T)/self.tensor([.95047,1,1.08883])
        # Clamp the inactive cube-root branch too, avoiding NaN gradients at 0.
        f=t.where(xyz>(6/29)**3,xyz.clamp(min=1e-12)**(1/3),xyz/(3*(6/29)**2)+4/29)
        return t.stack([116*f[:,1]-16,500*(f[:,0]-f[:,1]),200*(f[:,1]-f[:,2])],dim=1)


def initialize(smooth,seed,target,weights,lower,upper,*,steps=600,
               perceptual_weight=.35,parameter_smoothing=30,progress=None):
    """Additional train-only start; absence/failure leaves every CPU start intact."""
    try:
        import torch
    except ImportError:
        return None,dict(enabled=False,reason='PyTorch optional dependency is unavailable')
    if not torch.backends.mps.is_available():
        return None,dict(enabled=False,reason='Apple Metal/MPS is unavailable')
    torch.set_num_threads(8)
    try:
        gpu=SmoothGPU(smooth);tensor=gpu.tensor
        continuity=None
        if getattr(smooth,'output_continuity',None) is not None:
            from output_continuity import TensorPenalty
            bank,probe_model,amount=smooth.output_continuity
            probe_gpu=SmoothGPU(probe_model)
            continuity=TensorPenalty(bank,probe_gpu,amount)
        # Verify the full coarse training batch before permitting any GPU start.
        initial=gpu.render(tensor(seed)).detach().cpu().numpy()
        error=float(np.max(np.abs(initial-smooth.render(seed))))
        if not np.isfinite(error) or error>.08:
            raise ValueError(f'Metal renderer verification failed: {error} native codes')
        y=tensor(target/16383);mass=tensor(weights/np.sum(weights))
        target_lab=gpu.lab(y).detach()
        v=tensor(seed).requires_grad_(True);lo=tensor(lower+1e-5);hi=tensor(upper-1e-5)
        optimizer=torch.optim.Adam([v],lr=.015)
        best=None;best_loss=float('inf');before=None
        def objective():
            pred=gpu.render(v)/16383
            loss=(((pred-y)**2).mean(dim=1)*mass).sum()
            if perceptual_weight:
                loss=loss+(((gpu.lab(pred)-target_lab)/100)**2).sum(dim=1).mul(mass).sum()*perceptual_weight
            coeff=v[8:104].reshape(6,16)
            curvature=torch.roll(coeff,1,1)-2*coeff+torch.roll(coeff,-1,1)
            dx=torch.diff(gpu.axis/gpu.axis[-1]);gy=gpu.gamma(v)/16383
            gc=torch.diff(torch.diff(gy)/dx)*(dx[:-1]+dx[1:])/2
            loss=loss+(curvature.square().mean()*.02**2+gc.square().mean()*16**2)*(parameter_smoothing/100)
            if continuity is not None:loss=loss+continuity.loss(probe_gpu.render(v)/16383)
            return loss
        for step in range(steps):
            optimizer.zero_grad(set_to_none=True);loss=objective()
            value=float(loss.detach().cpu())
            if not np.isfinite(value):raise ValueError('Nonfinite Metal loss')
            if before is None:before=value
            if value<best_loss:best_loss=value;best=v.detach().cpu().numpy().astype(float)
            if progress and step%25==0:progress(iteration=step+1,evaluations=step+1,max_evaluations=steps,gpu_backend='Apple Metal/MPS',gpu_loss=value)
            loss.backward()
            if not bool(torch.isfinite(v.grad).all().cpu()):raise ValueError('Nonfinite Metal gradient')
            optimizer.step()
            with torch.no_grad():v.clamp_(lo,hi)
        result=dict(enabled=True,backend='Apple Metal/MPS',precision='float32 train-only initialization',
            steps=steps,renderer_max_error_native=error,loss_before=before,loss_after=best_loss,
            final_acceptance='native integer candidate evaluation; one bounded CPU correction, original GPU candidate retained')
        return best,result
    except (RuntimeError,ValueError,NotImplementedError) as error:
        return None,dict(enabled=False,reason=str(error),fallback='all CPU starts retained')
    finally:
        torch.mps.empty_cache()
