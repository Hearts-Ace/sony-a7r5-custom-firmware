# Adapted for R5FlashWorkbench, 2026-10-29. See THIRD_PARTY_NOTICES.md.
"""libJit 一次触发；完整终态、固定输出与预加载未变才开放一次 STOP。"""
from pathlib import Path
import hashlib
import json
import re
import struct
import time
from transport import Channel,FileResultError,HEADER,READ,wire

class Operation:
    packet_limit=512
    def __init__(self,bundle,channel_factory=Channel):
        self.bundle=Path(bundle);self.config=json.loads((self.bundle/'config.json').read_text())
        self.run=self.config['run_id'];self.prefix='/tmp/jiritsu/a7r5-jit-'+self.run
        self.payload=(self.bundle/'materials/libJit.so').read_bytes()
        self.ticket=(self.bundle/'materials/ticket.bin').read_bytes()
        self.output=None;self.interfaces_seen=0;self.permitted_packet=None;self.safe_to_stop=False
        self.channel_factory=channel_factory
        self.reads={'/version.txt':4096,'/usr/lib/libJiritsu.so':self.config['loader_bytes'],
                    '/etc/ld.so.preload':4096,'/tmp/jiritsu/libJit.so':65536,'/tmp/jbusy':64,
                    self.prefix+'.ticket':128,self.prefix+'.claim':128,self.prefix+'.state':512,
                    self.prefix+'.state.new':512,self.prefix+'.output':32768}
        self.writes={self.prefix+'.ticket':self.ticket,'/tmp/jiritsu/libJit.so':self.payload}
        self.trigger_attempts=0;self.written=set()

    def configure_ram_control(self,layout,marker):
        if layout not in ('ram-v1','ram-v2') or marker not in self.payload:
            raise ValueError('RAM控制文件与执行模板不匹配')
        previous=self.prefix
        self.prefix='/tmp_wbshd/a7r5-control-'+self.run+'/task'
        self.reads={self.prefix+path[len(previous):] if path.startswith(previous+'.') else path:limit
                    for path,limit in self.reads.items()}
        self.ticket_path=self.prefix+'.ticket' if layout=='ram-v1' else '/tmp_wbshd/a7r5-control-'+self.run+'.ticket'
        self.reads.pop(self.prefix+'.ticket',None);self.reads[self.ticket_path]=128
        self.writes={self.ticket_path:self.ticket,'/tmp/jiritsu/libJit.so':self.payload}

    def interface_checked(self,device,interface):
        raw=dict(pid=int(device.idProduct),bus=device.bus,ports=list(device.port_numbers or ()),
                 number=int(interface.bInterfaceNumber),alternate=int(interface.bAlternateSetting),
                 interface_class=int(interface.bInterfaceClass),subclass=int(interface.bInterfaceSubClass),
                 protocol=int(interface.bInterfaceProtocol),endpoints=[dict(address=int(e.bEndpointAddress),attributes=int(e.bmAttributes),max_packet=int(e.wMaxPacketSize),interval=int(e.bInterval)) for e in interface])
        self.interfaces_seen+=1
        if self.output is None:raise ValueError('缺少输出目录')
        (self.output/f'interface-{self.interfaces_seen}.json').write_text(json.dumps(raw,indent=2))
        if raw!=self.config['interfaces'].get(f'interface-{self.interfaces_seen}.json'):raise ValueError('接口指纹不符，不换端点')
        (self.output/f'endpoints-{self.interfaces_seen}.json').write_text(json.dumps(dict(incoming=129,outgoing=2,rule='fixed_first_bulk_no_fallback')))
    def guard_packet(self,packet):
        if packet!=self.permitted_packet or len(packet)<HEADER.size+7:raise PermissionError('未经精确授权')
        size,function,sequence,*meta=HEADER.unpack_from(packet);body=packet[HEADER.size:]
        if size!=len(body) or function!=0x40 or not 1<=sequence<=self.packet_limit or any(meta):raise PermissionError('非法报文')
        selects={struct.pack('<HH',0x1001,15)+b'\0'+wire(p)+b'\0' for p in self.reads}
        puts={struct.pack('<HH',0x1001,16)+b'\0\xff\0'+d for d in self.writes.values()}
        if body not in selects|puts|{READ}:raise PermissionError('禁止 DEBUG、START 命令或额外文件操作')
    def __call__(self,driver,output,log,report):
        self.output=Path(output);channel=self.channel_factory(driver,self,log)
        report.update(trigger_attempts=0,fixed_writes_attempted=0,debug_commands_sent=False,preload_written=False,protocol_gate_passed=False)
        def read(label,path):
            raw=channel.read(path,self.reads[path]);(self.output/(label+'.bin')).write_bytes(raw);return raw
        def candidate(label,path):
            try:read(label,path)
            except FileResultError as exc:
                if exc.result!=0x10000006:raise
                log('stat_failed_candidate',path=path,absence_proven=False);return
            raise ValueError('固定路径已有可读内容，停止：'+path)
        def put(path,data):
            if path in self.written:raise PermissionError('固定文件不允许重写')
            self.written.add(path);report['fixed_writes_attempted']+=1
            if path=='/tmp/jiritsu/libJit.so':
                self.trigger_attempts+=1;report['trigger_attempts']=self.trigger_attempts
            channel.put(path,data)
        if hashlib.sha256(read('version','/version.txt')).hexdigest()!=self.config['version_sha256']:raise ValueError('版本不符')
        if hashlib.sha256(read('loader','/usr/lib/libJiritsu.so')).hexdigest()!=self.config['loader_sha256']:raise ValueError('机内加载库与静态证据不符')
        baseline=read('preload-before','/etc/ld.so.preload')
        if baseline not in [bytes.fromhex(row[1]) for row in self.config['preload_baselines']]:raise ValueError('预加载基线未经审查，不触发')
        for i,path in enumerate(['/tmp/jiritsu/libJit.so','/tmp/jbusy',*[self.prefix+s for s in ('.ticket','.claim','.state','.state.new','.output')]]):
            candidate(f'candidate-{i}',path)
        if read('preload-before-upload','/etc/ld.so.preload')!=baseline:raise ValueError('基线变化')
        put(self.prefix+'.ticket',self.ticket)
        if read('ticket-readback',self.prefix+'.ticket')!=self.ticket:raise ValueError('票据读回不符')
        # 写入精确文件名本身即触发，不能先写这个文件再做读回。
        put('/tmp/jiritsu/libJit.so',self.payload)
        terminal=None;deadline=time.monotonic()+self.config['task_seconds']+10
        for i in range(100):
            if time.monotonic()>=deadline:break
            try:raw=read(f'state-{i:03}',self.prefix+'.state')
            except FileResultError as exc:
                if exc.result!=0x10000006:raise
                time.sleep(.25);continue
            pattern=rb'A7R5-JIT-1 '+self.run.encode()+rb' (RUNNING|DONE|FAILED|TIMEOUT) (\d+) uid=(\d+) euid=(\d+) bytes=(-?\d+) disarmed=(\d+) children=(-?\d+)\n'
            match=re.fullmatch(pattern,raw)
            if not match or match.group(3,4)!=(b'0',b'0'):raise ValueError('旧会话或非法身份状态')
            if match[1] in (b'FAILED',b'TIMEOUT'):raise RuntimeError('机内失败，不自动 STOP：'+raw.decode().strip())
            if match[1]==b'DONE':
                if match[2]!=b'0' or match.group(6,7)!=(b'1',b'0'):raise ValueError('退出码、解除加载或后代门槛不符')
                size=int(match[5])
                if not 0<size<32768:raise ValueError('输出长度无效')
                terminal=raw;break
            time.sleep(.25)
        if terminal is None:raise TimeoutError('机内未返回完整终态，不重试、不自动 STOP')
        data=read('shell-output',self.prefix+'.output')
        if len(data)!=size or not data.startswith(self.config['expected_output_begin'].encode()) or not data.endswith(self.config['expected_output_end'].encode()):raise ValueError('固定输出或长度不符')
        if read('preload-after','/etc/ld.so.preload')!=baseline:raise ValueError('预加载发生变化')
        if read('state-repeat',self.prefix+'.state')!=terminal:raise ValueError('终态变化')
        self.safe_to_stop=True
        report.update(protocol_gate_passed=True,root_task_done=True,root_uid=0,root_euid=0,
                      preload_unchanged=True,self_unlink_receipt=True,shell_output_bytes=len(data),
                      shell_output_sha256=hashlib.sha256(data).hexdigest(),camera_execution_verified=True)
