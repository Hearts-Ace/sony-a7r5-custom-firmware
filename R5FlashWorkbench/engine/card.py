"""Prepare a card/folder using bundled BIN and optional verified project firmware."""
from pathlib import Path
import fcntl, hashlib, os, shutil, struct, tempfile, uuid
from common import ROOT, load, save, safe, sha, progress

def filters():
    metadata=load(ROOT/'filters/manifest.json');path=ROOT/'filters/R5NATIVE.BIN'
    if metadata['training_status']!='done' or metadata['file']!=path.name:
        raise ValueError('附带滤镜不是已完成的正式合包')
    if path.stat().st_size!=metadata['bytes'] or sha(path)!=metadata['sha256']:
        raise ValueError('附带滤镜校验失败')
    raw=path.read_bytes()
    if raw[:8]!=b'R5CUST4\0' or struct.unpack_from('<I',raw,16)[0]!=len(raw):raise ValueError('滤镜 BIN 格式或长度错误')
    if struct.unpack_from('<I',raw,20)[0]!=len(metadata['filters']):raise ValueError('滤镜数量不符')
    return dict(metadata,path=str(path),count=len(metadata['filters']))

def plan(request,verify_firmware):
    root=safe(Path(request['destination']).expanduser().resolve())
    if not root.is_dir():raise ValueError('请选择已存在的存储卡根目录或文件夹')
    selected=filters();sources=[]
    if request.get('firmware'):
        source=safe(Path(request['firmware']).expanduser().resolve(),file=True)
        verified=verify_firmware(source);sources.append(dict(file='BODYDATA.DAT',source=str(source),bytes=verified['bytes'],sha256=verified['sha256']))
    sources.append(dict(file='R5NATIVE.BIN',source=selected['path'],bytes=selected['bytes'],sha256=selected['sha256']))
    for row in sources:
        target=root/row['file']
        if target.is_symlink():raise ValueError('目标文件是符号链接，不能替换：'+row['file'])
        current=sha(safe(target,file=True)) if target.exists() else None
        row.update(current_sha256=current,action='unchanged' if current==row['sha256'] else 'backup_and_replace' if current else 'create')
    return dict(ok=True,schema='r5-card-plan/1',destination=str(root),files=sources,
        filters=dict(count=selected['count'],sha256=selected['sha256'],source_batch=selected['source_batch'],dataset=selected['dataset']),
        requires_administrator=False,will_contact_camera=False,camera_upgrade_complete=False,
        bytes_to_copy=sum(r['bytes'] for r in sources if r['action']!='unchanged'))

def prepare(request,job,verify_firmware):
    destination=safe(Path(request['destination']).expanduser().resolve())
    if not destination.is_dir():raise ValueError('目标目录不存在')
    state=Path(os.environ.get('R5_WORKBENCH_STATE_DIR',Path.home()/'Library/Application Support/R5FlashWorkbench')).expanduser().resolve()
    lockroot=state/'Locks';lockroot.mkdir(parents=True,exist_ok=True,mode=0o700)
    lockname=hashlib.sha256(str(destination).encode()).hexdigest()+'.lock'
    fd=os.open(lockroot/lockname,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'r+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        value=plan(request,verify_firmware);save(job/'prepare-plan.json',value)
        if shutil.disk_usage(destination).free<value['bytes_to_copy']+1048576:raise ValueError('目标可用空间不足')
        completed=[];run=uuid.uuid4().hex
        backup=destination/'.R5Workbench-backups'/run
        if (destination/'.R5Workbench-backups').is_symlink():raise ValueError('旧文件备份目录不能是符号链接')
        with tempfile.TemporaryDirectory(prefix='.r5wb-stage-',dir=destination) as folder:
            stage=Path(folder)
            # Every new file must pass full readback before any current file is replaced.
            for row in value['files']:
                if row['action']=='unchanged':continue
                progress('正在准备 '+row['file'])
                with Path(row['source']).open('rb') as source,(stage/row['file']).open('xb') as out:
                    shutil.copyfileobj(source,out,4<<20);out.flush();os.fsync(out.fileno())
                if sha(stage/row['file'])!=row['sha256']:raise ValueError('临时文件完整读回不符：'+row['file'])
            for row in value['files']:
                target=destination/row['file']
                if target.is_symlink():raise ValueError('目标在准备期间发生变化')
                current=sha(safe(target,file=True)) if target.exists() else None
                if current!=row['current_sha256']:raise ValueError('目标在准备期间被其它程序修改：'+row['file'])
                backup_path=None
                if row['action']=='backup_and_replace':
                    backup.mkdir(parents=True,exist_ok=True)
                    backup_path=backup/row['file'];os.replace(target,backup_path)
                if row['action']!='unchanged':os.replace(stage/row['file'],target)
                if sha(target)!=row['sha256']:raise ValueError('最终文件读回不符：'+row['file'])
                completed.append(dict(file=str(target),sha256=row['sha256'],action=row['action'],
                    backup=str(backup_path) if backup_path else None,full_readback_verified=True))
                save(job/('prepared-'+row['file']+'.json'),completed[-1])
            fd=os.open(destination,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try:os.fsync(fd)
            finally:os.close(fd)
        return dict(ok=True,schema='r5-card-result/1',destination=str(destination),files=completed,
            filters=value['filters'],camera_IO=False,camera_upgrade_complete=False,
            next_step='仅更新滤镜：弹出存储卡并按已有固件的滤镜加载流程使用' if len(completed)==1 else '弹出存储卡，在相机机身菜单启动固件更新')
