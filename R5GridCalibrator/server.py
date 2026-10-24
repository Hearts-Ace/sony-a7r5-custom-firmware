"""Local-only independent grid calibration service."""
from pathlib import Path
import argparse,base64,copy,hashlib,io,json,threading,uuid,zipfile,webbrowser
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import numpy as np
import bin_v4,images,model,probe_sets
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'workspace'
LOCK=threading.Lock();JOBS={};FIT_LOCK=threading.Lock()

def uid(value):
    if not isinstance(value,str) or len(value)!=32 or any(c not in '0123456789abcdef' for c in value):raise ValueError('无效ID')
    return value

def blob(value,limit):
    if not isinstance(value,str) or len(value)>limit*4//3+8:raise ValueError('上传文件过大')
    b=base64.b64decode(value,validate=True)
    if len(b)>limit:raise ValueError('上传文件过大')
    return b

def config(value):return bin_v4.unpack(blob(value,bin_v4.MAXIMUM))
def grid(entry):return np.asarray(entry['grid_5x9x9']['coefficients']).reshape(3,405).T.tolist()
def parameters(e):return {k:e[k] for k in ('cc1_delta','block13','gamma_native_129')}
def entry(cfg,number):
    found=[e for e in cfg['entries'] if e['number']==int(number)]
    if not found:raise ValueError('BIN中没有所选配置')
    return found[0]

def save_pair(data):
    if data.get('confirmed') is not True:raise ValueError('请确认两图除网格外的参数及拍摄条件相同')
    cfg=config(data['bin']);e=entry(cfg,data['number']);g=grid(e)
    if not np.any(g):raise ValueError('带网格BIN的所选表为全零，请选实际使用的非零网格')
    before=blob(data['before'],96*1024**2);after=blob(data['after'],96*1024**2)
    if hashlib.sha256(before).digest()==hashlib.sha256(after).digest():raise ValueError('两张图文件完全相同')
    baseline_verified=False
    if data.get('baseline_bin'):
        be=entry(config(data['baseline_bin']),data.get('baseline_number',data['number']))
        if parameters(be)!=parameters(e) or np.any(grid(be)):raise ValueError('基准BIN必须与目标CC1/block13/Gamma相同，且网格全零')
        baseline_verified=True
    role=data.get('role','train')
    if role not in ('train','validation','test'):raise ValueError('未知样本用途')
    samples,audit=images.sample(before,after)
    pairid=uuid.uuid4().hex;out=DATA/'pairs'/pairid;out.mkdir(parents=True)
    audit.update(id=pairid,name=str(data.get('name','样本'))[:100],role=role,entry_number=e['number'],short_name=e['short_name'],full_name=e['full_name'],
                 bin_sha256=hashlib.sha256(blob(data['bin'],bin_v4.MAXIMUM)).hexdigest(),baseline_bin_verified=baseline_verified,
                 parameter_sha256=hashlib.sha256(json.dumps(parameters(e),sort_keys=True).encode()).hexdigest(),
                 base_look=str(data.get('base_look','未记录'))[:50],notes=str(data.get('notes',''))[:1000])
    (out/'pair.json').write_text(json.dumps(dict(**samples,grid=g,role=role,audit=audit),ensure_ascii=False))
    (out/'config.json').write_text(json.dumps(cfg,ensure_ascii=False))
    # Original inputs retained locally for provenance and later inspection.
    (out/'before.image').write_bytes(before);(out/'after.image').write_bytes(after)
    return audit

