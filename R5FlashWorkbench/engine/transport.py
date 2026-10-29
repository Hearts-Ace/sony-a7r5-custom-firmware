# Adapted for R5FlashWorkbench, 2026-10-29. See THIRD_PARTY_NOTICES.md.
"""固定文件通道；有完整响应才恢复同步标志，异常不重传。"""
import struct
import hashlib
HEADER=struct.Struct('<IHHBBBB')
READ=struct.pack('<HH',0x1001,17)+b'\0\xff\0'

class FileResultError(ValueError):
    def __init__(self,result,*,action=None,path=None):
        self.result,self.action,self.path=result,action,path
        meanings={
            ('read',0x10000006):'元数据查询失败，不能据此判断文件不存在',
            ('read',0x10000008):'读取请求被拒绝，相机未返回具体系统原因',
            ('read',0x1000000a):'读取长度不符',
            ('write',0x10000008):'打开目标文件失败，相机未返回具体系统原因',
            ('write',0x10000009):'写入长度不符',
            ('write',0x1000000f):'工作区容量检查未通过',
        }
        label={'select':'选择文件','read':'读取文件','write':'上传文件'}.get(action,'文件请求')
        detail=meanings.get((action,result),'未知文件错误')
        if action=='write' and result==0x10000008 and path and path.startswith('/tmp/jiritsu/'):
            # 目录槽位与数据容量独立；该回执不携带errno，不能直接断言空间已满。
            detail+='；请检查机内工作区目录项及挂载状态，保留现场，勿连续重试'
        super().__init__(f'{label}失败：{detail}（0x{result:08x}）'+(f'；路径：{path}' if path else ''))

def wire(path):
    return (path if path.startswith('/tmp/jiritsu/') else '/tmp/jiritsu/../..'+path).encode()

class Channel:
    def __init__(self,driver,operation,log):
        self.driver,self.operation,self.log=driver,operation,log
        self.sequence,self.usable=1,True
        self.packet_limit=getattr(operation,'packet_limit',512)
        if type(self.packet_limit) is not int or self.packet_limit not in (512,4096):
            raise ValueError('未知固定报文预算')
    def exchange(self,body,limit,*,action=None,path=None):
        if not self.usable or self.sequence>self.packet_limit:raise PermissionError('失步或报文超限，不再发送')
        self.log('file_request',action=action,path=path,sequence=self.sequence,
                 request_bytes=len(body),response_limit=limit)
        self.usable=False
        packet=HEADER.pack(len(body),0x40,self.sequence,0,0,0,0)+body
        self.operation.permitted_packet=packet
        try:
            self.operation.guard_packet(packet)
            if self.driver.write(packet)!=len(packet):raise OSError('短写，不重传')
        finally:self.operation.permitted_packet=None
        raw=self.driver.read(HEADER.size)
        self.log('response_header',raw_hex=raw.hex(),sequence=self.sequence,limit=limit)
        if len(raw)!=HEADER.size:raise ValueError('响应头长度异常')
        size,function,sequence,version,micon,offset,status=HEADER.unpack(raw)
        if function!=0x40 or sequence!=self.sequence or not 4<=size<=limit or status:raise ValueError('响应头字段异常')
        data=bytearray()
        try:
            # 参考Senser协议：响应按最多1MiB分帧，每帧内按32KiB逻辑块消费ZLP。
            # 后续帧有同序号的新响应头，size为剩余总长度，不能把头当成文件内容。
            frame_end=min(0x100000,size)
            while len(data)<size:
                block_start=len(data)
                block_end=min(block_start+0x8000,frame_end)
                while len(data)<block_end:
                    requested=block_end-len(data)
                    try:chunk=self.driver.read(requested)
                    except Exception as exc:
                        partial=getattr(exc,'usb_partial_data',b'')
                        if partial and len(partial)<=requested:
                            data.extend(partial)
                            self.log('response_native_error_partial',sequence=self.sequence,
                                received=len(partial),requested=getattr(exc,'usb_requested_bytes',requested),
                                backend_error_code=getattr(exc,'backend_error_code',None))
                        raise
                    self.log('response_body_fragment',sequence=self.sequence,offset=len(data),
                             requested=requested,received=len(chunk),block_end=block_end)
                    if not chunk or len(chunk)>requested:raise ValueError('响应体边界异常')
                    data.extend(chunk)
                block_size=block_end-block_start
                if block_size%512==0:
                    boundary=self.driver.read(512)
                    self.log('response_block_boundary',sequence=self.sequence,offset=len(data),received=len(boundary))
                    if boundary!=b'':raise ValueError('缺少分块空边界包')
                if len(data)==frame_end and len(data)<size:
                    raw=self.driver.read(HEADER.size)
                    self.log('response_continuation_header',raw_hex=raw.hex(),sequence=self.sequence,
                             received=len(data),remaining=size-len(data))
                    if len(raw)!=HEADER.size:raise ValueError('后续响应头长度异常')
                    remaining,part_function,part_sequence,*part_meta=HEADER.unpack(raw)
                    if (remaining!=size-len(data) or part_function!=0x40
                            or part_sequence!=self.sequence or part_meta[-1]):
                        raise ValueError('后续响应头字段异常')
                    frame_end=len(data)+min(0x100000,remaining)
        except BaseException as exc:
            self.log('response_body_failed',sequence=self.sequence,received=len(data),expected=size,
                     partial_sha256=hashlib.sha256(data).hexdigest(),error=type(exc).__name__+': '+str(exc))
            output=getattr(self.operation,'output',None)
            if output is not None:(output/f'response-{self.sequence:03}-partial.bin').write_bytes(data)
            raise
        self.sequence+=1;self.usable=True
        result,=struct.unpack_from('<I',data)
        self.log('file_result',result=hex(result),bytes=size-4,version=version,micon=micon,offset=offset,
                 action=action,path=path,sequence=self.sequence-1)
        if result:raise FileResultError(result,action=action,path=path)
        return bytes(data[4:])
    def select(self,path):self.exchange(struct.pack('<HH',0x1001,15)+b'\0'+wire(path)+b'\0',4,action='select',path=path)
    def read(self,path,limit):
        if self.operation.reads.get(path)!=limit:raise PermissionError('不是固定读取')
        self.select(path);return self.exchange(READ,limit+4,action='read',path=path)
    def put(self,path,data):
        if self.operation.writes.get(path)!=data:raise PermissionError('不是固定写入')
        self.select(path)
        if self.exchange(struct.pack('<HH',0x1001,16)+b'\0\xff\0'+data,4,action='write',path=path):raise ValueError('额外写入回执')
