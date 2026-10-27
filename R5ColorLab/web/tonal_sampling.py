from compute_backend import render_native
from patch_sampling import center_mean
"""Fixed baseline luminance strata; targets and fitted parameters never set bins."""
import numpy as np

LABELS = ('阴影', '中间调', '高光')


def classify(rgb):
    rgb = np.asarray(rgb, dtype=float)
    if rgb.ndim != 2 or rgb.shape[1] != 3 or not np.isfinite(rgb).all():
        raise ValueError('Expected finite Nx3 baseline RGB')
    # Match displayed luminance using the job's immutable source baseline.
    encoded = np.floor(np.clip(rgb, 0, 1)*255+.5)
    return np.minimum((encoded @ np.array([.2126,.7152,.0722])/85).astype(int),2)


def balanced_weights(bins):
    bins = np.asarray(bins)
    if bins.ndim != 1 or not np.isin(bins,[0,1,2]).all():
        raise ValueError('Invalid fixed luminance bins')
    if not len(bins):
        return np.ones(0)
    counts = np.bincount(bins.astype(int),minlength=3)
    return len(bins)/(np.count_nonzero(counts)*counts[bins.astype(int)])


def mean_cost(cost, bins=None):
    cost = np.asarray(cost)
    return float(np.average(cost,weights=balanced_weights(bins))) if bins is not None else float(cost.mean())


def audit(bins, split, anchor_ids, sector_ids):
    bins=np.asarray(bins)
    groups={'random':(anchor_ids<0)&(sector_ids<0),'primaries':(anchor_ids>=0)&(anchor_ids<4),
            'gray':(anchor_ids>=4)&(anchor_ids<260),'colorchecker24':anchor_ids>=260,'sector16':sector_ids>=0}
    result={'schema':'r5-fixed-baseline-tonal-balance/1','basis':'job-bound baseline integer color output before fitted WB; quantized sRGB display Y prime',
            'thresholds_8bit':[85,170],'target_independent':True,'policy':'equal nonempty luminance strata within each cohort; preserve user cohort total mass',
            'counts':{},'missing_train_strata':{}}
    for name,mask in groups.items():
        result['counts'][name]={s:np.bincount(bins[mask&(split==s)].astype(int),minlength=3).tolist() for s in ('train','valid','test')}
        result['missing_train_strata'][name]=[LABELS[i] for i,n in enumerate(result['counts'][name]['train']) if not n]
    return result


def validate(arrays, model):
    if 'baseline_tonal_index' not in arrays:return None
    expected=classify(center_mean(render_native(model,arrays['input']))/16383)
    if not np.array_equal(expected,arrays['baseline_tonal_index']):
        raise ValueError('固定基线亮度分区来源发生变化')
    return audit(expected,arrays['split'],arrays['anchor_index'],arrays.get('sector16_index',np.full(len(expected),-1)))
