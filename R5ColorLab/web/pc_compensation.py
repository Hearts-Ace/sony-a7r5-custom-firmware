"""Explicit PC-only residual grid. No camera coordinate/response claim."""
import json
from pathlib import Path
import numpy as np
import core
import white_balance
from edit_native_recipe import read
from residual_grid import evaluate, pack, unpack
import pc_stages


def load(job):
    value=json.loads((Path(job)/'pc_compensation.json').read_text())
    if (value['schema'] not in ('r5-PC-compensation/1','r5-PC-compensation/2') or value['camera_apply_allowed'] is not False
        or value.get('stage')!='after-color-subchain-PC-only'
        or value.get('coordinate_model') not in ('provisional-bt601-limited','measured-inverse-bspline-forward-TPS')
        or (value.get('pipeline')!=['qaq-provisional-grid'] and not np.array_equal(value.get('response'),np.eye(3)))
        or value['recipe_sha256']!=core.sha((Path(job)/'fit/recipe.json').read_bytes())
        or not core.target_matches(value,job)
        or value['pairs_sha256']!=core.sha((Path(job)/'pairs.npz').read_bytes())):
        raise ValueError('PC compensation source mismatch')
    if value['schema']=='r5-PC-compensation/2':
        if value.get('pipeline') not in (['gray-tone','gray-tint','gray-protected-color-grid'],['rgb-independent','gray-protected-color-grid'],['qaq-provisional-grid']):
            raise ValueError('Unknown PC pipeline')
        pc_stages.validate(value['curves'])
        if (value['pipeline']==['qaq-provisional-grid']) != (value['curves'].get('mode')=='qaq-grid'):
            raise ValueError('QAQ pipeline mismatch')
        if value['pipeline']==['qaq-provisional-grid'] and value['response']!=value['curves']['response']:
            raise ValueError('QAQ response mismatch')
        if (value['pipeline'][0]=='rgb-independent') != (value['curves'].get('mode')=='rgb-independent'):
            raise ValueError('Curve mode and pipeline mismatch')
    return value,unpack(bytes.fromhex(value['payload_hex']))


def apply(job,rgb):
    value,grid=load(job)
    a=np.asarray(rgb,dtype=float)
    if a.shape[-1]!=3 or not np.isfinite(a).all():raise ValueError('Expected finite RGB')
    if value['schema']=='r5-PC-compensation/2':
        return pc_stages.render(a.reshape(-1,3),value['curves'],grid).reshape(a.shape)
    return evaluate(a.reshape(-1,3),grid,np.eye(3)).reshape(a.shape)


def generate(job):
    job=Path(job)
    recipe,model=__import__('baseline').read_job(job)
    with np.load(job/'pairs.npz',allow_pickle=False) as p:
        split=p['split'];ids=p['anchor_index'];x=p['input'];target=p['0_target']/16383
        from fit_anchor_native import training_plan
        random_selection=np.flatnonzero((split=='train')&(ids<0)&(p['sector16_index']<0)) if 'design_srgb' in p else None
        train,_,_,weights=training_plan(split,ids,recipe.get("fitting",{}).get("selected_training_weights",recipe.get("fitting",{}).get("group_total_weights")),p["sector16_index"] if "sector16_index" in p else None,p["baseline_tonal_index"] if recipe.get("fitting",{}).get("tonal_balance") else None,random_selection,p.get('sample_kind'),recipe.get('fitting',{}).get('search_options',{}))
        base=white_balance.render_pairs(model,p,recipe)/16383
        gray=(ids>=4)&(ids<260)&(split=='train')
        if gray.sum()!=256:raise ValueError('需要完整256级实采灰阶训练色卡，请重新拟合原生任务')
        curve,grid,audit=pc_stages.fit_training(base[train],target[train],gray[train],weights, strategy=recipe.get("fitting",{}).get("pc_grid_strategy") or "direct", quantization_sweeps=recipe.get("fitting",{}).get("selected_pc_quantization_sweeps",0), perceptual_weight=recipe.get("fitting",{}).get("search_options",{}).get("perceptual_weight",0), curve_mode=recipe.get("fitting",{}).get("pc_options",{}).get("curve_mode","tone-tint"),response=recipe.get("fitting",{}).get("pc_options",{}).get("response"),parameter_smoothing=recipe.get("fitting",{}).get("search_options",{}).get("parameter_smoothing",0))
        tone,tinted,gate=pc_stages.curves(base,curve)
        corrected=pc_stages.render(base,curve,grid)
        metrics={}
        for name,mask in [('gray_training',gray),('test',split=='test'),('validation',split=='valid')]:
            metrics[name]={key:core.tonal_comparison(target[mask],rgb[mask])['groups']['all']['metrics']
                           for key,rgb in [('native',base),('tone',tone),('tint',tinted),('compensated',corrected)]}
    value=dict(schema='r5-PC-compensation/2',camera_apply_allowed=False,
        stage='after-color-subchain-PC-only',coordinate_model=('measured-inverse-bspline-forward-TPS' if isinstance(curve.get('response'),dict) else 'provisional-bt601-limited'),
        pipeline=(['qaq-provisional-grid'] if curve.get('mode')=='qaq-grid' else ['rgb-independent','gray-protected-color-grid'] if curve.get('mode')=='rgb-independent' else ['gray-tone','gray-tint','gray-protected-color-grid']),curves=curve,
        response=curve.get("response",np.eye(3).tolist()),payload_hex=pack(grid).hex(),grid_shape=[5,9,9],
        recipe_sha256=core.sha((job/'fit/recipe.json').read_bytes()),
        target_source=core.target_identity(job),pairs_sha256=core.sha((job/'pairs.npz').read_bytes()),
        metrics=metrics,fitting=audit,training_only=True,
        reference='Cobalt public separation of characterization, tone and look; independent implementation, not Cobalt algorithm.',
        reference_url='https://www.cobalt-image.com/tutorials/our_technology/',
        limits=[('QAQ measured A7C2 proxy when response is a snapshot; legacy fixed response otherwise. Not R5 calibration.' if curve.get('mode')=='qaq-grid' else 'PC provisional coordinates and identity RGB response; not R5 ISP calibration.'),
                'Post-color correction cannot recover differences already lost by native clipping.',
                'Not included in 4.18 BIN or fitted-ST.ARW.',
                'No dual-illuminant measurement or new RAW frontend calibration; output RGB correction only.'])
    destination=job/'pc_compensation.json'
    if destination.exists():
        old=destination.read_bytes()
        archive=job/('pc_compensation-'+core.sha(old)+'.json')
        if not archive.exists():archive.write_bytes(old)
    temporary=job/'pc_compensation.pending'
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(destination)
    return value
