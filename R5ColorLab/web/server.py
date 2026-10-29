#!/usr/bin/env python3
"""Loopback-only color workstation; no device operations, shell or path API."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
import traceback
from urllib.parse import urlparse, parse_qs
import uuid
import webbrowser
import zipfile

import core
import chart_target
import chart_datasets
import export_policy423
import batch_training
from grid_models import default_response
from residual_grid import response_json

STATIC = core.HERE / 'static'
RUNS = Path(os.environ.get('R5_RUNS_DIR', str(core.HERE / 'runs'))).resolve()
TOKEN = secrets.token_urlsafe(32)
JOBS = {}
LOCK = threading.Lock()
POOL = ThreadPoolExecutor(max_workers=1)
DIAGNOSTICS = {}
RAW_LOCK = threading.RLock()
PREVIEWS = {}
PREVIEW_POOL = ThreadPoolExecutor(max_workers=1)
MAX_BODY = 65 * 1024 * 1024


def dump(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode()


def preview_work(identifier, job_id, destination, pc=False, grid_key=None, reuse_id=None, grid_enabled=True):
    item = PREVIEWS[identifier]
    source = RUNS/job_id/'photo_previews'/reuse_id if reuse_id else destination/'input.ARW'
    try:
        item.update(status='running', phase='本地 RAW 解码与两套函数渲染（不采集 Edit）')
        (destination/'preview.json').write_bytes(dump(item))
        with (destination/'preview.log').open('w') as log:
            process = subprocess.run([sys.executable, str(core.HERE/'photo_preview.py'),
                str(source), str(RUNS/job_id), str(destination)]+(['--pc'] if pc else [])+(['--grid',grid_key] if grid_key else [])+(['--reuse'] if reuse_id else [])+([] if grid_enabled else ['--no-grid-effect']),
                stdout=log, stderr=subprocess.STDOUT, timeout=1800,
                env={**os.environ, 'OPENBLAS_NUM_THREADS':'1', 'VECLIB_MAXIMUM_THREADS':'1'})
        if process.returncode:
            details = (destination/'preview.log').read_text(errors='replace')
            raise ValueError(details.strip().splitlines()[-1] if details.strip() else '渲染失败')
        item.update(status='done', phase='两张预览已生成',
                    result=json.loads((destination/'result.json').read_text()))
    except Exception as error:
        item.update(status='error', phase='预览失败', error=str(error))
    finally:
        if not reuse_id: source.unlink(missing_ok=True)
        (destination/'preview.json').write_bytes(dump(item))


def compression_work(identifier,response,post_gray_refinement=False,objective='fuji-target'):
    output=RUNS/identifier
    state=dict(status='running',phase='压缩训练：采样总效果、求解与量化微调',started=time.time())
    path=output/'grid_training.json'
    path.write_bytes(dump(state))
    try:
        with RAW_LOCK:
            from grid_distillation import generate
            from training_progress import TrainingProgress
            tracker=TrainingProgress(output/'grid_progress.json',3)
            tracker.update(stage='压缩训练准备',state='running')
            report=generate(output,response,progress=tracker.update,post_gray_refinement=post_gray_refinement,objective=objective)
            tracker.update(stage='压缩训练完成',state='done')
        state.update(status='done',phase='压缩训练完成',key=report['key'])
    except Exception as error:
        state.update(status='error',phase='压缩训练失败',error=str(error))
    state['finished']=time.time()
    path.write_bytes(dump(state))
    return state


def work(identifier, body, resume=False):
    job = JOBS[identifier]
    output = RUNS / identifier
    try:
        output.mkdir(parents=True,exist_ok=resume)
        job.update(phase='检查传感器、原生前端与训练集来源', status='running')
        recipe_path=output/'fit/recipe.json'
        reuse_fit=resume and recipe_path.is_file()
        if reuse_fit:
            saved=json.loads(recipe_path.read_text())
            audit=json.loads((output/'chart_target.json').read_text())
            if audit['source_sha256']!=body.get('target_sha256') or saved['source']['pairs_sha256']!=core.sha((output/'pairs.npz').read_bytes()):
                raise ValueError('已有拟合的目标或训练数据身份不符，拒绝接续')
            if saved['source']['dataset_id'] not in chart_datasets.MODULES or saved['source']['dataset_id']!=body.get('dataset_id',__import__('v4_dataset').DATASET_ID):
                raise ValueError('已有拟合色卡版本不符')
            job.update(phase='复用已完成的原生拟合，接续补偿与压缩')
        else:
            fit_native(identifier,body,output,job)
        # Metal command encoders in one service process must not be entered
        # from concurrent batch/HTTP threads. Native fit subprocesses remain
        # independent and retain the requested batch concurrency.
        with RAW_LOCK:
            try:
                result=finish_native(identifier,body,output,job)
            finally:
                from gpu_runtime import available
                if available():
                    import torch
                    torch.mps.synchronize()
        job.update(status='done', phase='拟合与配置转换完成；待实际颜色验收', result=result)
    except Exception as error:
        output.mkdir(parents=True, exist_ok=True)
        (output / 'error.log').write_text(traceback.format_exc())
        job.update(status='error', phase='处理失败', error=str(error))
    finally:
        job['finished'] = time.time()
        (output / 'job.json').write_bytes(dump({k: v for k, v in job.items() if k != 'process'}))


def fit_native(identifier,body,output,job):
        if body.get('target_kind') == 'chart-image':
            source_path=core.HERE/'chart_uploads'/body['target_id']/'source.bin'
            data=source_path.read_bytes()
            if core.sha(data)!=body['target_sha256']:
                raise ValueError('目标图上传来源发生变化')
            chart_target.prepare(data,output,source_path=source_path,dataset_id=body.get('dataset_id'))
            description='source-bound measured RAW frontend -> processed chart image / sRGB'
        else:
            lut = output / 'input.cube'
            lut.write_text(body['lut'], encoding='utf-8')
            core.prepare_target(lut, body['gamut'], output,dataset_id=body.get('dataset_id'))
            description='integer RAW -> raw-alchemy-v0.6.2-fused ' + body['gamut'] + ' S-Log3 -> uploaded cube'
        job.update(phase='原生分阶段拟合与 PC 交替优化' if body.get('pc_compensation',False) else '原生分阶段拟合：明暗、色彩、联合微调')
        cmd = [sys.executable, str(core.HERE / 'fit_anchor_native.py'), str(output / 'pairs.npz'),
               '--capture', str(__import__('baseline').for_job(output)[0]), '--context', str(__import__('baseline').for_job(output)[1]), '--gamut', '0',
               '--output', str(output / 'fit'), '--evaluations', str(body['evaluations']),
               '--target-description', description]
        from training_policy import group_importance
        from optimizer_policy import search_options, pc_options
        cmd += ['--pc-options',json.dumps(pc_options(body.get('pc_options'))), '--group-weights',json.dumps(group_importance(body.get('group_weights'))), '--search-options',json.dumps(search_options(body.get('search_options')))]
        if body.get('white_balance',False):
            cmd.append('--white-balance')
        if body.get('speed_priority',False):
            cmd.append('--fast')
        elif body.get('pc_compensation',False):
            cmd.append('--pc-compensation')
        with (output / 'fit.log').open('w') as log:
            process = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                                       env={**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'VECLIB_MAXIMUM_THREADS': '1'})
            job['process'] = process
            try:
                code = process.wait()
            finally:
                job.pop('process', None)
        if code:
            raise ValueError('拟合器退出码 %s，请查看完整日志' % code)


def finish_native(identifier,body,output,job):
        job.update(phase='验证配方并转换 4.23 自定义配置')
        result = core.finish_fit(output, body['number'], body['short_name'], body['full_name'], body.get('gamma_endpoint128'))
        if body.get('pc_compensation',False):
            job.update(phase='整体训练：从整数原生参数重建 PC 残差并验证')
            from pc_compensation import generate
            value=generate(output)
            result['pc_compensation']=dict(enabled=True,sha256=core.sha((output/'pc_compensation.json').read_bytes()),metrics=value['metrics'])
        else:
            result['pc_compensation']=dict(enabled=False)
        if body.get('compression_training'):
            job.update(phase='压缩训练：最终网格直接拟合富士目标')
            state=compression_work(identifier,body['pc_options']['response'],body.get('post_gray_refinement',False),objective=body.get('compression_objective','fuji-target'))
            if state['status']!='done':raise ValueError(state.get('error','压缩训练失败'))
            result['grid_key']=state['key']
        return result


def validate_fit(body):
    body['post_gray_refinement']=False
    body['compressed_alternation_rounds']=0
    body.setdefault('compression_objective','fuji-target')
    if body['compression_objective'] not in ('fuji-target','pc-teacher'):
        raise ValueError('无效最终网格训练目标')
    if type(body.get('speed_priority',False)) is not bool:raise ValueError('速度优先开关须为布尔值')
    body.setdefault('speed_priority',False)
    from training_policy import group_importance
    body['group_weights']=group_importance(body.get('group_weights'))
    from optimizer_policy import search_options, pc_options
    if type(body.get('white_balance',False)) is not bool:raise ValueError('白平衡开关须为布尔值')
    body.setdefault('white_balance',False)
    body.setdefault('pc_compensation',True)
    body['search_options']=search_options(body.get('search_options'))
    body['pc_options']=pc_options(body.get('pc_options'))
    if type(body.get('compression_training',False)) is not bool:raise ValueError('压缩训练开关无效')
    if body.get('compression_training'):
        body['pc_compensation']=True
        body['pc_options']=pc_options(dict(curve_mode='tone-tint',grid_enabled=True,response=body['pc_options']['response']))
    if type(body.get('pc_compensation',False)) is not bool:
        raise ValueError('PC 补偿开关必须为布尔值')
    if type(body.get('number')) is not int or not 1 <= body['number'] <= 12:
        raise ValueError('自定义配置序号必须为 1–12')
    if type(body.get('evaluations')) is not int or not 1 <= body['evaluations'] <= 2000:
        raise ValueError('每阶段求解评估上限必须为 1–2000')
    kind=body.get('target_kind','lut')
    if kind not in ('lut','chart-image'):
        raise ValueError('请选择目标来源')
    if kind=='chart-image':
        target_id=body.get('target_id')
        if not isinstance(target_id,str) or len(target_id)!=32 or any(c not in '0123456789abcdef' for c in target_id):
            raise ValueError('请先上传色卡目标图')
        folder=core.HERE/'chart_uploads'/target_id
        body['dataset_id']=chart_datasets.upload_version(folder,body.get('dataset_id'))
        data=(folder/'source.bin').read_bytes()
        chart_target.decode(data,body['dataset_id'])
        body['target_sha256']=core.sha(data)
    elif body.get('gamut') not in ('S-Gamut3', 'S-Gamut3.Cine'):
        raise ValueError('请选择 LUT 输入色域')
    if kind=='lut':
        body['dataset_id']=chart_datasets.get(body.get('dataset_id')).DATASET_ID
    core.gamma_endpoint(body.get('gamma_endpoint128'))
    if kind=='lut' and (not isinstance(body.get('lut'), str) or not body['lut'].strip()):
        raise ValueError('请导入 .cube LUT')
    sample = dict(core.presets()[0][0], number=body['number'],
                  short_name=body.get('short_name'), full_name=body.get('full_name'))
    core.compiler.pack(core.config([sample]))
    return body


class Handler(BaseHTTPRequestHandler):
    def respond(self, data, mime='application/json', status=200, filename=None):
        if not isinstance(data, bytes):
            data = dump(data)
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'none'")
        if filename:
            self.send_header('Content-Disposition', 'attachment; filename="' + filename + '"')
        self.end_headers()
        self.wfile.write(data)

    def trusted(self):
        port = self.server.server_address[1]
        hosts = ('127.0.0.1:' + str(port), 'localhost:' + str(port))
        if self.headers.get('Host') not in hosts:
            return False
        origin = self.headers.get('Origin')
        return origin is None or origin in ['http://' + h for h in hosts]

    def do_GET(self):
        if not self.trusted():
            return self.respond(dict(error='Local origin required'), status=403)
        path = urlparse(self.path).path
        try:
            if path.startswith('/api/batches/'):
                return batch_training.get(self, path, sys.modules[__name__])
            if path == '/api/chart-original':
                dataset_id=parse_qs(urlparse(self.path).query).get('dataset_id',[None])[0]
                return self.respond(chart_target.download(dataset_id), 'application/zip', filename='GFX-100MP-chart.zip')
            if path == '/api/chart-file':
                query=parse_qs(urlparse(self.path).query)
                name,data=chart_target.raw_file(query.get('dataset_id',[None])[0],query.get('format',['raf'])[0])
                return self.respond(data,'application/octet-stream',filename=name)
            if path == '/api/bootstrap':
                entries, provenance = core.presets()
                return self.respond(dict(token=TOKEN, presets=entries, provenance=provenance,
                                         default_chart=chart_target.manifest(),
                                         chart_versions=chart_datasets.catalog(),
                                         compute_backend=__import__('gpu_runtime').policy(),
                                         latest_batch=batch_training.latest(core.HERE),
                                         template=core.config([]), stock_grids=__import__("stock_grids").catalog(),
                                         fitting_baseline='PT / v4.5 5300K simulated ITP+SSCS · 99,372 patches; derived context',
                                         grid_response=default_response(), history=[dict(id=k, status=v['status'], started=v['started'], phase=v['phase'],target_kind=v.get('target_kind','lut'),pc_available=(RUNS/k/'pc_compensation.json').is_file())
                                                  for k, v in sorted(JOBS.items(), key=lambda kv: kv[1]['started'], reverse=True)][:30],
                                         jobs=[k for k, v in JOBS.items() if v['status'] in ('running', 'queued')]))
            if path.startswith('/api/previews/'):
                bits = path.split('/')
                item = PREVIEWS.get(bits[3])
                if not item:
                    return self.respond(dict(error='预览不存在'), status=404)
                if len(bits) == 4:
                    value = dict(item)
                    if item['status'] in ('queued','running'):
                        progress = RUNS/item['job']/'photo_previews'/item['id']/'progress.json'
                        try:
                            state = json.loads(progress.read_text())
                            value['phase'] = state['phase'] + (' · %d%%' % state['percent'])
                        except (OSError,ValueError,KeyError): pass
                    return self.respond(value)
                name = bits[4]
                if len(bits) == 5 and name in ('lut.png', 'model.png', 'result.json') and item['status'] == 'done':
                    file = RUNS/item['job']/'photo_previews'/item['id']/name
                    return self.respond(file.read_bytes(), 'image/png' if name.endswith('.png') else 'application/json')
                return self.respond(dict(error='预览尚未就绪'), status=404)
            if path.startswith('/api/jobs/'):
                bits = path.split('/')
                identifier = bits[3]
                if identifier not in JOBS:
                    return self.respond(dict(error='任务不存在'), status=404)
                job = JOBS[identifier]
                if len(bits) == 5 and bits[4] == 'diagnostics':
                    if job['status'] not in ('done', 'error'):
                        raise ValueError('任务尚未完成')
                    pc=parse_qs(urlparse(self.path).query).get('pc',['0'])[0]=='1'
                    grid_key=parse_qs(urlparse(self.path).query).get('grid',[''])[0] or None
                    pc=bool(pc or grid_key)
                    key=(identifier,pc,grid_key)
                    with RAW_LOCK:
                        if key not in DIAGNOSTICS:
                            DIAGNOSTICS[key] = core.diagnostics(RUNS / identifier,pc,grid_key)
                    return self.respond(DIAGNOSTICS[key])
                if len(bits)==5 and bits[4]=='grid-training':
                    from grid_distillation import latest,load_result
                    state_path=RUNS/identifier/'grid_training.json'
                    state=json.loads(state_path.read_text()) if state_path.exists() else dict(status='idle')
                    from training_progress import read_progress
                    state['training_progress']=read_progress(RUNS/identifier/'grid_progress.json') if state['status']=='running' else None
                    requested_key=parse_qs(urlparse(self.path).query).get('key',[''])[0]
                    grid_key=requested_key or latest(RUNS/identifier)
                    if grid_key:
                        state['key']=grid_key
                        state['report']=load_result(RUNS/identifier,grid_key)[0]
                    return self.respond(state)
                if len(bits)==5 and bits[4]=='pc-download':
                    return self.respond((RUNS/identifier/'pc_compensation.json').read_bytes(), filename='PC-compensation.json')
                if len(bits)==5 and bits[4]=='grid-distillation-download':
                    from grid_distillation import download
                    key=parse_qs(urlparse(self.path).query).get('key',[''])[0]
                    return self.respond(download(RUNS/identifier,key),'application/zip',filename='native-sized-grid.zip')
                if len(bits)==5 and bits[4]=='grid-firmware-download':
                    from grid_distillation import firmware_config
                    key=parse_qs(urlparse(self.path).query).get('key',[''])[0]
                    return self.respond(firmware_config(RUNS/identifier,key),'application/zip',filename='r5-grid-v4-config.zip')
                if len(bits)==5 and bits[4]=='grid-firmware-config':
                    from grid_distillation import firmware_config
                    key=parse_qs(urlparse(self.path).query).get('key',[''])[0]
                    config=firmware_config(RUNS/identifier,key,configuration_only=True)
                    config['export_sources']={str(config['entries'][0]['number']):dict(kind='compressed',job=identifier,key=key)}
                    return self.respond(config)
                if len(bits) == 5 and bits[4] == 'download':
                    if job['status'] not in ('done', 'error'):
                        raise ValueError('任务尚未完成')
                    memory = io.BytesIO()
                    with zipfile.ZipFile(memory, 'w', zipfile.ZIP_DEFLATED) as archive:
                        # Only files from this job, never the original capture/RAW.
                        for name in ['native_config.json', 'conversion_audit.json',
                                     'input_audit.json', 'chart_target.json', 'target-image.bin', 'fit/recipe.json', 'pc_compensation.json', 'fit.log', 'error.log', 'job.json']:
                            source = RUNS / identifier / name
                            if source.is_file():
                                archive.write(source, name)
                        from grid_distillation import latest
                        grid_key=latest(RUNS/identifier)
                        if grid_key:
                            for name in ['result.json','teacher.json','grid.payload']:
                                archive.write(RUNS/identifier/'grid_distillation'/grid_key/name,'compressed/'+name)
                    return self.respond(memory.getvalue(), 'application/zip', filename='r5-fit-' + identifier + '.zip')
                if len(bits) != 4:
                    return self.respond(dict(error='Not found'), status=404)
                value = {k: v for k, v in job.items() if k != 'process'}
                previews = [p for p in PREVIEWS.values() if p['job'] == identifier and p['status'] == 'done']
                if previews:
                    value['photo_preview'] = previews[-1]
                    value['photo_previews'] = previews
                from training_progress import read_progress
                progress_name='grid_progress.json' if '压缩训练' in job.get('phase','') else 'training_progress.json'
                value['training_progress']=read_progress(RUNS/identifier/progress_name) if job['status']=='running' else None
                log = RUNS / identifier / 'fit.log'
                value['log'] = log.read_text(errors='replace')[-12000:] if log.exists() else ''
                return self.respond(value)
            assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                      '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                      '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if path in assets:
                name, mime = assets[path]
                return self.respond((STATIC / name).read_bytes(), mime)
            self.respond(dict(error='Not found'), status=404)
        except Exception as error:
            self.respond(dict(error=str(error)), status=400)

    def do_POST(self):
        if not self.trusted() or self.headers.get('X-R5-Token') != TOKEN:
            return self.respond(dict(error='Local session token required'), status=403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if urlparse(self.path).path == '/api/chart-target':
                if not 0 < length <= chart_target.MAX_BYTES or self.headers.get('Content-Type')!='application/octet-stream':
                    raise ValueError('请以二进制上传 1 GiB 内的 TIFF 或 JPG')
                data=self.rfile.read(length)
                if len(data)!=length:
                    raise ValueError('目标图上传不完整')
                dataset_id=parse_qs(urlparse(self.path).query).get('dataset_id',[None])[0]
                dataset_id=chart_datasets.get(dataset_id).DATASET_ID
                _, audit=chart_target.decode(data,dataset_id)
                identifier=uuid.uuid4().hex
                destination=core.HERE/'chart_uploads'/identifier
                destination.mkdir(parents=True)
                (destination/'source.bin').write_bytes(data)
                (destination/'audit.json').write_bytes(dump(audit))
                return self.respond(dict(id=identifier,audit=audit),status=201)
            if urlparse(self.path).path == '/api/preview':
                if not 0 < length <= 512*1024*1024 or self.headers.get('Content-Type') != 'application/octet-stream':
                    raise ValueError('请上传 512 MiB 内的 R5 RAW 二进制文件')
                job_id = parse_qs(urlparse(self.path).query).get('job', [''])[0]
                if job_id not in JOBS or not (RUNS/job_id/'fit/recipe.json').is_file() or not (RUNS/job_id/'input.cube').is_file():
                    raise ValueError('色卡目标仅支持色块验证；RAW 双图预览需要 LUT 目标和配方')
                with LOCK:
                    if any(p['status'] in ('queued', 'running') for p in PREVIEWS.values()):
                        return self.respond(dict(error='已有照片预览运行，请稍候'), status=409)
                    identifier = uuid.uuid4().hex
                    destination = RUNS/job_id/'photo_previews'/identifier
                    destination.mkdir(parents=True)
                    # Stream the original only into this isolated preview directory.
                    remaining = length
                    with (destination/'input.ARW').open('wb') as stream:
                        while remaining:
                            chunk = self.rfile.read(min(1024*1024, remaining))
                            if not chunk:
                                raise ValueError('RAW 上传不完整')
                            stream.write(chunk)
                            remaining -= len(chunk)
                    pc=parse_qs(urlparse(self.path).query).get('pc',['0'])[0]=='1'
                    grid_key=parse_qs(urlparse(self.path).query).get('grid',[''])[0] or None
                    if grid_key:
                        from grid_distillation import load_result
                        load_result(RUNS/job_id,grid_key)
                    PREVIEWS[identifier] = dict(id=identifier, job=job_id, status='queued', phase='等待渲染')
                    (destination/'preview.json').write_bytes(dump(PREVIEWS[identifier]))
                    PREVIEW_POOL.submit(preview_work, identifier, job_id, destination,pc,grid_key,None,parse_qs(urlparse(self.path).query).get('grid_effect',['1'])[0]!='0')
                return self.respond(dict(id=identifier), status=202)
            if urlparse(self.path).path == '/api/raw-export':
                if not 0 < length <= 512*1024*1024:
                    raise ValueError('ARW 大小必须在 512 MiB 内')
                if self.headers.get('Content-Type') != 'application/octet-stream':
                    raise ValueError('ARW 需以二进制上传')
                identifier = parse_qs(urlparse(self.path).query).get('job', [''])[0]
                job = JOBS.get(identifier)
                if not job or job['status'] not in ('done', 'error'):
                    raise ValueError('请先选择一个已完成的拟合任务')
                recipe = RUNS / identifier / 'fit/recipe.json'
                if not recipe.is_file():
                    raise ValueError('任务没有可用拟合配方')
                if not RAW_LOCK.acquire(blocking=False):
                    return self.respond(dict(error='已有 RAW 导出任务，请稍候'), status=409)
                try:
                    original = self.rfile.read(length)
                    if len(original) != length:
                        raise ValueError('ARW 上传不完整')
                    destination = RUNS / identifier / 'raw_exports' / uuid.uuid4().hex
                    audit = core.write_validation_raw(original, recipe, destination)
                    memory = io.BytesIO()
                    with zipfile.ZipFile(memory, 'w', zipfile.ZIP_STORED) as archive:
                        filename=audit.get('file','fitted-ST.ARW')
                        archive.write(destination / filename, filename)
                        audit_name=Path(filename).with_suffix('.audit.json').name
                        archive.write(destination / audit_name, audit_name)
                        archive.writestr('Edit验证说明.txt',
                            '本文件使用所选拟合任务的原始配方，非编辑器后续手动参数。\n'
                            '在 Imaging Edge Edit 中显式选择 '+audit.get('look','ST')+'。\n'
                            '关闭镜头补偿，保持白平衡、曝光、锐度和降噪等设置与对照一致后导出。\n'
                            'RAW 嵌入预览未重绘，不代表实际滤镜结果。传感器数据和其他外观参数保持。\n'
                            '任务ID：' + identifier + '\n配方SHA256：' + audit['recipe_sha256'] + '\n')
                    return self.respond(memory.getvalue(), 'application/zip', filename='r5-edit-validation.zip')
                finally:
                    RAW_LOCK.release()
            if not 0 < length <= MAX_BODY:
                raise ValueError('请求大小必须在 65 MiB 内')
            body = json.loads(self.rfile.read(length), object_pairs_hook=core.compiler.unique,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
            path = urlparse(self.path).path
            if path == '/api/preview-reuse':
                job_id=body.get('job');reuse_id=body.get('preview');item=PREVIEWS.get(reuse_id)
                if job_id not in JOBS or not item or item['job']!=job_id or item['status']!='done':
                    raise ValueError('RAW预览来源无效')
                if not (RUNS/job_id/'input.cube').is_file():
                    raise ValueError('色卡目标不提供任意 RAW 的目标照片渲染')
                source=RUNS/job_id/'photo_previews'/reuse_id
                if not (source/'render_inputs.npz').is_file():raise ValueError('历史预览没有缓存，请重新上传一次RAW')
                if item['result'].get('preview_long_edge') != 3840:raise ValueError('历史预览为低分辨率，请重新上传一次 RAW 生成 4K 对照图')
                if type(body.get('grid_effect',True)) is not bool:raise ValueError('网格效果开关必须为布尔值')
                grid_key=body.get('grid') or None
                if grid_key:
                    from grid_distillation import load_result
                    load_result(RUNS/job_id,grid_key)
                with LOCK:
                    if any(p['status'] in ('queued','running') for p in PREVIEWS.values()):raise ValueError('已有照片预览运行，请稍候')
                    identifier=uuid.uuid4().hex
                    destination=RUNS/job_id/'photo_previews'/identifier
                    destination.mkdir(parents=True)
                    PREVIEWS[identifier]=dict(id=identifier,job=job_id,status='queued',phase='复用同一RAW采样切换算法')
                    (destination/'preview.json').write_bytes(dump(PREVIEWS[identifier]))
                    PREVIEW_POOL.submit(preview_work,identifier,job_id,destination,body.get('pc',False),grid_key,reuse_id,body.get('grid_effect',True))
                return self.respond(dict(id=identifier),status=202)
            if path == '/api/grid-training':
                identifier=body.get('job')
                if identifier not in JOBS or JOBS[identifier]['status']!='done':raise ValueError('请先选择完成的PC补偿任务，或导入LUT开始新的压缩训练')
                from residual_grid import response_matrix
                from pc_compensation import load
                value,_=load(RUNS/identifier)
                if value.get('curves',{}).get('mode','tone-tint')!='tone-tint':raise ValueError('压缩训练需要明暗＋灰阶染色方案')
                response=response_json(body.get('response',default_response()))
                gray_refinement=False
                with LOCK:
                    state_path=RUNS/identifier/'grid_training.json'
                    if state_path.exists() and json.loads(state_path.read_text()).get('status') in ('running','queued'):raise ValueError('该任务压缩训练仍在运行')
                    state_path.write_bytes(dump(dict(status='queued',phase='等待压缩训练',started=time.time())))
                    POOL.submit(compression_work,identifier,response,gray_refinement)
                return self.respond(dict(job=identifier,status='queued'),status=202)
            if path == '/api/grid-distillation':
                identifier=body.get('job')
                if identifier not in JOBS or JOBS[identifier]['status']!='done':
                    raise ValueError('请先载入已完成的 PC 补偿任务')
                if not RAW_LOCK.acquire(blocking=False):
                    raise ValueError('已有文件处理任务，请稍候')
                try:
                    from grid_distillation import generate
                    return self.respond(generate(RUNS/identifier,body.get('response',default_response()),post_gray_refinement=body.get('post_gray_refinement',False)))
                finally:
                    RAW_LOCK.release()
            if path == '/api/pc-compensation':
                identifier=body.get('job')
                if identifier not in JOBS or JOBS[identifier]['status']!='done':
                    raise ValueError('请先载入已完成任务')
                if not RAW_LOCK.acquire(blocking=False):
                    raise ValueError('已有文件处理任务，请稍候')
                try:
                    from pc_compensation import generate
                    value=generate(RUNS/identifier)
                    for cache_key in list(DIAGNOSTICS):
                        if cache_key[0]==identifier:DIAGNOSTICS.pop(cache_key,None)
                    return self.respond(value)
                finally:
                    RAW_LOCK.release()
            if path == '/api/export':
                config, receipts = export_policy423.validate(body, RUNS)
                payload,compiler_path,firmware,version = core.compile_config(config)
                memory = io.BytesIO()
                with zipfile.ZipFile(memory, 'w', zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr('native_config.json', dump(body))
                    archive.writestr('R5NATIVE.BIN', payload)
                    archive.writestr('export_audit.json', dump(dict(schema='r5-web-export/1',
                        binary_sha256=core.sha(payload), bytes=len(payload), native_numbers=[e['number'] for e in body['entries']],
                        white_balance_in_binary=False, color_accuracy_accepted=False, firmware=firmware,format_version=version,
                        grid_required=True, config_numbers_are_independent=True, grid_sources=receipts,
                        SD_import_policy='replace-entire-set; missing selected configuration turns custom filter off',
                        compiler_sha256=core.sha(compiler_path.read_bytes()))))
                return self.respond(memory.getvalue(), 'application/zip', filename='r5-native-config.zip')
            if path == '/api/validate':
                value=export_policy423.configuration(body)
                if 'export_sources' in body:
                    value,_=export_policy423.validate(body,RUNS)
                data,_,_,_ = core.compile_config(value)
                return self.respond(dict(valid=True, bytes=len(data), sha256=core.sha(data)))
            if path == '/api/batches':
                return self.respond(batch_training.submit(body, sys.modules[__name__]), status=202)
            if path == '/api/fit':
                validate_fit(body)
                with LOCK:
                    if any(v['status'] in ('queued', 'running') for v in JOBS.values()):
                        return self.respond(dict(error='已有拟合任务运行，请完成或取消后再提交'), status=409)
                    identifier = uuid.uuid4().hex
                    JOBS[identifier] = dict(id=identifier, target_kind=body.get('target_kind','lut'), status='queued', phase='等待开始', started=time.time())
                    POOL.submit(work, identifier, body)
                return self.respond(dict(id=identifier), status=202)
            if path == '/api/cancel':
                job = JOBS.get(body.get('id'))
                if not job or job['status'] != 'running':
                    raise ValueError('任务未在运行')
                process = job.get('process')
                if process is None:
                    raise ValueError('正在验证或转换，请稍候')
                process.terminate()
                job['phase'] = '正在取消，保留已有日志'
                return self.respond(dict(ok=True))
            self.respond(dict(error='Not found'), status=404)
        except Exception as error:
            self.respond(dict(error=str(error)), status=400)


def main():
    os.environ.setdefault('R5_GPU_TRAINING','1')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4180)
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args()
    # Fail before opening the UI if local source files cannot be verified.
    core.presets()
    if RUNS.exists():
        for path in sorted(RUNS.glob('*/job.json')):
            if len(path.parent.name) != 32 or any(c not in '0123456789abcdef' for c in path.parent.name):
                continue
            try:
                job = json.loads(path.read_text())
                if job['id'] != path.parent.name:
                    continue
                native=json.loads((path.parent/'native_config.json').read_text())
                core.compiler.pack(native)
                if job['status'] in ('running','queued'):
                    job.update(status='error',phase='服务重启中断',error='请重新提交训练')
                JOBS[job['id']] = job
            except (ValueError, KeyError, OSError):
                continue
        for path in RUNS.glob('*/grid_training.json'):
            try:
                state=json.loads(path.read_text())
                if state['status'] in ('running','queued'):
                    state.update(status='error',phase='压缩训练被服务重启中断',error='请重新开始压缩训练')
                    path.write_bytes(dump(state))
            except (ValueError,KeyError,OSError):pass
        for path in RUNS.glob('*/photo_previews/*/preview.json'):
            try:
                item = json.loads(path.read_text())
                if item['id'] == path.parent.name and item['job'] == path.parents[2].name:
                    if item['status'] in ('queued','running'):
                        item.update(status='error',phase='预览被服务重启中断',error='请重新生成预览')
                        path.write_bytes(dump(item))
                    PREVIEWS[item['id']] = item
            except (ValueError, KeyError, OSError):
                continue
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    url = 'http://127.0.0.1:%d' % server.server_address[1]
    print('R5 色彩工作台：' + url, flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for job in JOBS.values():
            if job.get('process'):
                job['process'].terminate()
        server.server_close()
        POOL.shutdown(wait=True)
        PREVIEW_POOL.shutdown(wait=True)


if __name__ == '__main__':
    main()
