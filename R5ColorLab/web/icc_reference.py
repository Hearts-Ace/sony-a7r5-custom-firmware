"""Independent matrix/TRC ICC test oracle; no LittleCMS or filesystem side effects."""
import struct
import numpy as np

def tags(raw):
    entries=[struct.unpack_from('>4sII',raw,132+12*i) for i in range(struct.unpack_from('>I',raw,128)[0])]
    return {sig:raw[start:start+size] for sig,start,size in entries}

def matrix_and_curves(raw):
    t=tags(raw)
    columns=[];curves=[]
    for ch in (b'r',b'g',b'b'):
        xyz=t[ch+b'XYZ'];assert xyz[:4]==b'XYZ '
        columns.append(np.array(struct.unpack_from('>3i',xyz,8))/65536)
        trc=t[ch+b'TRC']
        if trc[:4]==b'curv':
            n=struct.unpack_from('>I',trc,8)[0]
            if n==1:curves.append(dict(type='gamma',gamma=struct.unpack_from('>H',trc,12)[0]/256))
            elif n==0:curves.append(dict(type='gamma',gamma=1.))
            else:curves.append(dict(type='sampled',values=(np.frombuffer(trc,dtype='>u2',offset=12,count=n).astype(float)/65535).tolist()))
        else:
            assert trc[:4]==b'para' and struct.unpack_from('>H',trc,8)[0]==3
            curves.append(dict(type='parametric3',parameters=(np.array(struct.unpack_from('>5i',trc,12))/65536).tolist()))
    return np.array(columns).T,curves

def linearize(values,curves):
    out=np.empty_like(values,dtype=float)
    for ch,curve in enumerate(curves):
        x=values[...,ch]
        if curve['type']=='gamma':out[...,ch]=x**curve['gamma']
        elif curve['type']=='sampled':out[...,ch]=np.interp(x,np.linspace(0,1,len(curve['values'])),curve['values'])
        else:
            g,a,b,cc,d=curve['parameters']
            out[...,ch]=np.where(x>=d,np.maximum(a*x+b,0)**g,cc*x)
    return out

def encode(values,curves):
    out=np.empty_like(values,dtype=float)
    for ch,curve in enumerate(curves):
        x=values[...,ch]
        if curve['type']=='gamma':out[...,ch]=np.maximum(x,0)**(1/curve['gamma'])
        elif curve['type']=='sampled':out[...,ch]=np.interp(x,curve['values'],np.linspace(0,1,len(curve['values'])))
        else:
            g,a,b,cc,d=curve['parameters']
            out[...,ch]=np.where(x>=cc*d,(np.maximum(x,0)**(1/g)-b)/a,x/cc)
    return out

def independent_convert(src_values,src_icc,dst_icc):
    sm,sc=matrix_and_curves(src_icc);dm,dc=matrix_and_curves(dst_icc)
    rgb=linearize(src_values/65535,sc)@sm.T@np.linalg.inv(dm).T
    result=encode(np.clip(rgb,0,1),dc)
    return np.rint(np.clip(result,0,1)*65535).astype('uint16'),rgb

