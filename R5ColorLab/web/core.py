from compute_backend import render_native
from patch_sampling import center_mean
"""Local UI adapters and R5 4.23 independent custom filter exports."""
import copy
import white_balance
import baseline
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
ROOT = RESEARCH
SCRIPTS = RESEARCH / 'scripts'
sys.path.insert(0, str(SCRIPTS))
COMPILER_PATH = ROOT / 'compilers/custom_filter_v4.py'
spec = importlib.util.spec_from_file_location('custom423_compiler', COMPILER_PATH)
compiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)
BASE = ROOT / 'data/model'
CAPTURE = BASE / 'capture'
CHART = BASE / 'synthetic_C'
PAIRS = BASE / 'pairs_C/pairs.npz'
PROFILE = ROOT / 'data/camera_profile.json'
WIRES = [0, 3, 2, 1, 16, 15, 19, 20, 17, 18, 5, 13]
PROFILES = [0, 6, 2, 1, 42, 41, 54, 55, 43, 44, 53, 53]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def gamma_endpoint(value):
    if value is not None and (type(value) is not int or not 0 <= value <= 131071):
        raise ValueError('伽马最后一点必须是 0–131071 的整数，或留空保留 ST 原生端点')
    return value


def config(entries):
    return compiler.config(entries)


def compile_config(value):
    return compiler.pack(value), COMPILER_PATH, '4.23', 4


def verified(path, digest):
    data = path.read_bytes()
    if sha(data) != digest:
        raise ValueError('Source identity changed: ' + str(path))
    return data


def presets():
    value=json.loads((ROOT/'data/presets.json').read_text())
    compiler.pack(config(value['entries']))
    return copy.deepcopy(value['entries']),copy.deepcopy(value['provenance'])


def measured_inputs(dataset_id=None):
    import numpy as np
    import anchor_dataset
    if dataset_id == 'legacy':
        with np.load(anchor_dataset.PAIRS, allow_pickle=False) as archive:
            arrays = {key: archive[key].copy() for key in archive.files}
        audit = anchor_dataset.validate(arrays)
    else:
        import chart_datasets
        arrays,audit = chart_datasets.get(dataset_id).load()
    import sector16
    from edit_color_pipeline import RuntimeColor
    capture,context=baseline.resolve(audit.get('dataset_id'))
    model=RuntimeColor.from_capture(capture,context)
    arrays['sector16_index'],audit['sector16']=sector16.select(arrays,model)
    import tonal_sampling
    arrays['baseline_tonal_index']=tonal_sampling.classify(center_mean(render_native(model,arrays['input']))/16383)
    audit['tonal_balance']=tonal_sampling.validate(arrays,model)
    return arrays, audit


def target_identity(job):
    job = Path(job)
    audit = json.loads((job/'input_audit.json').read_text())
    kind = audit.get('target_kind','lut')
    if kind not in ('lut','chart-image'):
        raise ValueError('Unknown target source')
    path = job/('target-image.bin' if kind=='chart-image' else 'input.cube')
    digest = sha(path.read_bytes())
    expected = audit.get('target_source_sha256') if kind=='chart-image' else audit.get('lut_sha256')
    if digest != expected:
        raise ValueError('Target source mismatch')
    return dict(kind=kind, sha256=digest)


def target_matches(value, job):
    identity = target_identity(job)
    if 'target_source' in value:
        return value['target_source'] == identity
    return identity['kind']=='lut' and value.get('lut_sha256')==identity['sha256']


def prepare_target(lut, gamut, output, dataset_id=None):
    from raw_slog3_reference import Cube, RawSLog3Reference
    from validate_synthetic_pairs import validate_profile
    import numpy as np
    import anchor_dataset
    arrays, audit = measured_inputs(dataset_id)
    profile = json.loads(PROFILE.read_text())
    validate_profile(profile, json.loads((anchor_dataset.CHART / 'manifest.json').read_text()))
    reference = RawSLog3Reference(profile, Cube(lut), gamut, mode='raw-alchemy-v0.6.2-fused')
    arrays['0_target'] = reference(arrays.get('reference_sensor',arrays['sensor'])) * 16383
    arrays.pop('1_target', None)
    np.savez_compressed(output / 'pairs.npz', **arrays)
    audit.update(lut_sha256=sha(lut.read_bytes()), gamut=gamut, profile_sha256=sha(PROFILE.read_bytes()),
                 original_pairs_sha256=__import__('chart_datasets').get(audit['dataset_id']).metadata()['pairs_sha256'], context=baseline.resolve(audit.get('dataset_id'))[1],
                 reference_mode=reference.mode, photo_training=False)
    (output / 'input_audit.json').write_text(json.dumps(audit, indent=2) + '\n')


