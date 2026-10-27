"""Persistent folder training, using the same validation and export provenance gates."""
import copy
import json
import re
import time
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor


def folder_names(files):
    if not isinstance(files, list) or not 1 <= len(files) <= 12:
        raise ValueError('每批需 1–12 张 JPG / TIFF；不会截断或漏掉滤镜')
    names=[]
    for item in files:
        filename=item['filename']
        if not isinstance(filename,str) or '/' in filename or '\\' in filename or not re.search(r'\.(jpe?g|tiff?)$',filename,re.I):
            raise ValueError('目标文件名无效')
        name=filename.rsplit('.',1)[0]
        if not name.strip() or '\0' in name or len(name.encode('utf-8'))>23:
            raise ValueError('简称须为 1–23 个 UTF-8 字节：'+filename)
        if name.casefold() in {n.casefold() for n in names}:
            raise ValueError('去掉后缀后的名称重复：'+name)
        names.append(name)
    return names


def save(path,value,server):
    temporary=path.with_suffix('.tmp')
    temporary.write_bytes(server.dump(value));temporary.replace(path)


def submit(body,server):
    files=body.get('files');names=folder_names(files)
    concurrency=body.get('concurrency',2)
    if type(concurrency) is not int or not 1 <= concurrency <= 3:
        raise ValueError('批量并发数必须为1–3')
    jobs=[]
    for number,(item,name) in enumerate(zip(files,names),1):
        options=copy.deepcopy(body.get('options',{}))
        options.update(target_kind='chart-image',target_id=item['target_id'],number=number,
                       short_name=name,full_name=item.get('full_name',name),compression_training=True,white_balance=False,post_gray_refinement=False)
        # The 129th point is an export-only endpoint, outside the fitted 128-point model.
        if options.get('gamma_endpoint128') is None:options['gamma_endpoint128']=131071
        server.validate_fit(options)
        jobs.append(dict(id=uuid.uuid4().hex,filename=item['filename'],name=name,options=options))
    with server.LOCK:
        if any(j['status'] in ('queued','running') for j in server.JOBS.values()):
            raise ValueError('已有训练运行，请完成后提交批量任务')
        identifier=uuid.uuid4().hex
        destination=server.core.HERE/'batches'/identifier;destination.mkdir(parents=True)
        state=dict(id=identifier,status='queued',started=time.time(),jobs=jobs,concurrency=concurrency)
        save(destination/'batch.json',state,server)
        for item in jobs:
            server.JOBS[item['id']]=dict(id=item['id'],target_kind='chart-image',status='queued',phase='批量等待：'+item['name'],started=time.time())
        server.POOL.submit(run,state,destination,server)
    return dict(id=identifier)


def run(state,destination,server):
    state['status']='running';save(destination/'batch.json',state,server)
    try:
        entries=[];sources={}
        from grid_distillation import firmware_config
        # Independent job directories and fitter subprocesses; merge in filename order.
        with ThreadPoolExecutor(max_workers=state.get('concurrency',1)) as pool:
            futures=[pool.submit(server.work,item['id'],item['options']) for item in state['jobs']]
            for future in futures:future.result()
        for item in state['jobs']:
            job=server.JOBS[item['id']]
            if job['status']!='done':
                raise ValueError(item['filename']+'：'+job.get('error','训练失败'))
            key=job['result']['grid_key']
            config=firmware_config(server.RUNS/item['id'],key,configuration_only=True)
            entry=config['entries'][0];entries.append(entry)
            sources[str(entry['number'])]=dict(kind='compressed',job=item['id'],key=key)
        project=server.core.config(entries);project['export_sources']=sources
        config,receipts=server.export_policy423.validate(project,server.RUNS)
        payload,_,firmware,version=server.core.compile_config(config)
        (destination/'R5NATIVE.BIN').write_bytes(payload)
        (destination/'native_config.json').write_bytes(server.dump(project))
        (destination/'export_audit.json').write_bytes(server.dump(dict(bytes=len(payload),sha256=server.core.sha(payload),grid_sources=receipts,firmware=firmware,format_version=version,color_accuracy_accepted=False)))
        state.update(status='done',sha256=server.core.sha(payload),bytes=len(payload))
    except Exception as error:
        state.update(status='error',error=str(error))
        for item in state['jobs']:
            job=server.JOBS[item['id']]
            if job['status']=='queued':job.update(status='error',phase='批量停止',error=str(error))
    finally:
        state['finished']=time.time();save(destination/'batch.json',state,server)


def get(handler,path,server):
    parts=path.strip('/').split('/')
    if len(parts) not in (3,4) or not re.fullmatch('[0-9a-f]{32}',parts[2]):raise ValueError('批量编号无效')
    destination=server.core.HERE/'batches'/parts[2]
    state=json.loads((destination/'batch.json').read_text())
    if len(parts)==4:
        if state['status']!='done' or parts[3] not in ('R5NATIVE.BIN','native_config.json','export_audit.json'):raise ValueError('完整批量结果尚未就绪')
        return handler.respond((destination/parts[3]).read_bytes(),'application/octet-stream',filename=parts[3])
    jobs=[]
    for item in state['jobs']:
        job=server.JOBS.get(item['id'])
        if job is None:
            saved=server.RUNS/item['id']/'job.json'
            job=json.loads(saved.read_text()) if saved.exists() else dict(status='error',phase='服务重启中断，请重新提交')
        from training_progress import read_progress
        progress_name='grid_progress.json' if '压缩训练' in job.get('phase','') else 'training_progress.json'
        progress=read_progress(server.RUNS/item['id']/progress_name) if job['status']=='running' else None
        jobs.append(dict(id=item['id'],name=item['name'],status=job['status'],phase=job['phase'],error=job.get('error'),training_progress=progress))
    state['jobs']=jobs
    if state['status'] in ('running','queued') and not any(j['status'] in ('queued','running') for j in jobs):
        state.update(status='error',error='服务重启中断，请重新提交；已完成训练保留在历史记录')
    return handler.respond(state)


def latest(root):
    paths=list((root/"batches").glob("*/batch.json"))
    return max(paths,key=lambda p:p.stat().st_mtime).parent.name if paths else None