def create_set(data):
    raw=blob(data['bin'],bin_v4.MAXIMUM)
    packed,meta=probe_sets.build(raw,data['number'],data.get('amplitude',12))
    out=DATA/'sets'/meta['id'];out.mkdir(parents=True)
    (out/'R5NATIVE.BIN').write_bytes(packed);(out/'source.bin').write_bytes(raw)
    (out/'manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
    return meta

def capture(data):
    setid=uid(data['set_id']);meta=json.loads((DATA/'sets'/setid/'manifest.json').read_text())
    if data.get('confirmed') is not True:raise ValueError('请确认固定拍摄条件，并使用1 ZERO作基准')
    raw=blob(data['baseline'],96*1024**2)
    images.decode(raw)
    cid=uuid.uuid4().hex;out=DATA/'captures'/cid;out.mkdir(parents=True)
    info=dict(id=cid,set_id=setid,name=str(data.get('name','场景1'))[:100],base_look=str(data.get('base_look','ST'))[:40],
              conditions=str(data.get('conditions',''))[:1000],baseline_sha256=hashlib.sha256(raw).hexdigest())
    (out/'baseline.image').write_bytes(raw);(out/'capture.json').write_text(json.dumps(info,ensure_ascii=False))
    return info

def capture_photo(data):
    cid=uid(data['capture_id']);cap=DATA/'captures'/cid;info=json.loads((cap/'capture.json').read_text())
    sid=uid(info['set_id']);meta=json.loads((DATA/'sets'/sid/'manifest.json').read_text())
    number=int(data['number']);raw=blob(data['image'],96*1024**2);base=(cap/'baseline.image').read_bytes()
    if number==1:
        samples,audit=images.sample(base,raw)
        drift=model.metric(np.asarray(samples['x']),np.asarray(samples['y']))
        audit['drift']=drift;(cap/'repeat_zero.json').write_text(json.dumps(audit,ensure_ascii=False))
        return dict(drift=drift,message='基准重复拍摄已记录；不参与模型训练')
    if not 2<=number<=12:raise ValueError('探针编号须为2–12')
    old=cap/f'probe_{number}.json'
    if old.exists():raise ValueError('该探针已上传；更换照片请新建采集批次，以保留原始对应关系')
    cfg=bin_v4.unpack((DATA/'sets'/sid/'R5NATIVE.BIN').read_bytes());e=entry(cfg,number)
    if not np.any(grid(e)):raise ValueError('该探针为全零，无需上传；请使用其他非零探针')
    payload=dict(confirmed=True,bin=base64.b64encode(bin_v4.pack(cfg)).decode(),number=number,
                 before=base64.b64encode(base).decode(),after=base64.b64encode(raw).decode(),
                 baseline_bin=base64.b64encode(bin_v4.pack(cfg)).decode(),baseline_number=1,
                 role=meta['entries'][number-1]['role'],name=info['name']+' / '+e['short_name'],base_look=info['base_look'],notes=info['conditions'])
    audit=save_pair(payload)
    pairfile=DATA/'pairs'/audit['id']/'pair.json';pair=json.loads(pairfile.read_text())
    pair['audit'].update(capture_id=cid,set_id=sid,probe_number=number);pairfile.write_text(json.dumps(pair,ensure_ascii=False))
    old.write_text(json.dumps(dict(pair_id=audit['id'],number=number),ensure_ascii=False))
    return pair['audit']

def run_fit(jobid,pairids,refine,options=None):
    out=DATA/'fits'/jobid
    try:
        pairs=[json.loads((DATA/'pairs'/uid(p)/'pair.json').read_text()) for p in pairids]
        def progress(message):
            with LOCK:JOBS[jobid]['message']=message
        identities={(p['audit']['parameter_sha256'],p['audit']['base_look']) for p in pairs}
        if len(identities)!=1:raise ValueError('一次拟合必须使用同一套非网格参数和原厂创意外观；请分开计算')
        if not any(p['role']=='test' for p in pairs):raise ValueError('请上传至少一张留出测试探针图')
        result=model.fit(pairs,progress,refine,options)
        caps={p['audit'].get('capture_id') for p in pairs}-{None}
        drift=[]
        for cid in caps:
            path=DATA/'captures'/uid(cid)/'repeat_zero.json'
            if path.exists():
                check=json.loads(path.read_text());drift.append(dict(capture_id=cid,**check['drift']))
                if check['drift']['rmse']>1:result['report']['warnings'].append('重复ZERO差异超过1级，可能光线/机位漂移；请检查后重拍')
        result['report']['repeat_zero_checks']=drift
        result['provenance']=[p['audit'] for p in pairs]
        result['scope']='sRGB encoded paired-image empirical model, baseline=identical non-grid parameters plus zero grid; no unique ISP identification'
        (out/'model.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        with LOCK:JOBS[jobid].update(state='done',message='拟合完成',result=result)
    except Exception as exc:
        with LOCK:JOBS[jobid].update(state='error',message=str(exc))
    finally:
        with LOCK:snapshot=copy.deepcopy(JOBS[jobid])
        (out/'status.json').write_text(json.dumps(snapshot,ensure_ascii=False))
        FIT_LOCK.release()

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,data,status=200,mime='application/json; charset=utf-8',filename=None):
        if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)))
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store')
        if filename:self.send_header('Content-Disposition','attachment; filename="'+filename+'"')
        self.end_headers();self.wfile.write(data)
    def safe_origin(self):
        allowed={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        if self.headers.get('Host') not in allowed:raise ValueError('仅允许本机访问')
        origin=self.headers.get('Origin')
        if origin and origin not in {'http://'+h for h in allowed}:raise ValueError('不接受跨站请求')
    def do_GET(self):
        try:
            self.safe_origin();path=self.path.split('?')[0]
            if path=='/api/sets':
                return self.send([json.loads(p.read_text()) for p in sorted((DATA/'sets').glob('*/manifest.json'))])
            if path=='/api/captures':
                captures=[]
                for p in sorted((DATA/'captures').glob('*/capture.json')):
                    c=json.loads(p.read_text());c['uploaded']=[json.loads(q.read_text()) for q in p.parent.glob('probe_*.json')]
                    c['repeat_zero']=(p.parent/'repeat_zero.json').exists();captures.append(c)
                return self.send(captures)
            if path.startswith('/api/probe-download/'):
                sid=uid(path.rsplit('/',1)[-1]);folder=DATA/'sets'/sid
                return self.send(probe_sets.archive((folder/'R5NATIVE.BIN').read_bytes(),json.loads((folder/'manifest.json').read_text())),mime='application/zip',filename='R5-grid-probes.zip')
            if path=='/api/pairs':
                return self.send([json.loads(p.read_text())['audit'] for p in sorted((DATA/'pairs').glob('*/pair.json'))])
            if path.startswith('/api/status/'):
                jid=uid(path.rsplit('/',1)[-1])
                with LOCK:state=copy.deepcopy(JOBS.get(jid))
                if state is None:
                    p=DATA/'fits'/jid/'status.json'
                    if not p.exists():raise ValueError('任务不存在')
                    state=json.loads(p.read_text())
                return self.send(state)
            if path.startswith('/api/export/'):
                jid=uid(path.rsplit('/',1)[-1]);m=DATA/'fits'/jid/'model.json'
                if not m.exists():raise ValueError('模型尚未完成')
                z=io.BytesIO()
                with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as a:
                    a.writestr('model.json',m.read_bytes());a.write(ROOT/'model.py','model.py')
                    a.writestr('使用说明.txt','此模型为独立反推工具导出，尚未自动接入R5ColorLab。Python调用：model.predict(rgb_Nx3_0to1, grid_405x3, json.load(model.json))。需numpy/scipy。网格三通道排列遵守BIN原顺序。含训练来源和留出误差；不能声称唯一恢复ISP或跨外观/ISO/WB通用。\n')
                return self.send(z.getvalue(),mime='application/zip',filename='R5-grid-response.zip')
            static={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
            if path not in static:return self.send({'error':'不存在'},404)
            name=static[path];mime={'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8'}[name.rsplit('.',1)[1]]
            return self.send((ROOT/'static'/name).read_bytes(),mime=mime)
        except (ValueError,FileNotFoundError) as e:self.send({'error':str(e)},400)
    def do_POST(self):
        try:
            self.safe_origin();size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=280*1024**2:raise ValueError('请求过大或为空')
            data=json.loads(self.rfile.read(size));path=self.path
            if path=='/api/bin':
                cfg=config(data['bin']);return self.send({'entries':[dict(number=e['number'],short_name=e['short_name'],full_name=e['full_name'],nonzero=int(np.count_nonzero(grid(e)))) for e in cfg['entries']]})
            if path=='/api/pair':return self.send(save_pair(data))
            if path=='/api/probes':return self.send(create_set(data))
            if path=='/api/capture':return self.send(capture(data))
            if path=='/api/photo':return self.send(capture_photo(data))
            if path=='/api/fit':
                ids=data['pairs']
                if not isinstance(ids,list) or not 1<=len(ids)<=100 or len(ids)!=len(set(ids)):raise ValueError('请选择1–100个不同样本')
                for p in ids:
                    if not (DATA/'pairs'/uid(p)/'pair.json').exists():raise ValueError('样本不存在')
                options=model.optimization_options(data.get('options'))
                if not FIT_LOCK.acquire(blocking=False):raise ValueError('已有拟合在运行')
                jid=uuid.uuid4().hex;(DATA/'fits'/jid).mkdir(parents=True)
                with LOCK:JOBS[jid]=dict(id=jid,state='running',message='准备数据')
                threading.Thread(target=run_fit,args=(jid,ids,bool(data.get('refine',True)),options),daemon=True).start()
                return self.send({'id':jid})
            return self.send({'error':'不存在'},404)
        except (ValueError,KeyError,TypeError,FileNotFoundError) as e:self.send({'error':str(e)},400)
        except Exception as e:self.send({'error':f'文件处理失败（{type(e).__name__}）：{str(e)[:300]}'},400)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=4190);parser.add_argument('--no-browser',action='store_true');a=parser.parse_args()
    for d in ('pairs','fits','sets','captures'):(DATA/d).mkdir(parents=True,exist_ok=True)
    # A fit directory with no completion receipt was interrupted.
    for folder in (DATA/'fits').iterdir():
        if folder.is_dir() and not (folder/'status.json').exists():
            (folder/'status.json').write_text(json.dumps(dict(id=folder.name,state='error',message='服务重启，拟合中断，请重新开始'),ensure_ascii=False))
    # Recover interrupted fit states explicitly.
    for p in (DATA/'fits').glob('*/status.json'):
        s=json.loads(p.read_text())
        if s.get('state')=='running':s.update(state='error',message='服务重启，拟合中断，请重新开始');p.write_text(json.dumps(s,ensure_ascii=False))
    server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler)
    print(f'R5 网格反推工具：http://127.0.0.1:{a.port}',flush=True)
    if not a.no_browser:webbrowser.open(f'http://127.0.0.1:{a.port}')
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
