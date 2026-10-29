# Adapted for R5FlashWorkbench, 2026-10-29. See THIRD_PARTY_NOTICES.md.
from pathlib import Path
import base64, shutil
from common import ROOT, SOURCE_SHA, TARGET_SHA, PARTITION_BYTES, config, digest, load, render_template, safe, save, sha, write_payload
from capture_operation import Operation as CaptureOperation
from trust_operation import Operation as TrustOperation


def package_base(job, run, baseline):
    package = job/'package';package.mkdir(mode=0o700)
    (package/'materials').mkdir(mode=0o700)
    cfg = config(run, baseline)
    return package, cfg

def prepare_capture(job, run, baseline, *, probe=False):
    if probe:raise ValueError('Work probe is not included')
    template='capture.so'
    if load(ROOT/'templates.json')['files'].get(template,{}).get('control_layout')!='ram-v2':
        raise ValueError('捕获模板不支持RAM控制文件，请重新构建客户端；未开始上传')
    package, cfg = package_base(job, run, baseline)
    cfg.update(capture_path='/tmp_wbshd/a7r5-capture-'+run+'/partition.bin',
               capture_control_layout='ram-v2',
               expected_output_begin='A7R5_CAPTURE_BEGIN '+run+'\n', expected_output_end='A7R5_CAPTURE_END '+run+'\n')
    if not probe:
        if load(ROOT/'templates.json')['files'][template].get('capture_format')!='ram-16k-v1':
            raise ValueError('捕获模板分块布局不符，请重新构建客户端；未开始上传')
        cfg['capture_format']='ram-16k-v1'
        if load(ROOT/'templates.json')['files'].get('capture-cleanup.so',{}).get('cleanup_policy')!='verified-current-ram-v2':
            raise ValueError('缺少本次RAM副本清理模板，请重新构建客户端；未开始上传')
        cfg['capture_cleanup_policy']='verified-current-ram-v2'
        write_payload(package/'materials/capture-cleanup.so',render_template('capture-cleanup.so',run))
    save(package/'config.json', cfg)
    write_payload(package/'materials/libJit.so', render_template(template, run))
    write_payload(package/'materials/ticket.bin', ('A7R5_LIBJIT '+run+'\n').encode())
    return package, CaptureOperation(package)

def prepare_update(job, run, baseline, backup_manifest, *, force=False):
    if type(force) is not bool:raise ValueError('强制模式标记必须为布尔值')
    if force:raise ValueError('Force install is not supported')
    if backup_manifest is None:raise ValueError('请选择真实原厂备份记录，或明确选择强制安装')
    record = load(backup_manifest)
    if (record.get('kind') != 'backup' or not record.get('task_complete') or record.get('device_IO') is not True
            or record.get('simulation') is not False or record.get('backup_sha256') != SOURCE_SHA):
        raise ValueError('需要已完成且匹配原厂4.00前像的真实备份记录')
    before = safe(record['backup_file'], file=True).read_bytes()
    sectors = load(ROOT/'trust-sectors.json')
    if len(before) != PARTITION_BYTES or digest(before) != SOURCE_SHA:raise ValueError('备份文件变化或未适配')
    candidate = bytearray(before)
    for row in sectors['rows']:
        at = row['offset'];old = base64.b64decode(row['before'], validate=True);new = base64.b64decode(row['after'], validate=True)
        if len(old) != 512 or len(new) != 512 or candidate[at:at+512] != old:raise ValueError('备份扇区前像不符')
        candidate[at:at+512] = new
    if digest(candidate) != TARGET_SHA:raise ValueError('完整候选摘要不符')
    package, cfg = package_base(job, run, baseline)
    # 当前支持的SSH基础为原厂512换行；两种已知预加载分别有独立载荷。
    preload_name = record['preload_name']
    values = dict(cfg['preload_baselines'])
    if preload_name not in values:raise ValueError('备份预加载类型未适配')
    if load(ROOT/'templates.json')['files'].get('trust-'+preload_name+'.so',{}).get('control_layout')!='ram-v2':
        raise ValueError('信任更新模板不支持RAM控制文件，请重新构建客户端；未开始上传')
    ram = '/tmp_wbshd/a7r5-trust-'+run
    cfg.update(trust_control_layout='ram-v2',expected_preload_hex=values[preload_name], ram_dir=ram, journal_path=ram+'/journal',
               readback_path=ram+'/partition.logical', partition_bytes=PARTITION_BYTES,
               candidate_sha256=TARGET_SHA, source_sha256=SOURCE_SHA,
               expected_output_begin='A7R5_TRUST_BEGIN_'+run+'\n', expected_output_end='A7R5_TRUST_END_'+run+'\n')
    save(package/'config.json', cfg)
    write_payload(package/'materials/libJit.so', render_template('trust-'+preload_name+'.so', run))
    write_payload(package/'materials/ticket.bin', ('A7R5_LIBJIT '+run+'\n').encode())
    write_payload(package/'materials/candidate.logical.img', candidate)
    shutil.copyfile(ROOT/'write-plan.json', package/'materials/write-plan.json')
    return package, TrustOperation(package)
