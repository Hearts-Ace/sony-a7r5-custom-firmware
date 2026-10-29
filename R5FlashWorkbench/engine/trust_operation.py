# Adapted for R5FlashWorkbench, 2026-10-29. See THIRD_PARTY_NOTICES.md.
"""专用libJit事务；完整日志、对应格式的回读及重复终态通过才开放一次STOP。"""
import hashlib
import base64
import json
import os
from pathlib import Path
import re
import time
from libjit_operation import Operation as BaseOperation
from transport import Channel, FileResultError
from common import save,write_payload


def persist_readback_progress(output,checkpoint,chunk=None):
    if chunk is not None:
        fd=os.open(chunk,os.O_RDWR|os.O_NOFOLLOW)
        try:os.fchmod(fd,0o600);os.fsync(fd)
        finally:os.close(fd)
    pending=output/'.trust-readback-checkpoint.new'
    save(pending,checkpoint);os.replace(pending,output/'trust-readback-checkpoint.json')
    fd=os.open(output,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def validate_journal(raw,run,plan,*,force=False):
    if not raw.endswith(b'\n'):raise ValueError('日志尾部缺失')
    pattern=re.compile(r'A7R5_TRUST '+re.escape(run)+r' ([A-Z_]+) completed=(\d+) offset=(-?\d+) code=(-?\d+)')
    actual=[]
    for line in raw.decode('ascii').splitlines():
        match=pattern.fullmatch(line)
        if match is None:raise ValueError('日志格式或会话不符')
        actual.append((match[1],int(match[2]),int(match[3]),int(match[4])))
    expected=[('FORCE_PREIMAGE_CAPTURED' if force else 'PREIMAGE_VERIFIED',0,-1,0)]
    for index,row in enumerate(plan['rows']):
        expected += [('WRITE_BEGIN',index,row['offset'],0),('WRITE_RETURNED',index+1,row['offset'],0)]
        if index==len(plan['rows'])-1 or row['phase']!=plan['rows'][index+1]['phase']:
            expected.append(('PHASE_SYNC_RETURNED',index+1,row['offset'],0))
    expected += [('FULL_LOGICAL_READBACK_MATCH',26,-1,0),('REOPENED_FULL_CAPTURE_MATCH',26,-1,0),('COMPLETED',26,-1,0)]
    if actual!=expected:raise ValueError('日志阶段、计数、偏移或结果不符')
    return True


class Operation(BaseOperation):
    def __init__(self,bundle,channel_factory=Channel,clock=time.monotonic,sleep=time.sleep):
        super().__init__(bundle,channel_factory)
        if self.config.get('trust_control_layout')!='ram-v2':
            raise ValueError('信任更新模板不支持RAM控制文件，请重新构建客户端')
        self.force=self.config.get('force_install',False)
        if self.force:raise ValueError('Force install is not supported by this workbench')
        if type(self.force) is not bool:raise ValueError('强制模式标记无效')
        self.readback_format=self.config.get('trust_readback_format','full-16k-v1')
        if self.readback_format not in ('full-16k-v1','planned-sectors-v2') or not self.force and self.readback_format!='full-16k-v1':
            raise ValueError('信任回读格式不符')
        self.sector_readback=self.force and self.readback_format=='planned-sectors-v2'
        self.resource_policy=self.config.get('trust_resource_policy','legacy-64m-v1')
        if self.resource_policy not in ('legacy-64m-v1','planned-sectors-32m-v1') or (
                self.resource_policy=='planned-sectors-32m-v1' and not self.sector_readback):
            raise ValueError('信任资源预算与回读格式不符')
        self.memory_required_kib=32768 if self.resource_policy=='planned-sectors-32m-v1' else 65536
        force_marker=(b'A7R5_TRUST_FORCE_V3_RESOURCE_BUDGET' if self.memory_required_kib==32768 else
            b'A7R5_TRUST_FORCE_V2_SECTOR_READBACK' if self.sector_readback else b'A7R5_TRUST_FORCE_V1_RAM_16K')
        self.configure_ram_control('ram-v2',force_marker if self.force else b'A7R5_TRUST_PRODUCTION_V3_RAM_BOOTSTRAP')
        self.clock,self.sleep=clock,sleep
        self.reads['/tmp/jiritsu/libJit.so']=1048576
        self.reads[self.config['journal_path']]=131072
        self.readback_parts=[]
        if self.force:
            self.packet_limit=512 if self.sector_readback else 4096;self.usb_read_size=8192;self.strict_usb_reads=True
            self.readback_parts=([(self.config['readback_path']+'.sectors-'+str(i),min(16384,13312-i*16384)) for i in range(9)]
                if self.sector_readback else [(self.config['readback_path']+'.part-'+str(i),16384) for i in range(1532)])
            self.reads.update(self.readback_parts)
        else:self.reads[self.config['readback_path']]=25100288
        self.may_have_written=False
        self.plan=json.loads((self.bundle/'materials/write-plan.json').read_text())
        if self.force:
            self.patch=json.loads((self.bundle/'materials/trust-sectors.json').read_text())['rows']
            if len(self.patch)!=26 or [r['offset'] for r in self.patch]!=[r['offset'] for r in self.plan['rows']]:
                raise ValueError('强制模式写入范围不符')
            for row in self.patch:
                if (row['offset']%512 or not 0<=row['offset']<=25100288-512
                    or len(base64.b64decode(row['after'],validate=True))!=512):raise ValueError('强制模式扇区材料不符')
            self.expected_candidate=None
        else:self.expected_candidate=(self.bundle/'materials/candidate.logical.img').read_bytes()

    def __call__(self,driver,output,log,report):
        self.output=Path(output);channel=self.channel_factory(driver,self,log)
        report.update(trigger_attempts=0,fixed_writes_attempted=0,debug_commands_sent=False,
            preload_written=False,protocol_gate_passed=False,partition_write_may_have_started=False,
            complete_partition_readback_verified=False,worker_timeout_kill=False,
            trust_control_layout='ram-v2',native_write_complete=False,planned_sector_readback_verified=False)
        report['force_install']=self.force
        report['trust_resource_policy']=self.resource_policy
        def read(label,path):
            raw=channel.read(path,self.reads[path]);(self.output/(label+'.bin')).write_bytes(raw);return raw
        def candidate(label,path):
            try:read(label,path)
            except FileResultError as error:
                if error.result!=0x10000006:raise
                log('stat_failed_candidate',path=path,absence_proven=False);return
            raise ValueError('固定路径已有可读内容，不覆盖：'+path)
        def put(path,data):
            if path in self.written:raise PermissionError('禁止重复上传')
            self.written.add(path);report['fixed_writes_attempted']+=1
            if path=='/tmp/jiritsu/libJit.so':
                self.trigger_attempts+=1;self.may_have_written=True
                report.update(trigger_attempts=self.trigger_attempts,partition_write_may_have_started=True)
            stage='loader' if path=='/tmp/jiritsu/libJit.so' else 'ticket'
            report.update(upload_stage=stage,upload_path=path)
            try:channel.put(path,data)
            except FileResultError as error:
                report['upload_failure']=dict(stage=stage,path=path,action=error.action,
                    result=f'0x{error.result:08x}',system_errno=None)
                raise
        if hashlib.sha256(read('version','/version.txt')).hexdigest()!=self.config['version_sha256']:raise ValueError('版本不符')
        if hashlib.sha256(read('loader','/usr/lib/libJiritsu.so')).hexdigest()!=self.config['loader_sha256']:raise ValueError('加载库不符')
        baseline=read('preload-before','/etc/ld.so.preload')
        if self.force:
            if baseline not in [bytes.fromhex(row[1]) for row in self.config['preload_baselines']]:raise ValueError('预加载类型未适配')
        elif baseline!=bytes.fromhex(self.config['expected_preload_hex']):raise ValueError('精确预加载基线不符')
        for index,path in enumerate(['/tmp/jiritsu/libJit.so','/tmp/jbusy',self.ticket_path,*[self.prefix+s for s in ('.claim','.state','.state.new','.output')]]):
            candidate(f'candidate-{index}',path)
        if read('preload-before-upload','/etc/ld.so.preload')!=baseline:raise ValueError('上传前预加载变化')
        put(self.ticket_path,self.ticket)
        if read('ticket-readback',self.ticket_path)!=self.ticket:raise ValueError('票据不符')
        put('/tmp/jiritsu/libJit.so',self.payload)
        deadline=self.clock()+self.config['observe_seconds'];terminal=None
        for index in range(100):
            if self.clock()>=deadline:break
            try:raw=read(f'state-{index:03}',self.prefix+'.state')
            except FileResultError as error:
                if error.result!=0x10000006:raise
                self.sleep(.6);continue
            match=re.fullmatch(rb'A7R5-JIT-1 '+self.run.encode()+rb' (RUNNING|DONE|FAILED|TIMEOUT) (\d+) uid=(\d+) euid=(\d+) bytes=(-?\d+) disarmed=(\d+) children=(-?\d+)'
                rb'(?: precheck_reason=(\d+) precheck_pid=(-?\d+) precheck_fd=(-?\d+) precheck_error=(-?\d+) precheck_device=(\d+) partition_writes=(0)'
                rb'| resource_reason=(\d+) resource_error=(-?\d+) memory_available_kib=(-?\d+) memory_required_kib=(\d+) ram_available_bytes=(-?\d+) partition_writes=(0))?\n',raw)
            if not match or match.group(3,4)!=(b'0',b'0'):raise ValueError('状态会话或root身份不符')
            if match[8] is not None and not (match[1]==b'FAILED' and match[2]==b'47' and match.group(6,7)==(b'1',b'0')):
                raise ValueError('写前诊断与任务终态不符')
            if match[14] is not None and not (match[1]==b'FAILED' and match[2] in (b'43',b'44')
                    and match.group(5,6,7)==(b'0',b'1',b'0')):
                raise ValueError('资源诊断与任务终态不符')
            if match[1]==b'FAILED':
                report['trust_native_exit_code']=int(match[2])
                if match[2] in (b'43',b'44') and match.group(5,6,7)==(b'0',b'1',b'0'):
                    # 固定模板的43/44只出现在打开目标分区之前；不把它当成未知写入失败。
                    detail='写前内存或RAM工作目录检查未通过，旧载荷未记录具体原因'
                    if match[14] is not None:
                        diagnostic=dict(zip(('reason','error','memory_available_kib','memory_required_kib','ram_available_bytes'),
                            (int(match[i]) for i in range(14,19))))
                        reasons={1:'无法读取内存信息',2:'可用内存不足或内存信息缺失',3:'无法打开RAM工作目录',
                            4:'RAM文件系统或可用容量检查未通过',5:'进程文件大小限制检查未通过',6:'关闭RAM目录句柄失败'}
                        allowed=(1,2,3) if match[2]==b'43' else (4,5,6)
                        if diagnostic['reason'] not in allowed or diagnostic['memory_required_kib']!=self.memory_required_kib:
                            raise ValueError('资源诊断字段与固定门槛不符')
                        report['trust_resources']=diagnostic
                        detail=(reasons[diagnostic['reason']]+f'；可用内存={diagnostic["memory_available_kib"]} KiB，'
                            f'要求={diagnostic["memory_required_kib"]} KiB，系统返回={diagnostic["error"]}')
                    report.update(trust_resource_check_failed=True,partition_write_may_have_started=False,partition_writes=0)
                    raise RuntimeError('写入前资源检查失败：'+detail+'；本次未写更新器分区，保留现场，不STOP、不重试')
                if match[2]==b'47' and match.group(6,7)==(b'1',b'0'):
                    report.update(trust_precheck_failed=True,partition_write_may_have_started=False,partition_writes=0)
                    detail='进程或挂载占用检查未通过，旧载荷没有记录具体阻塞原因'
                    if match[8] is not None:
                        diagnostic=dict(zip(('reason','pid','fd','error','device'),(int(match[i]) for i in range(8,13))))
                        reasons={1:'无法打开进程目录',2:'无法枚举进程',3:'进程目录项格式异常',
                            4:'无法读取进程挂载信息',5:'目标分区或父设备已挂载',6:'无法打开进程文件描述符目录',
                            7:'无法枚举进程文件描述符',8:'文件描述符目录项格式异常',9:'无法读取文件描述符身份',
                            10:'其他进程持有目标分区或父设备',11:'关闭进程检查句柄失败',12:'挂载信息格式不完整',13:'无法取得本进程身份',
                            14:'无法打开进程元数据目录'}
                        if diagnostic['reason'] not in reasons:raise ValueError('未知写前诊断原因')
                        report['trust_precheck']=diagnostic
                        detail=(reasons[diagnostic['reason']]+f'；PID={diagnostic["pid"]}，FD={diagnostic["fd"]}，系统返回={diagnostic["error"]}')
                    # 诊断随同一份终态取得；失败后不追加文件读取或恢复请求。
                    raise RuntimeError('写入前检查失败：'+detail+'；本次未写更新器分区，保留现场，不STOP、不重试')
            if match[1] in (b'FAILED',b'TIMEOUT'):raise RuntimeError('原生任务失败，不STOP、不重试：'+raw.decode().strip())
            if match[1]==b'DONE':
                if match[2]!=b'0' or match.group(6,7)!=(b'1',b'0'):raise ValueError('成功终态门槛不符')
                size=int(match[5])
                if not 0<size<32768:raise ValueError('输出长度无效')
                terminal=raw;break
            self.sleep(.6)
        if terminal is None:raise TimeoutError('只停止主机观察，不终止写入进程，不STOP或重试')
        data=read('native-output',self.prefix+'.output')
        if self.force:
            layout=(b'chunks=9 chunk_bytes=16384 readback=planned-sectors-v2\n' if self.sector_readback
                else b'chunks=1532 chunk_bytes=16384\n')
            pattern=(re.escape(self.config['expected_output_begin'].encode())+
                rb'A7R5_TRUST_FORCE_COMPLETE ([0-9a-f]{64}) source_sha256=([0-9a-f]{64}) sectors=26 bytes=13312 reopened=1 '+re.escape(layout)+
                re.escape(self.config['expected_output_end'].encode()))
            match=re.fullmatch(pattern,data)
            if not match or len(data)!=size:raise ValueError('强制安装原生输出不符')
            candidate_sha=match[1].decode();report['actual_source_sha256']=match[2].decode()
        else:
            candidate_sha=self.config['candidate_sha256']
            expected=(self.config['expected_output_begin']+'A7R5_TRUST_COMPLETE '+candidate_sha+
                ' sectors=26 bytes=13312 reopened=1\n'+self.config['expected_output_end']).encode()
            if data!=expected or len(data)!=size:raise ValueError('固定原生输出不符')
        journal=read('native-journal',self.config['journal_path']);validate_journal(journal,self.run,self.plan,force=self.force)
        report.update(native_write_complete=True,native_full_readback_verified=True,
            native_reopened_readback_verified=True,native_logical_partition_sha256=candidate_sha,
            trust_readback_format=self.readback_format,trust_readback_scope='planned-sectors' if self.sector_readback else 'full-partition')
        receipt=dict(run_id=self.run,native_logical_sha256=candidate_sha,sectors=26,write_bytes=13312,
            terminal_sha256=hashlib.sha256(terminal).hexdigest(),output_sha256=hashlib.sha256(data).hexdigest(),
            journal_sha256=hashlib.sha256(journal).hexdigest())
        save(self.output/'trust-native-verified.json',receipt)
        if self.force:
            raw=bytearray();download_hash=hashlib.sha256()
            expected_sectors=b''.join(base64.b64decode(row['after'],validate=True) for row in self.patch)
            report.update(trust_readback_completed_chunks=0,trust_readback_total_chunks=len(self.readback_parts),trust_readback_state='downloading')
            checkpoint=dict(receipt,format=self.readback_format,total_chunks=len(self.readback_parts),
                completed_chunks=0,completed_bytes=0,completed_sha256=download_hash.hexdigest(),host_verified=False)
            persist_readback_progress(self.output,checkpoint)
            try:
                for index,(path,expected) in enumerate(self.readback_parts):
                    label=f'trust-readback-{index:04}'
                    part=read(label,path)
                    if len(part)!=expected:raise ValueError('信任回读分块长度不符')
                    if self.sector_readback and part!=expected_sectors[index*16384:index*16384+expected]:
                        raise ValueError('强制安装计划扇区回读不符')
                    raw.extend(part);download_hash.update(part)
                    checkpoint.update(completed_chunks=index+1,completed_bytes=len(raw),completed_sha256=download_hash.hexdigest())
                    persist_readback_progress(self.output,checkpoint,self.output/(label+'.bin'))
                    report['trust_readback_completed_chunks']=index+1
                if self.sector_readback:
                    if len(raw)!=13312 or raw!=expected_sectors:raise ValueError('计划扇区完整回读不符')
                    write_payload(self.output/'planned-sector-readback.bin',raw)
                else:
                    for row in self.patch:
                        if raw[row['offset']:row['offset']+512]!=base64.b64decode(row['after'],validate=True):
                            raise ValueError('强制安装扇区回读不符')
            except BaseException:
                report['trust_readback_state']='failed';raise
        else:raw=read('partition1.logical',self.config['readback_path'])
        if not self.sector_readback and (len(raw)!=25100288 or hashlib.sha256(raw).hexdigest()!=candidate_sha or not self.force and raw!=self.expected_candidate):
            raise ValueError('完整分区回读与候选不符，禁止STOP')
        if self.force and not self.sector_readback:(self.output/'partition1.logical.bin').write_bytes(raw)
        if read('preload-after','/etc/ld.so.preload')!=baseline:raise ValueError('预加载变化')
        if read('state-repeat',self.prefix+'.state')!=terminal:raise ValueError('重复终态变化')
        report.update(protocol_gate_passed=True,root_task_done=True,root_uid=0,root_euid=0,
            preload_unchanged=True,self_unlink_receipt=True,complete_partition_readback_verified=not self.sector_readback,
            planned_sector_readback_verified=self.sector_readback,patch_sectors=26,logical_write_bytes=13312,
            shell_output_bytes=len(data),shell_output_sha256=hashlib.sha256(data).hexdigest())
        if self.sector_readback:
            report.update(planned_sector_readback_sha256=hashlib.sha256(raw).hexdigest(),trust_readback_bytes=len(raw))
        else:report['logical_partition_sha256']=hashlib.sha256(raw).hexdigest()
        if self.force:
            checkpoint['host_verified']=True;persist_readback_progress(self.output,checkpoint)
            report['trust_readback_state']='verified'
        self.safe_to_stop=True
