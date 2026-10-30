"""MSC transactions adapted from Liwenru88/a7r5-rea (290c79e), 2026-10-29.

Only backup and normal installation of OUR public key are exposed. No fastboot,
force mode, SSH, setting-partition migration or firmware flashing over USB.
"""
from pathlib import Path
import os
from common import PARTITION_BYTES, SOURCE_SHA, TARGET_SHA, load, save, sha, progress
from preparation import prepare_capture, prepare_update
from policy import pre_service_failure
import host


def run(request, job, *, session_module=None, host_module=host):
    if os.geteuid()!=0 and session_module is None:raise PermissionError('需要 macOS 管理员授权')
    kind=request['kind'];run_id=request['run_id']
    if kind not in ('backup','update') or request.get('force_install',False):
        raise ValueError('仅支持备份和标准信任安装')
    before=host_module.snapshot(job,'initial')
    if (before.get('kind')!='ordinary' or before.get('model')!='ILCE-7RM5'
            or not before.get('media') or not before.get('drivers')):
        raise ValueError('未识别到 ILCE-7RM5 的普通 USB／MSC 连接；未开始设备事务')
    if kind=='backup':package,operation=prepare_capture(job,run_id,before)
    else:package,operation=prepare_update(job,run_id,before,request.get('backup_manifest'))
    if session_module is None:
        from system_dump import session as session_module
    save(job/'baseline.json',before)
    (job/'ATTEMPT_LOCK').mkdir(mode=0o700)
    operation.output=job/'session'
    progress('正在备份更新器分区' if kind=='backup' else '正在安装匹配 4.36 的更新公钥；保持供电和 USB 连接')
    report=session_module.run_session(operation.output,'libusb',_operation=operation)
    save(job/'session-result.json',report)
    writes,triggers=(4,2) if kind=='backup' else (2,1)
    verified=report.get('capture_verified' if kind=='backup' else 'complete_partition_readback_verified') is True
    operation_complete=(not report.get('failure') and report.get('protocol_gate_passed') is True
        and report.get('preload_unchanged') is True and report.get('fixed_writes_attempted')==writes
        and report.get('trigger_attempts')==triggers and report.get('service_stop_attempts')==1 and verified)
    if kind=='backup':operation_complete=operation_complete and report.get('capture_cleanup_verified') is True
    if kind=='update':
        plan=load(Path(__file__).parent/'write-plan.json')
        operation_complete=operation_complete and report.get('patch_sectors')==plan['changed_sectors']
    complete=operation_complete and report.get('service_stop_result')=='returned'
    value=dict(kind=kind,run_id=run_id,task_complete=bool(complete),device_IO=True,
        simulation=session_module.__name__!='system_dump.session',USB_recovered=False,
        screen_confirmation_pending=True,can_replug=bool(complete),automatic_retry=False,baseline=before,report=report)
    if kind=='backup' and report.get('capture_verified') is True and report.get('backup_persisted') is True:
        raw=job/'session/partition1.logical.bin'
        if raw.stat().st_size!=PARTITION_BYTES or sha(raw)!=report['capture_sha256']:
            raise ValueError('备份持久化复核失败')
        cfg=load(package/'config.json')
        value.update(backup_complete=True,backup_sha256=sha(raw),backup_file=str(raw),
            trust_state={SOURCE_SHA:'original',TARGET_SHA:'installed'}.get(sha(raw),'unsupported'),
            preload_name=next(name for name,text in cfg['preload_baselines'] if text==report['expected_preload_hex']))
    def observe():
        try:
            proof=host_module.observe(before,lambda label,timeout=5:host_module.snapshot(job,label,timeout,before['location_id']))
            save(job/'host-recovery.json',proof);value['USB_recovered']=proof['recovered']
        except Exception as e:value['recovery_error']=str(e)
    stalled=(operation_complete and report.get('service_stop_result')=='stalled'
        and report.get('service_stop_backend_error_code')==-9)
    if stalled:
        progress('机内核验完成；退出返回 STALL，仅观察同端口 MSC 恢复，不重发 STOP')
        observe()
        if value['USB_recovered']:
            complete=True;value.update(task_complete=True,can_replug=True,stop_confirmation='stable_msc_after_stall')
    if not complete:
        value['error']=report.get('failure') or report.get('service_stop_error') or '事务回执未完整通过；保留连接和日志，不自动重试'
        if pre_service_failure(value):value.update(recovery_kind='pre_service_failure',can_replug=True)
        return value
    if not stalled:
        progress('事务与退出请求已完成，正在观察普通 MSC 恢复')
        observe()
    return value
