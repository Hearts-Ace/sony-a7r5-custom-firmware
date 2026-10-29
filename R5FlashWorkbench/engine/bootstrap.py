#!/usr/bin/env python3
"""Fixed local actions for the native macOS UI. Import/selfcheck never enumerates USB."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT),str(ROOT/'site'),str(ROOT/'vendor/pmca_source')]
import argparse, ctypes, datetime, fcntl, hashlib, json, os, re, shutil, stat, subprocess, traceback
from common import safe, save, load, sha, progress, render_template

FIRMWARE=ROOT.parent/'firmware/r5'
if not FIRMWARE.is_dir():
    FIRMWARE=ROOT.parents[1]/'firmware/r5'
DAT_SHA='76b06194aacd7b78553ad524e6d6fe0d7fc73edfae671e5ebc1e54bafe17ff74'
DAT_BYTES=754525608
APP_ID='R5FlashWorkbench'

def selfcheck():
    from Cryptodome.PublicKey import RSA
    from cryptography.hazmat.primitives.ciphers import Cipher
    import numpy, capstone, elftools, usb
    from pmca.usb.sony import SonySenserAuthDevice
    ctypes.CDLL(str(ROOT/'lib/libusb-1.0.dylib'))
    for name in load(ROOT/'templates.json')['files']:
        render_template(name,'0123456789abcdef0123456789abcdef')
    for name,expected in load(FIRMWARE/'sources.lock.json').items():
        if sha(FIRMWARE/name)!=expected:raise ValueError('固件构建源码散列不符：'+name)
    for name,expected in load(ROOT/'resources.lock.json').items():
        if sha(ROOT/name)!=expected:raise ValueError('USB 运行资源散列不符：'+name)
    public=RSA.import_key((ROOT/'public.pem').read_bytes())
    if public.has_private():raise ValueError('应用不允许携带签名私钥')
    plan=load(ROOT/'write-plan.json')
    if plan['changed_sectors']!=26 or plan['logical_write_bytes']!=13312:raise ValueError('信任写入计划变化')
    from card import filters
    return dict(ok=True,version='0.2.1',firmware='4.35',python=sys.version.split()[0],bundled_filters=filters(),
        platform='macOS arm64',USB_enumerated=False,camera_IO=False,templates_verified=True,
        signing_private_key_included=False,trust_sectors=26,firmware_DAT_sha256=DAT_SHA,
        compiler_available=Path('/Library/Developer/CommandLineTools/usr/bin/clang').is_file(),
        device_validation='未做本应用实机验收')

def verify_dat(path):
    path=safe(path,file=True)
    progress('核对 4.35 固件完整 SHA-256')
    if path.stat().st_size!=DAT_BYTES or sha(path)!=DAT_SHA:
        raise ValueError('文件不是我们已冻结的 4.35 BODYDATA.DAT；停止导出')
    return dict(ok=True,version='4.35',bytes=DAT_BYTES,sha256=DAT_SHA,file=str(path),camera_IO=False)

def export_dat(request,job):
    source=safe(request['firmware'],file=True);verify_dat(source)
    root=safe(request['destination'])
    if not root.is_dir():raise ValueError('目标目录不存在')
    target=root/'BODYDATA.DAT'
    if target.exists():raise ValueError('目标已存在 BODYDATA.DAT；请先自行保留或移走旧文件')
    progress('写入 BODYDATA.DAT，并重新读取核对')
    created=False
    try:
        with target.open('xb') as out,source.open('rb') as inp:
            created=True;shutil.copyfileobj(inp,out,4<<20);out.flush();os.fsync(out.fileno())
        if sha(target)!=DAT_SHA:raise ValueError('目标读回散列不符，文件不可用于升级')
    except BaseException:
        # Preserve incomplete output as evidence, never give it an installable DAT name.
        if created and target.exists():target.rename(root/('BODYDATA.INCOMPLETE-'+job.name))
        raise
    result=dict(ok=True,file=str(target),sha256=DAT_SHA,full_readback_verified=True,
        camera_IO=False,camera_upgrade_complete=False)
    save(job/'export.json',result);return result

def build_firmware(request,job):
    if request.get('original_dat'):
        from original_inputs import prepare
        config=prepare(request['original_dat'],request['private_key'],job/'original-inputs',FIRMWARE,ROOT)
    else:config=safe(request['inputs'],file=True)
    values=load(config)
    # Full original-input/source verification remains inside the one supported builder.
    output=safe(request['destination'])
    if output.exists():raise ValueError('构建输出必须是一个尚不存在的新目录')
    progress('启动唯一固件构建入口 firmware/r5/build.py；需要 Xcode Command Line Tools')
    if not shutil.which('clang'):raise ValueError('未找到 clang，请先安装 Apple Command Line Tools')
    # Reject keys that do not correspond to the installed/public signing identity, before compilation.
    from Cryptodome.PublicKey import RSA
    keypath=safe(values['private_key'],file=True)
    if stat.S_IMODE(keypath.stat().st_mode)!=0o600:raise ValueError('外部签名私钥权限须为 0600')
    key=RSA.import_key(keypath.read_bytes());public=RSA.import_key((ROOT/'public.pem').read_bytes())
    if not key.has_private() or (key.n,key.e)!=(public.n,public.e):raise ValueError('外部签名私钥与本项目公钥不匹配')
    process=subprocess.Popen([sys.executable,'-B',str(FIRMWARE/'build.py'),'--inputs',str(config),'--output',str(output)],
        env=dict(os.environ,PATH='/usr/bin:/bin:/usr/sbin:/sbin'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    for line in process.stdout:print(line,end='',flush=True)
    if process.wait():raise RuntimeError('统一构建失败；保留输出与日志，不导出未完成固件')
    return dict(verify_dat(output/'BODYDATA.DAT'),build_directory=str(output),unique_builder=True)

def device_action(request,job):
    if sys.platform!='darwin' or os.geteuid()!=0:raise PermissionError('USB 事务只能由 macOS 管理员授权入口执行')
    if request.get('kind') not in ('backup','update','recovery'):raise ValueError('设备动作无效')
    state=Path('/private/var/db/R5FlashWorkbench')
    state.mkdir(mode=0o700,parents=True,exist_ok=True)
    info=state.lstat()
    if stat.S_ISLNK(info.st_mode) or info.st_uid!=0 or info.st_mode&0o077:raise ValueError('设备锁目录属主或权限不符')
    fd=os.open(state/'device.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'r+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        pending=state/'pending.json'
        if request['kind']=='recovery':
            previous=safe(request['previous'],file=True);value=load(previous)
            from policy import pre_service_failure
            if value.get('task_complete') is not True and not pre_service_failure(value):
                raise ValueError('前次事务没有完整终态；仅可查看日志，禁止恢复重试')
            if pending.exists() and load(pending)['job']!=str(previous.parent):raise ValueError('不是待处理事务的记录')
            import host
            baseline=host.snapshot(job,'recovery-current')
            if baseline.get('kind')!='ordinary' or baseline.get('model')!='ILCE-7RM5':raise ValueError('未恢复到 MSC')
            if baseline.get('location_id')!=value['baseline']['location_id']:raise ValueError('恢复端口与前次事务不符')
            proof=host.observe(value['baseline'],lambda label,timeout=5:host.snapshot(job,label,timeout,baseline['location_id']))
            if not proof['recovered']:raise ValueError('MSC 媒体和驱动尚未稳定恢复')
            if pending.exists():pending.unlink()
            return dict(ok=True,USB_recovered=True,camera_protocol_requests=0,previous=str(previous))
        if pending.exists():raise ValueError('存在未完成设备事务：'+load(pending)['job']+'；先查看该记录，不重试')
        save(pending,dict(job=str(job),kind=request['kind'],run_id=request['run_id']))
        import device
        try:result=device.run(request,job)
        except Exception as error:
            attempted=(job/'ATTEMPT_LOCK').exists()
            result=dict(kind=request['kind'],task_complete=False,device_IO=attempted,
                can_replug=not attempted,automatic_retry=False,error=str(error))
        save(job/'result.json',result)
        if result.get('device_IO') is False or result.get('recovery_kind')=='pre_service_failure' or (
            result.get('task_complete') is True and result.get('USB_recovered') is True):pending.unlink()
        return result

def execute(action,request,job):
    if action=='selfcheck':return selfcheck()
    if action=='inspect':
        import host
        return dict(host.snapshot(job,'usb'),camera_protocol_requests=0)
    if action=='verify':return verify_dat(request['firmware'])
    if action=='export':return export_dat(request,job)
    if action in ('plan','prepare'):
        import card
        return card.plan(request,verify_dat) if action=='plan' else card.prepare(request,job,verify_dat)
    if action=='build':return build_firmware(request,job)
    if action=='device':return device_action(request,job)
    raise ValueError('未知动作')

def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('selfcheck','inspect','verify','export','plan','prepare','build','device'))
    p.add_argument('request',nargs='?',type=Path);p.add_argument('job',nargs='?',type=Path)
    a=p.parse_args();job=None;owner=None
    try:
        if a.action=='selfcheck' and a.request is None:result=selfcheck()
        else:
            job=safe(a.job);request_path=safe(a.request,file=True)
            if request_path.parent!=job or job.is_symlink():raise ValueError('任务路径不符')
            request=load(request_path);owner=request_path.stat().st_uid
            if job.stat().st_uid!=owner or job.stat().st_mode&0o077 or request_path.stat().st_mode&0o077:
                raise ValueError('任务文件和目录必须属于同一用户，且仅本人可读写')
            if not re.fullmatch('[0-9a-f]{32}',request.get('run_id','')):raise ValueError('任务编号无效')
            # Prevent duplicate clicks, replays and concurrent actions on this task.
            fd=os.open(job/'RUNNING',os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600);os.close(fd)
            if a.action=='device':
                if owner==0:raise ValueError('请由普通用户界面发起设备任务')
                log=os.open(job/'engine.log',os.O_CREAT|os.O_APPEND|os.O_WRONLY|os.O_NOFOLLOW,0o600)
                os.dup2(log,1);os.dup2(log,2);os.close(log)
                # Verify the packaged engine/firmware before opening any USB backend.
                selfcheck()
            result=execute(a.action,request,job)
            if not (job/'result.json').exists():save(job/'result.json',result)
        print(json.dumps(dict(result=result),ensure_ascii=False),flush=True)
        return 1 if result.get('error') else 0
    except Exception as error:
        value=dict(error=str(error),task_complete=False,automatic_retry=False)
        if job is not None and not (job/'result.json').exists():save(job/'result.json',value)
        print(json.dumps(value,ensure_ascii=False),flush=True)
        traceback.print_exc(file=sys.stderr);return 1
    finally:
        if job is not None and os.geteuid()==0 and owner is not None and owner!=0:
            # Return only files within this new task; no symlink traversal or external chown.
            for base,dirs,files in os.walk(job,followlinks=False):
                for name in [*dirs,*files]:
                    path=Path(base)/name
                    if not path.is_symlink():os.chown(path,owner,-1,follow_symlinks=False)
            os.chown(job,owner,-1,follow_symlinks=False)

if __name__=='__main__':sys.exit(main())
