# Adapted for R5FlashWorkbench, 2026-10-29. See THIRD_PARTY_NOTICES.md.
"""固定分区只读捕获与本次RAM副本清理；导入时不初始化USB后端。"""
import hashlib
import fcntl
import os
from pathlib import Path
import re
import time

from libjit_operation import Operation as BaseOperation
from transport import Channel,FileResultError
from common import PARTITION_BYTES, load, save, sha, progress


def persist_backup(output, raw, run, digest, *, chunks):
    """删除准入依据必须是持久化并重新读取的完整本机文件。"""
    path=output/'partition1.logical.bin'
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
        if hasattr(fcntl,'F_FULLFSYNC'):fcntl.fcntl(stream.fileno(),fcntl.F_FULLFSYNC)
    if path.stat().st_size!=PARTITION_BYTES or sha(path)!=digest:raise ValueError('本机备份持久化后读回不符，不清理RAM副本')
    receipt=output/'backup-verified.json'
    save(receipt,dict(run_id=run,bytes=PARTITION_BYTES,sha256=digest,chunks=chunks,file=path.name))
    fd=os.open(receipt,os.O_RDWR|os.O_NOFOLLOW)
    try:
        if hasattr(fcntl,'F_FULLFSYNC'):fcntl.fcntl(fd,fcntl.F_FULLFSYNC)
    finally:os.close(fd)
    fd=os.open(output,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


class Operation(BaseOperation):
    payload_marker=b'A7R5_CAPTURE_READONLY_V5_RAM_16K'
    usb_read_size=8192
    strict_usb_reads=True
    cleanup_after_capture=True
    def __init__(self,bundle,channel_factory=Channel,clock=time.monotonic,sleep=time.sleep):
        super().__init__(bundle,channel_factory)
        self.clock,self.sleep=clock,sleep
        format=self.config.get('capture_format')
        if format not in (None,'ram-16k-v1'):raise ValueError('未知捕获分块布局')
        self.chunk_bytes=16384 if format=='ram-16k-v1' else 262144
        self.chunk_count=(PARTITION_BYTES+self.chunk_bytes-1)//self.chunk_bytes
        layout=self.config.get('capture_control_layout')
        self.ticket_path=self.prefix+'.ticket'
        if layout not in (None,'ram-v1','ram-v2'):raise ValueError('未知捕获控制文件布局')
        if layout in ('ram-v1','ram-v2'):
            marker=(b'A7R5_CAPTURE_READONLY_V3_RAM_CONTROL' if layout=='ram-v1' else
                b'A7R5_CAPTURE_READONLY_V4_RAM_BOOTSTRAP' if format is None and self.payload_marker==Operation.payload_marker
                else self.payload_marker)
            self.configure_ram_control(layout,marker)
        if format=='ram-16k-v1':
            if layout!='ram-v2' or Operation.payload_marker not in self.payload:
                raise ValueError('16KiB分块与执行模板不匹配')
            self.packet_limit=4096
        self.reads['/tmp/jiritsu/libJit.so']=1048576
        self.parts=[(self.config['capture_path']+'.part-'+str(i),min(self.chunk_bytes,PARTITION_BYTES-i*self.chunk_bytes))
                    for i in range(self.chunk_count)]
        self.reads.update(self.parts)
        self.may_have_written=False
        self.cleanup_required=self.cleanup_after_capture
        if self.cleanup_required:
            if format!='ram-16k-v1' or self.config.get('capture_cleanup_policy')!='verified-current-ram-v2':
                raise ValueError('捕获缺少本次RAM副本清理模板，请重新构建客户端')
            self.cleanup_prefix='/tmp_wbshd/a7r5-cleanup-'+self.run+'/task'
            self.cleanup_ticket='/tmp_wbshd/a7r5-cleanup-'+self.run+'.ticket'
            self.cleanup_payload=(self.bundle/'materials/capture-cleanup.so').read_bytes()
            if b'A7R5_CAPTURE_CLEANUP_V2_RAM_16K' not in self.cleanup_payload:
                raise ValueError('RAM清理模板不符')
            self.reads.update({self.cleanup_ticket:128,self.cleanup_prefix+'.state':512,
                              self.cleanup_prefix+'.output':32768})

    def __call__(self,driver,output,log,report):
        if self.config.get('capture_control_layout')!='ram-v2':
            raise PermissionError('旧捕获布局仅允许接续读取，禁止重新上传；请重新构建客户端')
        self.output=Path(output);channel=self.channel_factory(driver,self,log)
        report.update(fixed_writes_attempted=0,trigger_attempts=0,partition_writes=0,
            preload_written=False,debug_commands_sent=False,protocol_gate_passed=False,
            upload_stage='not_started',upload_complete=False,loader_upload_attempted=False,
            loader_execution_observed=False)
        report['capture_control_layout']=self.config.get('capture_control_layout','legacy-work')
        report.update(capture_cleanup_required=self.cleanup_required,capture_cleanup_state='not_started')
        def read(label,path):
            raw=channel.read(path,self.reads[path]);(self.output/(label+'.bin')).write_bytes(raw);return raw
        def candidate(label,path):
            try:read(label,path)
            except FileResultError as error:
                if error.result!=0x10000006:raise
                log('stat_failed_candidate',path=path,absence_proven=False);return
            raise ValueError('固定路径已有可读内容，停止')
        if hashlib.sha256(read('version','/version.txt')).hexdigest()!=self.config['version_sha256']:raise ValueError('固件版本未知，不触发捕获')
        if hashlib.sha256(read('loader','/usr/lib/libJiritsu.so')).hexdigest()!=self.config['loader_sha256']:raise ValueError('加载库不符')
        baseline=read('preload-before','/etc/ld.so.preload')
        if baseline not in [bytes.fromhex(r[1])for r in self.config['preload_baselines']]:raise ValueError('预加载未知')
        for i,path in enumerate(['/tmp/jiritsu/libJit.so','/tmp/jbusy',self.ticket_path,*[self.prefix+s for s in ('.claim','.state','.state.new','.output')]]):candidate(f'candidate-{i}',path)
        if read('preload-repeat','/etc/ld.so.preload')!=baseline:raise ValueError('捕获前基线变化')
        for path,data in ((self.ticket_path,self.ticket),('/tmp/jiritsu/libJit.so',self.payload)):
            stage='loader' if path=='/tmp/jiritsu/libJit.so' else 'ticket'
            report.update(upload_stage=stage,upload_path=path)
            log('capture_upload_started',stage=stage,path=path,bytes=len(data))
            self.written.add(path);report['fixed_writes_attempted']+=1
            if path.endswith('/libJit.so'):
                self.may_have_written=True;report.update(trigger_attempts=1,loader_upload_attempted=True)
            try:channel.put(path,data)
            except FileResultError as error:
                report['upload_failure']=dict(stage=stage,path=path,action=error.action,
                    result=f'0x{error.result:08x}',system_errno=None)
                log('capture_upload_failed',**report['upload_failure'])
                raise
            log('capture_upload_returned',stage=stage,path=path)
            if path.endswith('.ticket') and read('ticket-readback',path)!=data:raise ValueError('票据读回不符')
        report.update(upload_stage='complete',upload_complete=True)
        self.collect(read,report,baseline)
        if self.cleanup_required:
            self.cleanup(channel,read,report,baseline)

    def collect(self,read,report,baseline):
        # 新捕获和旧捕获接续使用同一套终态、分块摘要与退出门槛。
        terminal,size=self.wait_terminal(read,report)
        data=read('native-output',self.prefix+'.output')
        pattern=(re.escape(self.config['expected_output_begin'].encode())+rb'A7R5_CAPTURE_COMPLETE ([0-9a-f]{64})'+re.escape(f' bytes=25100288 twice=1 chunks={self.chunk_count} chunk_bytes={self.chunk_bytes}\n'.encode())+re.escape(self.config['expected_output_end'].encode()))
        match=re.fullmatch(pattern,data)
        if not match or len(data)!=size:raise ValueError('捕获输出不完整')
        # 机内生成与本机完整下载分别记录，下载失败时不丢失已取得的终态证据。
        report.update(native_capture_complete=True,native_capture_sha256=match[1].decode(),
            native_capture_bytes=25100288,native_capture_chunks=self.chunk_count,
            capture_chunk_bytes=self.chunk_bytes,capture_expected_chunks=self.chunk_count)
        raw=bytearray();download_hash=hashlib.sha256()
        report['capture_download_chunks']=0
        for index,(path,expected) in enumerate(self.parts):
            part=read(f'partition-chunk-{index:03}',path)
            if len(part)!=expected:raise ValueError('备份分块长度不符')
            # 只将完整分块计入持久进度；超时残片保留为独立证据。
            chunk_file=self.output/f'partition-chunk-{index:03}.bin'
            fd=os.open(chunk_file,os.O_RDWR|os.O_NOFOLLOW)
            try:os.fchmod(fd,0o600);os.fsync(fd)
            finally:os.close(fd)
            raw.extend(part);download_hash.update(part)
            checkpoint=dict(run_id=self.run,native_sha256=match[1].decode(),
                native_terminal_sha256=hashlib.sha256(terminal).hexdigest(),
                chunk_bytes=self.chunk_bytes,total_chunks=self.chunk_count,
                completed_chunks=index+1,completed_bytes=len(raw),
                completed_sha256=download_hash.hexdigest())
            pending=self.output/'.download-checkpoint.new'
            save(pending,checkpoint)
            os.replace(pending,self.output/'download-checkpoint.json')
            fd=os.open(self.output,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try:os.fsync(fd)
            finally:os.close(fd)
            report['capture_download_chunks']=index+1
        if len(raw)!=25100288 or hashlib.sha256(raw).hexdigest()!=match[1].decode():raise ValueError('备份长度或摘要不符')
        if read('preload-after','/etc/ld.so.preload')!=baseline or read('state-repeat',self.prefix+'.state')!=terminal:raise ValueError('捕获后状态或预加载变化')
        persist_backup(self.output,raw,self.run,match[1].decode(),chunks=self.chunk_count)
        self.safe_to_stop=not self.cleanup_required
        report.update(protocol_gate_passed=True,root_task_done=True,preload_unchanged=True,
            capture_verified=True,capture_sha256=match[1].decode(),capture_bytes=len(raw),partition_writes=0,
            expected_preload_hex=baseline.hex(),self_unlink_receipt=True,backup_persisted=True)

    def cleanup(self,channel,read,report,baseline):
        self.safe_to_stop=False
        report.update(capture_cleanup_state='checking',capture_cleanup_verified=False)
        try:
            receipt=load(self.output/'backup-verified.json')
            expected=dict(run_id=self.run,bytes=PARTITION_BYTES,sha256=report['capture_sha256'],chunks=self.chunk_count,file='partition1.logical.bin')
            image=self.output/'partition1.logical.bin'
            if (not report.get('capture_verified') or not report.get('backup_persisted') or receipt!=expected
                or image.stat().st_size!=PARTITION_BYTES or sha(image)!=receipt['sha256']):
                raise ValueError('完整本机副本或持久化回执变化，禁止清理')
            if read('preload-before-cleanup','/etc/ld.so.preload')!=baseline:
                raise ValueError('清理前预加载变化')
            progress('本机完整备份已落盘并复核，正在清理本次机内临时副本')
            # 清理载荷仅有固定本次路径；不能借此上传任意文件或清理其他任务。
            self.writes={self.cleanup_ticket:self.ticket,'/tmp/jiritsu/libJit.so':self.cleanup_payload}
            report['capture_cleanup_state']='uploading'
            for path,data in ((self.cleanup_ticket,self.ticket),('/tmp/jiritsu/libJit.so',self.cleanup_payload)):
                report['fixed_writes_attempted']+=1
                if path=='/tmp/jiritsu/libJit.so':report['trigger_attempts']+=1
                channel.put(path,data)
                if path==self.cleanup_ticket and read('cleanup-ticket-readback',path)!=data:
                    raise ValueError('清理票据读回不符')
            report['capture_cleanup_state']='waiting'
            terminal,size=self.wait_terminal(read,report,prefix=self.cleanup_prefix,label='cleanup-state')
            data=read('cleanup-output',self.cleanup_prefix+'.output')
            expected=(f'A7R5_CAPTURE_CLEANUP {self.run} sha256={receipt["sha256"]} '
                      f'deleted={self.chunk_count} bytes=25100288 directory_removed=1\n').encode()
            if data!=expected or len(data)!=size:raise ValueError('机内副本清理回执不符')
            if (read('preload-after-cleanup','/etc/ld.so.preload')!=baseline or
                read('cleanup-state-repeat',self.cleanup_prefix+'.state')!=terminal):
                raise ValueError('清理后状态或预加载变化')
            report.update(capture_cleanup_state='complete',capture_cleanup_verified=True,
                          capture_cleanup_deleted_chunks=self.chunk_count,capture_cleanup_directory_removed=True)
            self.safe_to_stop=True
        except BaseException as error:
            report.update(capture_cleanup_state='failed',capture_cleanup_error=type(error).__name__+': '+str(error))
            raise

    def wait_terminal(self,read,report,*,prefix=None,label='state'):
        prefix=self.prefix if prefix is None else prefix
        terminal=None;deadline=self.clock()+60
        for index in range(100):
            if self.clock()>=deadline:break
            try:raw=read(f'{label}-{index}',prefix+'.state')
            except FileResultError as error:
                if error.result!=0x10000006:raise
                self.sleep(.5);continue
            m=re.fullmatch(rb'A7R5-JIT-1 '+self.run.encode()+rb' (RUNNING|DONE|FAILED|TIMEOUT) (\d+) uid=(\d+) euid=(\d+) bytes=(-?\d+) disarmed=(\d+) children=(-?\d+)\n',raw)
            if not m or m.group(3,4)!=(b'0',b'0'):raise ValueError('捕获状态身份不符')
            report['loader_execution_observed']=True
            if m[1] in (b'FAILED',b'TIMEOUT'):
                report['capture_cleanup_native_exit_code' if prefix!=self.prefix else 'capture_native_exit_code']=int(m[2])
                reason=(f'清理失败，机内退出码{int(m[2])}' if prefix!=self.prefix else
                    '机内可用内存低于64MiB或无法确认，未开始备份分区读取' if m[2]==b'46' else f'捕获失败，机内退出码{int(m[2])}')
                raise RuntimeError(reason+'；保留现场，不重试')
            if m[1]==b'DONE':
                if m[2]!=b'0' or m.group(6,7)!=(b'1',b'0') or not 0<int(m[5])<32768:raise ValueError('捕获终态不符')
                terminal=raw;size=int(m[5]);break
            self.sleep(.5)
        if terminal is None:raise TimeoutError('捕获观察超时，不杀工作进程、不STOP')
        return terminal,size


class ExistingCaptureOperation(Operation):
    """仅读取指定旧捕获；没有票据、载荷上传或其他文件写入权限。"""
    cleanup_after_capture=False
    def __init__(self,bundle,**kwargs):
        super().__init__(bundle,**kwargs)
        self.writes={}
        self.reads={path:self.reads[path] for path in (
            '/version.txt','/usr/lib/libJiritsu.so','/etc/ld.so.preload',
            self.prefix+'.state',self.prefix+'.output',*(path for path,_ in self.parts))}

    def __call__(self,driver,output,log,report):
        self.output=Path(output);channel=self.channel_factory(driver,self,log)
        report.update(fixed_writes_attempted=0,trigger_attempts=0,partition_writes=0,
            preload_written=False,debug_commands_sent=False,protocol_gate_passed=False,
            existing_capture_read_only=True,existing_capture_run_id=self.run,
            upload_stage='disabled',upload_complete=False,loader_upload_attempted=False,
            loader_execution_observed=False)
        def read(label,path):
            raw=channel.read(path,self.reads[path]);(self.output/(label+'.bin')).write_bytes(raw);return raw
        if hashlib.sha256(read('version','/version.txt')).hexdigest()!=self.config['version_sha256']:
            raise ValueError('固件版本未知，不接续旧捕获')
        if hashlib.sha256(read('loader','/usr/lib/libJiritsu.so')).hexdigest()!=self.config['loader_sha256']:
            raise ValueError('加载库不符，不接续旧捕获')
        baseline=read('preload-before','/etc/ld.so.preload')
        if baseline not in [bytes.fromhex(row[1]) for row in self.config['preload_baselines']]:
            raise ValueError('预加载未知，不接续旧捕获')
        self.collect(read,report,baseline)
