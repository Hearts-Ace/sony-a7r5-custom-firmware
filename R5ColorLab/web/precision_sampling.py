"""Train-only H/S/Y strata and complete tonal tracks, independent of targets."""
import numpy as np

TONAL = ('gray','hue24_tonal','hue16_tonal','primary_tonal','primary_anchor','colorchecker24')

def bins(rgb):
    rgb=np.clip(np.asarray(rgb,dtype=float),0,1)
    mx=rgb.max(1);delta=np.ptp(rgb,axis=1);h=np.zeros(len(rgb))
    mask=delta>1e-12;channel=rgb.argmax(1)
    for c in range(3):
        m=mask&(channel==c)
        h[m]=((rgb[m,(c+1)%3]-rgb[m,(c+2)%3])/delta[m]+2*c)%6
    hue=np.minimum((h*4).astype(int),23)
    sat=np.minimum((np.divide(delta,mx,out=np.zeros_like(mx),where=mx>0)*8).astype(int),7)
    lum=np.minimum((rgb@np.array([.2126,.7152,.0722])*16).astype(int),15)
    return (hue*8+sat)*16+lum

def coarse(arrays,per_bin=4):
    pool=np.flatnonzero((arrays['split']=='train')&(arrays['anchor_index']<0)&(arrays['sector16_index']<0))
    kind=arrays.get('sample_kind',np.full(len(arrays['split']),''))
    protected=pool[np.isin(kind[pool],TONAL)]
    strata=bins(arrays['design_srgb'])
    selected=[]
    for s in np.unique(strata[pool]):
        rows=pool[strata[pool]==s]
        selected.extend(rows[np.linspace(0,len(rows)-1,min(per_bin,len(rows)),dtype=int)])
    return np.unique(np.r_[protected,selected]).astype(int)

def hard_weights(error,strata):
    """Keep every row; emphasize large training errors within each color stratum."""
    error=np.asarray(error,dtype=float);strata=np.asarray(strata)
    weights=np.ones(len(error))
    for s in np.unique(strata):
        rows=np.flatnonzero(strata==s);scale=max(float(np.median(error[rows])),1e-12)
        weights[rows]=np.clip(np.sqrt(np.maximum(error[rows],0)/scale),1,4)
    return weights


def track_multipliers(kinds, options=None):
    options=options or {}
    kinds=np.asarray(kinds)
    result=np.ones(len(kinds),dtype=float)
    result[np.isin(kinds,('primary_tonal','primary_anchor'))]=options.get('primary_tonal_weight',1.0)
    result[kinds=='hue24_tonal']=options.get('hue24_tonal_weight',1.0)
    return result


def track_mean_cost(cost, tonal_bins=None, kinds=None, options=None):
    from tonal_sampling import balanced_weights
    cost=np.asarray(cost,dtype=float)
    weights=np.ones(len(cost)) if tonal_bins is None else balanced_weights(tonal_bins)
    if kinds is not None:weights=weights*track_multipliers(kinds,options)
    return float(np.average(cost,weights=weights))
