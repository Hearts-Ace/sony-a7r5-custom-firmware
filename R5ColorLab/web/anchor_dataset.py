"""Measured anchor cohort; color-model capture remains the verified ST context.

Frontend samples are read before Edit's color matrix. The new capture supplies
only these inputs; the existing ST capture supplies every modeled color stage.
No frontend interpolation or full-JPEG equivalence is assumed.
"""
from pathlib import Path
import hashlib
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT/'data/training'
CHART = BUNDLE/'chart'
FRONTEND = BUNDLE/'frontend_capture'
PAIRS = BUNDLE/'pairs.npz'
CONTEXT = 2
DATASET_ID = 'balanced-chart-20261022-manual-context2'

def source(arrays):
    identity = str(np.asarray(arrays.get('dataset_id', '')).item())
    if identity:
        if identity != DATASET_ID:
            raise ValueError('Unknown measured dataset identity')
        return BUNDLE, CONTEXT
    raise ValueError('独立项目不包含更早期的训练任务数据')


def validate(arrays):
    import v4_dataset
    if v4_dataset.identity(arrays):
        return v4_dataset.validate(arrays)
    # Historical 260-anchor datasets retain their original capture binding.
    version=284 if np.sum(arrays["anchor_index"]>=0)==284 else 260
    bundle,context=source(arrays)
    chart_path,frontend_path=bundle/"chart",bundle/"frontend_capture"
    from validate_synthetic_pairs import validate as original_validate
    audit = original_validate(arrays, chart_path, frontend_path, context)
    chart = np.load(chart_path/'chart.npz', allow_pickle=False)
    index = chart['anchor_index']
    expected = np.array([index[(y-44)//128, (x-32)//128] for x,y in arrays['coords']])
    if not np.array_equal(arrays['anchor_index'], expected):
        raise ValueError('Anchor coordinates changed')
    ids = arrays['anchor_index']; selected = ids >= 0
    if sorted(ids[selected].tolist()) != list(range(version)) or not np.all(arrays['split'][selected] == 'train'):
        raise ValueError('All mandatory anchors must be unique training samples')
    order = np.flatnonzero(selected)[np.argsort(ids[selected])]
    if not np.array_equal(arrays['sensor_codes'][order], chart['anchors']):
        raise ValueError('Anchor code mismatch')
    expected_codes = np.rint(512+15871*np.arange(256)/255).astype(np.uint16)
    if not np.array_equal(arrays['sensor_codes'][order][4:260], np.repeat(expected_codes[:,None],3,axis=1)):
        raise ValueError('Incomplete 256-step gray ramp')
    audit.update(anchor_count=version,colorchecker24_count=24 if version==284 else 0,gray_steps=256,primaries=4,
                 anchors_in_training=True, anchors_in_independent_test=False,
                 frontend_capture_sha256=hashlib.sha256((frontend_path/'report.json').read_bytes()).hexdigest(),
                 dataset_id=str(np.asarray(arrays.get('dataset_id','legacy')).item()),
                 frontend_context=context, frontend='actual Edit post-SSCS/pre-matrix; no interpolation',
                 scope='new measured frontend; original verified ST color subchain')
    return audit

def build():
    # Pack only original measured planes; preserve the complete capture beside it.
    report=json.loads((FRONTEND/'report.json').read_text()); groups={}
    for row in report['messages']:
        p=row['message'].get('payload',{}); label=p.get('label','')
        if not label.startswith(f'synthetic-input-{CONTEXT}-'): continue
        data=(FRONTEND/row['data']['file']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=row['data']['sha256']:raise ValueError('Changed capture')
        g=groups.setdefault(label.rsplit('-ch',1)[0],dict(points=p['points'],planes={}))
        g['planes'][p['ch']]=np.frombuffer(data,dtype='<u2').reshape(-1,9)
    samples={}
    for g in groups.values():
        pixels=np.stack([g['planes'][i]for i in range(3)],axis=-1)
        for p,x in zip(g['points'],pixels):
            key=(p['sy'],p['sx'])
            if key in samples:raise ValueError('Repeated sample')
            samples[key]=(p,x)
    chart=np.load(CHART/'chart.npz',allow_pickle=False);keys=sorted(samples)
    codes=np.array([chart['rgb_codes'][key]for key in keys])
    arrays=dict(dataset_id=np.array(DATASET_ID),sensor_codes=codes,sensor=(codes.astype(float)-512)/15871,
                input=np.array([samples[k][1]for k in keys]),
                coords=np.array([[samples[k][0]['gx'],samples[k][0]['gy']]for k in keys]),
                split=np.array(['test' if (sy*76+sx)%5==0 else 'valid' if (sy*76+sx)%5==1 else 'train'for sy,sx in keys]),
                anchor_index=np.array([chart['anchor_index'][key]for key in keys]))
    audit=validate(arrays)
    np.savez_compressed(PAIRS,**arrays)
    audit['pairs_sha256']=hashlib.sha256(PAIRS.read_bytes()).hexdigest()
    (BUNDLE/'dataset_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps(audit,indent=2))

if __name__=='__main__':
    import sys
    sys.path.insert(0,str(ROOT/'scripts'))
    build()