def finish_fit(output, number, short_name, full_name, gamma_endpoint128=None):
    gamma_endpoint128 = gamma_endpoint(gamma_endpoint128)
    # Preserve the compiler's default verified ST endpoint. An unsupported fit
    # is reported as an error instead of silently increasing the endpoint.
    recipe_path = output / 'fit/recipe.json'
    original_recipe = recipe_path.read_bytes()
    conversion_path = recipe_path
    # The frozen compiler caps its JSON input at 128 KiB. Search history is
    # diagnostic data; retain it in the original and project only that field.
    if len(original_recipe) > 128*1024:
        projected = json.loads(original_recipe)
        projected.pop('fitting', None)
        conversion_path = output / 'fit/native_conversion_recipe.json'
        conversion_path.write_text(json.dumps(projected, separators=(',', ':'))+'\n')
    capture,context=baseline.for_job(output)
    native, audit = compiler.from_fit(conversion_path, capture, number, short_name, full_name, gamma_endpoint128)
    if conversion_path != recipe_path:
        audit['compiler_input_sha256'] = audit['recipe_sha256']
        audit['recipe_sha256'] = sha(original_recipe)
        audit['compiler_input_policy'] = 'original parameters/source unchanged; fitting diagnostics omitted for frozen compiler size cap'
    audit['white_balance']=json.loads(original_recipe).get('white_balance')
    audit['white_balance_in_binary']=False
    payload = compiler.pack(native)
    (output / 'native_config.json').write_text(json.dumps(native, indent=2, ensure_ascii=False) + '\n')
    (output / 'conversion_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    # A fit alone is not exportable: select a stock grid or finish compression.
    (output / 'R5NATIVE.BIN').unlink(missing_ok=True)
    from edit_native_recipe import read
    import numpy as np
    recipe, model = baseline.read_job(output)
    with np.load(output / 'pairs.npz', allow_pickle=False) as pairs:
        mask = pairs['split'] == 'test'
        inputs = pairs['input'][mask]
        target = pairs['0_target'][mask]
        pairs_data={key:pairs[key][mask] for key in ('input','sensor_codes')}
    from edit_color_pipeline import RuntimeColor
    before = center_mean(render_native(RuntimeColor.from_capture(capture,context),inputs))
    after = white_balance.render_pairs(model, pairs_data, recipe)
    preview = dict(before=np.clip(before/16383, 0, 1).tolist(),
                   target=np.clip(target/16383, 0, 1).tolist(),
                   after=np.clip(after/16383, 0, 1).tolist())
    (output / 'preview.json').write_text(json.dumps(preview))
    return dict(white_balance=recipe.get('white_balance'),config=native, heldout=recipe['heldout'], fitting=recipe['fitting'], preview=preview,
                binary_sha256=sha(payload), binary_bytes=len(payload))


def histogram_comparison(target, predicted):
    """256-bin RGB distribution overlap, not paired/colorimetric accuracy."""
    import numpy as np
    a, b = np.asarray(target, dtype=float), np.asarray(predicted, dtype=float)
    if a.ndim != 2 or a.shape[1] != 3 or a.shape != b.shape or not len(a):
        raise ValueError('Expected equal nonempty Nx3 colors')
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Nonfinite histogram input')
    bins = [np.floor(np.clip(v, 0, 1)*255+.5).astype(int) for v in (a, b)]
    histograms = [np.stack([np.bincount(v[:, c], minlength=256)/len(v) for c in range(3)]) for v in bins]
    overlap = np.minimum(*histograms).sum(axis=1)
    return dict(bins=256, samples=len(a), target=histograms[0].tolist(), after=histograms[1].tolist(),
                overlap_percent=(overlap*100).tolist(), mean_overlap_percent=float(overlap.mean()*100),
                scope='full independent test set; clipped display RGB; training anchors reported separately')


def diagnostics(output, pc=False, grid_key=None):
    """Evaluate measured samples only; historical runs require refitting anchors."""
    pc=bool(pc or grid_key)
    import numpy as np
    from edit_native_recipe import read
    from edit_color_pipeline import RuntimeColor
    def report_metrics(predicted,target):
        m=tonal_comparison(target/16383,predicted/16383)['groups']['all']['metrics']
        return dict(mae_8bit=m['mae'],rmse_8bit=m['rmse'],p95_8bit=m['p95'])
    recipe, model = __import__('baseline').read_job(output)
    baseline = RuntimeColor.from_capture(*__import__('baseline').for_job(output))
    with np.load(output / 'pairs.npz', allow_pickle=False) as pairs:
        measured, split = pairs['input'], pairs['split']
        test = split == 'test'
        target = pairs['0_target'][test]/16383
        after = white_balance.render_pairs(model,pairs,recipe,test)/16383
        native_after=after.copy()
        grid_sha=None
        if grid_key:
            import grid_distillation
            _,_,grid_sha=grid_distillation.load_result(output,grid_key)
            apply=lambda job,rgb:grid_distillation.apply(job,rgb,grid_key)
            after=apply(output,after)
        elif pc:
            from pc_compensation import apply
            after=apply(output,after)
        fields = None
        if 'anchor_index' in pairs.files:
            import anchor_dataset
            arrays={key:pairs[key] for key in pairs.files}
            anchor_dataset.validate(arrays)
            ids=pairs['anchor_index']; selected=np.flatnonzero(ids>=0)
            order=selected[np.argsort(ids[selected])]
            x=measured[order]; t=pairs['0_target'][order]
            before=center_mean(render_native(baseline,x)); predicted=white_balance.render_pairs(model,pairs,recipe,order)
            if pc or grid_key: predicted=apply(output,predicted/16383)*16383
            fields=dict(input=pairs['sensor'][order].tolist(),
                        target=np.clip(t/16383,0,1).tolist(),
                        before=np.clip(before/16383,0,1).tolist(),
                        after=np.clip(predicted/16383,0,1).tolist(),
                        frontend=('experimental WB: flatfield ITP + frozen measured frontend residual' if white_balance.active(white_balance.from_recipe(recipe)) else anchor_dataset.validate(arrays)['frontend']),
                        included_in_training=True,gray_steps=256,
                        names=['正红','正黄','正绿','正蓝'],
                        metrics={label:dict(before=report_metrics(before[sl],t[sl]),
                                            after=report_metrics(predicted[sl],t[sl]))
                                 for label,sl in [('primaries',slice(0,4)),('gray',slice(4,260)),('all',slice(None))]+([('colorchecker24',slice(260,None))] if len(order)==284 else [])})
    sector_fields=None
    with np.load(output/'pairs.npz',allow_pickle=False) as pairs:
        if 'sector16_index' in pairs:
            import sector16
            sector_audit=sector16.validate(pairs,baseline)
            selected=np.flatnonzero(pairs['sector16_index']>=0)
            order=selected[np.argsort(pairs['sector16_index'][selected])]
            before=center_mean(render_native(baseline,pairs['input'][order]))
            predicted=white_balance.render_pairs(model,pairs,recipe,order)
            current_inputs=white_balance.inputs(model,pairs['input'][order],pairs['sensor_codes'][order],white_balance.from_recipe(recipe))
            current_sectors=model.sectors(current_inputs)[:,4].tolist()
            target_sector=pairs['0_target'][order]
            if pc or grid_key:predicted=apply(output,predicted/16383)*16383
            sector_fields=dict(audit=sector_audit,current_sectors=current_sectors,
                before=np.clip(before/16383,0,1).tolist(),target=np.clip(target_sector/16383,0,1).tolist(),
                after=np.clip(predicted/16383,0,1).tolist(),
                metrics=dict(before=report_metrics(before,target_sector),after=report_metrics(predicted,target_sector)),
                nodes=[dict(node=i,metrics=report_metrics(predicted[3*i:3*i+3],target_sector[3*i:3*i+3])) for i in range(16)])
    cc24=None
    if fields and len(fields['input'])==284:
        from colorchecker24 import NAMES
        cc24=dict(names=NAMES,**{k:fields[k][260:] for k in ['input','target','before','after']},
                  metrics=fields['metrics']['colorchecker24'],included_in_training=True)
    return dict(sector16=sector_fields,white_balance=recipe.get('white_balance'),histogram=histogram_comparison(target, after), anchors=fields,colorchecker24=cc24,
                dataset=json.loads((output/'input_audit.json').read_text()) if (output/'input_audit.json').exists() else None,
                training_fitting=recipe.get('fitting',{}),
                pc_sha256=sha((output/'pc_compensation.json').read_bytes()) if pc else None,
                pc_report=json.loads((output/'pc_compensation.json').read_text()) if pc else None,
                grid_key=grid_key, grid_sha256=grid_sha, algorithm=('compressed' if grid_key else 'pc' if pc else 'native'),
                pc_enabled=bool(pc or grid_key), native_tonal=tonal_comparison(target,native_after),
                test_preview=after.tolist(),
                fitting_policy=('原生分阶段：Gamma 灰阶明暗 → CC1 / block13 彩色响应 → '+(('按任务权重联合微调（随机／正色／灰阶／24色'+('／矩阵16色相' if 'sector16' in recipe['fitting']['group_total_weights'] else '')+'：'+ '/'.join(str(recipe['fitting']['group_total_weights'][k]) for k in ('random','primaries','gray','colorchecker24',*(['sector16'] if 'sector16' in recipe['fitting']['group_total_weights'] else [])))+'），不设灰阶优先门槛。') if recipe['fitting'].get('group_total_weights') else '历史灰阶优先约束联合微调。')+('已启用原生参数与 PC 残差交替训练，按补偿后的整条链路选择候选。' if recipe['fitting'].get('pc_compensation_training') else '本任务仅优化原生参数。')) if recipe.get('fitting',{}).get('training_pipeline') else ('历史灰阶优先任务；未使用新版原生分阶段流程。' if recipe.get('fitting',{}).get('gray_priority') else '历史任务：四组等权；重新拟合后应用新版流程。'),
                tonal=tonal_comparison(target,after),
                recipe_sha256=sha((output / 'fit/recipe.json').read_bytes()))


def tonal_comparison(target, predicted):
    """Matched uint8 RGB, grouped by target encoded Rec.709 luma thirds."""
    import numpy as np
    a,b=np.asarray(target,dtype=float),np.asarray(predicted,dtype=float)
    if a.ndim!=2 or a.shape[1]!=3 or a.shape!=b.shape or not len(a) or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Finite equal nonempty Nx3 RGB required')
    a,b=[np.floor(np.clip(v,0,1)*255+.5).astype(np.uint8) for v in (a,b)]
    luma=a.astype(float)@np.array([.2126,.7152,.0722])
    masks=[('all','全部',np.ones(len(a),dtype=bool)),('shadows','阴影',luma<85),
           ('midtones','中间调',(luma>=85)&(luma<170)),('highlights','高光',luma>=170)]
    groups={}
    for key,label,mask in masks:
        aa,bb=a[mask],b[mask];delta=bb.astype(float)-aa.astype(float)
        metrics=None
        if len(aa):
            from perceptual import compare
            metrics=dict(mae=float(np.abs(delta).mean()),rmse=float(np.sqrt(np.mean(delta**2))),
                         p95=float(np.percentile(np.abs(delta),95)),
                         channel_mae=np.abs(delta).mean(axis=0).tolist(),
                         channel_rmse=np.sqrt(np.mean(delta**2,axis=0)).tolist(),
                         channel_bias=delta.mean(axis=0).tolist(),
                         perceptual=compare(aa/255,bb/255))
        groups[key]=dict(label=label,samples=len(aa),metrics=metrics,
                         histogram=histogram_comparison(aa/255,bb/255) if len(aa) else None)
    return dict(encoding='clip [0,1], floor(RGB*255+0.5), uint8; no black subtraction',
                split='target encoded Y prime = .2126R + .7152G + .0722B; shadows <85; midtones [85,170); highlights >=170',
                groups=groups)


def write_validation_raw(original, recipe_path, destination):
    import validation_raw
    return validation_raw.write(original, recipe_path, destination)
