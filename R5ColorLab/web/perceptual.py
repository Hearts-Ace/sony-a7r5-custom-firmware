"""Display-only sRGB D65 metrics, after the same uint8 quantization as UI.

Lab/CIEDE2000 math reused from analysis/r5_fl_edit_comparison_20261017/compare.py.
These are not scene-referred or physical camera characterization metrics.
"""
import numpy as np

def to_lab(rgb):
    x = np.asarray(rgb, dtype=np.float64)/255
    x = np.where(x <= .04045, x/12.92, ((x+.055)/1.055)**2.4)
    xyz = x @ np.array([[.4124564,.3575761,.1804375],
                        [.2126729,.7151522,.0721750],
                        [.0193339,.1191920,.9503041]]).T
    xyz /= np.array([.95047,1,1.08883])
    f = np.where(xyz > (6/29)**3, np.cbrt(xyz), xyz/(3*(6/29)**2)+4/29)
    return np.stack([116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])],axis=-1)


def de2000(a, b):
    L1,a1,b1 = a.T; L2,a2,b2 = b.T
    C1=np.hypot(a1,b1); C2=np.hypot(a2,b2); Cm=(C1+C2)/2
    G=.5*(1-np.sqrt(Cm**7/(Cm**7+25**7)))
    ap1=(1+G)*a1; ap2=(1+G)*a2
    cp1=np.hypot(ap1,b1); cp2=np.hypot(ap2,b2)
    hp1=np.mod(np.degrees(np.arctan2(b1,ap1)),360)
    hp2=np.mod(np.degrees(np.arctan2(b2,ap2)),360)
    hp1=np.where(cp1==0,0,hp1); hp2=np.where(cp2==0,0,hp2)
    dl=L2-L1; dc=cp2-cp1
    dh=hp2-hp1
    dh=np.where(cp1*cp2==0,0,np.where(dh>180,dh-360,np.where(dh < -180,dh+360,dh)))
    dH=2*np.sqrt(cp1*cp2)*np.sin(np.radians(dh/2))
    lm=(L1+L2)/2; cm=(cp1+cp2)/2
    hm=np.where(cp1*cp2==0,hp1+hp2,np.where(np.abs(hp1-hp2)<=180,(hp1+hp2)/2,
        np.where(hp1+hp2<360,(hp1+hp2+360)/2,(hp1+hp2-360)/2)))
    T=1-.17*np.cos(np.radians(hm-30))+.24*np.cos(np.radians(2*hm))+.32*np.cos(np.radians(3*hm+6))-.20*np.cos(np.radians(4*hm-63))
    sl=1+.015*(lm-50)**2/np.sqrt(20+(lm-50)**2); sc=1+.045*cm; sh=1+.015*cm*T
    rt=-2*np.sqrt(cm**7/(cm**7+25**7))*np.sin(np.radians(60*np.exp(-((hm-275)/25)**2)))
    return np.sqrt((dl/sl)**2+(dc/sc)**2+(dH/sh)**2+rt*(dc/sc)*(dH/sh))



def compare(target, predicted):
    a,b=[np.floor(np.clip(v,0,1)*255+.5) for v in (target,predicted)]
    la,lb=to_lab(a),to_lab(b)
    de=de2000(la,lb)
    dl=lb[:,0]-la[:,0]
    tint=lb[:,1:]-la[:,1:]
    return dict(delta_e00_mean=float(de.mean()), delta_e00_p95=float(np.percentile(de,95)),
                lightness_rmse=float(np.sqrt(np.mean(dl**2))),
                ab_rmse=float(np.sqrt(np.mean(np.sum(tint**2,axis=1)))),
                interpretation='display sRGB, D65 Lab, quantized uint8; not calibrated scene colorimetry')
