#!/usr/bin/env python3
"""执行装配后 AP 菜单/状态代码；文件系统与原厂服务采用显式模型。"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import sys

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn import arm64_const as A

DISPLAY_ORDER=(0,4,1,6,2,7,5,3)
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))


def require(value, message):
    if not value: raise AssertionError(message)


class Machine:
    relocations = None
    def __init__(self, raw, report, bias=0):
        self.u=Uc(UC_ARCH_ARM64,UC_MODE_ARM); self.bias=bias
        self.symbols=report['module']['symbols']; self.native=0;self.calls=[]
        self.files={};self.handles={};self.nextfd=7;self.fail=None;self.syscalls=[];self.mutate=None
        self.directory_flags=[];self.directory_syncs=[];self.directory_fail=None
        self.original_list=False
        self.pending_on_commit=False
        self.mutex_held=False;self.mutex_failure=0;self.mutex_calls=[]
        self.on_mutex_lock=None;self.on_locked_begin=None
        elf=ELFFile(io.BytesIO(raw))
        for s in elf.iter_segments():
            if s['p_type']!='PT_LOAD':continue
            address=s['p_vaddr']+bias;lo=address&~4095;size=(address+s['p_memsz']+4095&~4095)-lo
            self.u.mem_map(lo,size);self.u.mem_write(address,s.data())
        # 本回放不构造整套原生服务，仅 descriptor 是原生间接调用的输入。
        if Machine.relocations is None:
            Machine.relocations=[(a,c) for a,b,c in struct.iter_unpack('<QQq',elf.get_section_by_name('.rela.dyn').data())
                                 if b==1027 and 0x586b990<=a<0x586ba50]
        for address,addend in Machine.relocations:
            self.u.mem_write(address+bias,struct.pack('<Q',addend+bias))
        for address,size in [(0x20000000,0x200000),(0x30000000,0x20000),(0x40000000,4096)]:self.u.mem_map(address,size)
        self.u.reg_write(A.UC_ARM64_REG_CPACR_EL1,3<<20)
        self.u.hook_add(UC_HOOK_CODE,self.hook);self.u.hook_add(UC_HOOK_INTR,self.interrupt)

    def addr(self,name):return self.symbols[name]+self.bias
    def write(self,a,value,fmt='<I'):self.u.mem_write(a,struct.pack(fmt,value))
    def read(self,a,fmt='<I'):return struct.unpack(fmt,self.u.mem_read(a,struct.calcsize(fmt)))[0]
    def token(self):return self.read(self.addr('aspect_ap_selection'))
    def row_for_alias(self,alias):
        rows=self.addr('aspect_rows')
        matches=[rows+i*128 for i in range(8) if self.read(rows+i*128)==alias]
        require(len(matches)==1,'alias没有唯一descriptor行')
        return matches[0]
    def invoke(self,name,*arguments):
        for i,value in enumerate(arguments):self.u.reg_write(A.UC_ARM64_REG_X0+i,value)
        self.u.reg_write(A.UC_ARM64_REG_SP,0x3001f000);self.u.reg_write(A.UC_ARM64_REG_LR,0x40000000)
        self.u.emu_start(self.addr(name) if isinstance(name,str) else name+self.bias,0x40000000,count=500000)
        require(self.u.reg_read(A.UC_ARM64_REG_PC)==0x40000000,'AP 回放未返回')
        return self.u.reg_read(A.UC_ARM64_REG_X0)
    def returning(self,value=0):
        self.u.reg_write(A.UC_ARM64_REG_X0,value&0xffffffffffffffff)
        self.u.reg_write(A.UC_ARM64_REG_PC,self.u.reg_read(A.UC_ARM64_REG_LR))
    def hook(self,u,address,size,data):
        at=address-self.bias
        if (self.mutex_held and self.on_locked_begin and 'aspect_selection_begin' in self.symbols and
                address==self.addr('aspect_selection_begin')):
            fn=self.on_locked_begin;self.on_locked_begin=None;fn(self)
        if at==0x1c448dc:self.returning(self.native)
        elif (at==0x16dc820 and 'aspect_message_mutex' in self.symbols and
              u.reg_read(A.UC_ARM64_REG_X0)==self.addr('aspect_message_mutex')):
            require(not self.mutex_held,'非队列模型发生消息重入')
            self.mutex_calls.append('lock')
            if self.on_mutex_lock:
                fn=self.on_mutex_lock;self.on_mutex_lock=None;fn(self)
            if not self.mutex_failure:self.mutex_held=True
            self.returning(self.mutex_failure)
        elif (at==0x16dc620 and 'aspect_message_mutex' in self.symbols and
              u.reg_read(A.UC_ARM64_REG_X0)==self.addr('aspect_message_mutex')):
            require(self.mutex_held,'没有持锁却解锁')
            self.mutex_calls.append('unlock');self.mutex_held=False;self.returning()
        elif at==0x1c61d14:
            value=u.reg_read(A.UC_ARM64_REG_W0);require(value<4,'私有 ID 泄漏到原厂参数')
            self.native=value;self.calls.append(('set',value));self.returning()
        elif at==0x1c93d88:
            alias=u.reg_read(A.UC_ARM64_REG_W0);require(126<=alias<=129,'私有 alias 泄漏到原厂提交')
            if self.pending_on_commit:
                # 在原commit与save之间注入真实可能存在的准入等待状态。
                self.write(self.addr('aspect_ap_pending'),(self.token()<<32)|1,'<Q')
            self.calls.append(('commit',alias));self.returning()
        elif at==0x1c91e94:
            self.calls.append(('register',u.reg_read(A.UC_ARM64_REG_X1),u.reg_read(A.UC_ARM64_REG_X2)));self.returning()
        elif at==0x1c91c40:
            require(self.read(self.addr('aspect_rows'))==126,'八行表尚未就绪即发布 descriptor')
            self.calls.append(('menu-register',u.reg_read(A.UC_ARM64_REG_X1),u.reg_read(A.UC_ARM64_REG_X2)));self.returning()
        elif at==0x1bd851c:self.returning(33)
        elif at==0x1bd906c:self.returning(1)
        elif at==0x1bd90c4:
            self.write(0x20001000,0x586b990+self.bias,'<Q');self.returning(0x20001000)
        elif at==0x1bc397c and self.original_list:
            # list trampoline 已重放 sub sp,#0x230；原生成器主体由完成模型替代。
            u.reg_write(A.UC_ARM64_REG_SP,u.reg_read(A.UC_ARM64_REG_SP)+0x230);self.returning()
        elif address==0x20004010:
            alias=u.reg_read(A.UC_ARM64_REG_W1)
            require(126<=alias<=129,'通用 broker 收到私有 alias')
            self.returning(self.row_for_alias(alias))
        elif address==0x20004018:
            key=self.read(u.reg_read(A.UC_ARM64_REG_X1));value=self.read(u.reg_read(A.UC_ARM64_REG_X2))
            require(key==0x52b and value<4,'通用 broker 收到非法原厂比例')
            self.native=value;self.calls.append(('broker',key,value));self.returning()

    def string(self,address):
        result=bytearray()
        while len(result)<1024:
            c=self.u.mem_read(address+len(result),1)
            if c==b'\0':return result.decode()
            result.extend(c)
        raise AssertionError('字符串未终止')
    def interrupt(self,u,number,data):
        n=u.reg_read(A.UC_ARM64_REG_X8)
        args=[u.reg_read(A.UC_ARM64_REG_X0+i) for i in range(4)]
        self.syscalls.append(n)
        if self.mutate:
            fn=self.mutate;self.mutate=None;fn(self)
        result=-1
        if self.fail==n:result=-5
        elif n==56:
            name=self.string(args[1]);flags=args[2]
            if name=='/setting':
                self.directory_flags.append(flags)
                # 独立采用目标 Linux arm64 UAPI，拒绝把 O_DIRECT 当目录标志。
                require(flags==0o40000,'目标 ARM64 O_DIRECTORY 错误')
                if self.directory_fail!=56:
                    result=self.nextfd;self.nextfd+=1;self.handles[result]=[name,0]
            elif name in self.files or flags&64:
                if flags&512:self.files[name]=b''
                result=self.nextfd;self.nextfd+=1;self.handles[result]=[name,0]
        elif n in (63,64):
            name,position=self.handles[args[0]]
            if n==63:
                content=self.files.get(name,b'')[position:position+args[2]]
                u.mem_write(args[1],content);result=len(content)
            else:
                # 强制短写，验证完整写入循环。
                result=min(args[2],3);content=bytes(u.mem_read(args[1],result))
                old=self.files.get(name,b'');self.files[name]=old[:position]+content+old[position+result:]
            self.handles[args[0]][1]+=result
        elif n==57:
            name=self.handles.pop(args[0])[0]
            result=-5 if name=='/setting' and self.directory_fail==57 else 0
        elif n==82:
            name=self.handles[args[0]][0]
            if name=='/setting':self.directory_syncs.append(args[0])
            result=-5 if name=='/setting' and self.directory_fail==82 else 0
        elif n==38:
            self.files[self.string(args[3])]=self.files.pop(self.string(args[1]));result=0
        self.u.reg_write(A.UC_ARM64_REG_X0,result&0xffffffffffffffff)


def verify(raw,report):
    count=admission_cases=0
    record=lambda id:struct.pack('<4I',0x32505243,2,id,id^0xffffffff)
    path='/setting/custom_aspect_v2.dat'
    for bias in (0,0x10000000):
        m=Machine(raw,report,bias)
        m.invoke('aspect_menu_register',0x20000000,0x20000100,0x20000120)
        require(m.calls[0]==('menu-register',0x20000100,0x20000120),'原菜单构造器链未保留')
        m.calls=[];count+=1
        m.invoke('aspect_rows_register',0x20000000,0x20000100,0x20000120)
        rows=m.addr('aspect_rows')
        require([m.read(rows+i*128+0x34) for i in range(8)]==list(DISPLAY_ORDER),'八项显示顺序不符')
        for position,id in enumerate(DISPLAY_ORDER):
            r=rows+position*128
            if id<4:
                require(bytes(m.u.mem_read(r,128))==bytes(m.u.mem_read(0x3f46600+bias+id*128,128)),'原厂行内容改变')
            else:
                require(m.read(r)==0x1700+id-4 and m.read(r+0x34)==id,'新选项身份错误')
        for i in range(4):
            require(m.invoke('aspect_normalize',0,0x1700+i)==0x1700+i,'alias 归一失败')
            require(m.invoke('aspect_parent',0,0x1700+i)==33,'父叶错误')
        require(len(m.calls)>=2 and m.calls[0]==('register',0x20000100,0x20000120)
                and m.calls[-1][2]-m.calls[-1][1]==64,'构造器链未保留')
        registered=m.calls[-1][1]
        for i in range(4):
            require(m.read(registered+i*16,'<Q')==0x1700+i and m.read(registered+i*16+8,'<Q')==m.row_for_alias(0x1700+i),'私有注册顺序或行指针改变')
        # 原生通用 setter 的整段行查找和间接调用：禁止/父叶/查表服务为模型。
        self=0x20002000;vt=0x20003000;stub=0x20004000
        m.write(self,vt,'<Q');m.u.mem_write(stub,bytes.fromhex('00008052c0035fd6'))
        m.u.mem_write(stub+8,bytes.fromhex('20048052c0035fd6'))
        m.write(vt+0x250,stub,'<Q');m.write(vt+0x328,stub+8,'<Q')
        for i,alias in enumerate([126,127,128,129,0x1700,0x1701,0x1702,0x1703]):
            m.invoke(0x1bd924c,self,alias)
            require(m.invoke('aspect_get')==i,'原生行应用没有进入私有 setter')
            require(m.native==(i if i<4 else 0),'原厂值域改变')
            m.invoke('aspect_commit',alias)
            require(m.files[path]==record(i if i>=4 else 0),'保存记录错误')
            require(m.directory_flags[-1]==0o40000 and len(m.directory_syncs)==i+1,
                    '保存缺少目标目录同步')
            count+=1
        # 取消：模拟原生保存进入前 ID，浏览其他项，原生 setter 还原保存值。
        m.invoke('aspect_set',5);saved=m.invoke('aspect_get');m.invoke('aspect_set',7)
        epoch=m.token()&~15;m.invoke('aspect_set',saved)
        require(m.invoke('aspect_get')==5 and m.token()&~15!=epoch,'取消未还原/未失效旧快照')
        previous=m.token();m.invoke('aspect_set',8);require(m.token()==previous,'非法参数改变状态')
        # 等待时只抑制getter/预览；同epoch全部成功后才恢复，失败先撤选。
        pending=lambda:mm.read(mm.addr('aspect_ap_pending'),'<Q')
        mm=Machine(raw,report,bias);mm.files[path]=record(4);mm.invoke('aspect_restore_once')
        frozen=mm.token();saved_file=mm.files[path];before_syscalls=len(mm.syscalls)
        require(mm.invoke('aspect_selection_begin',frozen)==1 and mm.invoke('aspect_get')==0,'等待准入仍显示私有比例')
        require(mm.invoke('aspect_selection_begin',frozen)==1 and pending()&0xffffffff==2,'同epoch并发计数错误')
        mm.invoke('aspect_selection_end',frozen,0xf000,1)
        require(mm.invoke('aspect_get')==0 and pending()&0xffffffff==1,'第一条成功应答过早发布')
        mm.invoke('aspect_selection_end',frozen,0xf000,1)
        require(mm.invoke('aspect_get')==4 and pending()&0xffffffff==0,'全部成功后未恢复私有比例')
        require(len(mm.syscalls)==before_syscalls and mm.files[path]==saved_file,'准入回调进行了文件操作')
        admission_cases+=4
        mm.invoke('aspect_selection_begin',frozen)
        mm.invoke('aspect_set',5);newer=mm.token();mm.invoke('aspect_selection_begin',newer)
        mm.invoke('aspect_selection_end',frozen,0xf001,1)
        require(mm.token()==newer and pending()==(newer<<32)|1 and mm.invoke('aspect_get')==0,
                '旧失败应答撤销/解除较新epoch等待')
        mm.invoke('aspect_selection_end',newer,0xf000,1)
        require(mm.invoke('aspect_get')==5,'新epoch成功未恢复')
        admission_cases+=2
        mm.invoke('aspect_selection_begin',newer);mm.invoke('aspect_selection_begin',newer)
        mm.invoke('aspect_selection_end',newer,0xf001,1)
        require(mm.token()==((newer+16)&0xfffffff0) and mm.invoke('aspect_get')==0,
                '失败最后计数清除前未撤销私有epoch')
        require(mm.invoke('aspect_selection_id',newer)==0,'失败后的旧token重新发布私有比例')
        mm.invoke('aspect_selection_end',newer,0xf000,1);mm.invoke('aspect_restore_once')
        require(mm.invoke('aspect_get')==0 and mm.files[path]==saved_file,'本次失败被已保存记录重新启用')
        admission_cases+=2
        for invalid in (0,4,8,11):
            previous=mm.token()
            require(mm.invoke('aspect_selection_begin',invalid)==0,'非法请求进入准入计数')
            mm.invoke('aspect_selection_end',invalid,0xf001,0)
            require(mm.token()==previous,'非法应答改变运行选择');admission_cases+=1
        mm=Machine(raw,report,bias);mm.pending_on_commit=True
        mm.invoke('aspect_commit',0x1700)
        require(mm.invoke('aspect_get')==0 and mm.files[path]==record(4),
                '准入等待的getter0被错误保存，丢失用户偏好')
        admission_cases+=1
        count+=13
        # 真实发送闸门：正常/失败应答均成对解锁，取锁失败不解锁也不留下pending。
        for native in range(4):
            mm=Machine(raw,report,bias);mm.invoke('aspect_restore_once');mm.invoke('aspect_set',4)
            original=mm.token();before_syscalls=len(mm.syscalls)
            frozen=mm.invoke('aspect_message_enter',native)
            require(frozen==(original if native==0 else 0) and mm.mutex_held,'闸门冻结值或持锁状态错误')
            if native==0:require(mm.invoke('aspect_get')==0,'持锁准入等待仍显示私有比例')
            mm.invoke('aspect_message_leave',frozen,0xf001)
            require(mm.mutex_calls==['lock','unlock'] and not mm.mutex_held,'应答未正确释放mutex')
            require(mm.token()==(((original+16)&0xfffffff0) if native==0 else original),
                    '失败应答撤销了错误选择')
            require(len(mm.syscalls)==before_syscalls,'闸门进行了文件操作');count+=1;admission_cases+=1
        for error in (22,35):
            mm=Machine(raw,report,bias);mm.invoke('aspect_restore_once');mm.invoke('aspect_set',7)
            original=mm.token();mm.mutex_failure=error
            marker=mm.invoke('aspect_message_enter',0)
            require(marker==original&~8 and not mm.mutex_held and mm.mutex_calls==['lock'],
                    '取锁失败伪造持锁或错误marker')
            require(mm.invoke('aspect_get')==0 and not mm.read(mm.addr('aspect_ap_pending'),'<Q')&0xffffffff,
                    '取锁失败未撤销选择/释放等待计数');count+=1;admission_cases+=1
        mm=Machine(raw,report,bias);mm.invoke('aspect_restore_once');mm.invoke('aspect_set',4)
        original=mm.token();middle=((original+16)&0xfffffff0)|13;latest=((middle+16)&0xfffffff0)|14
        mm.on_mutex_lock=lambda m:m.write(m.addr('aspect_ap_selection'),middle)
        mm.on_locked_begin=lambda m:m.write(m.addr('aspect_ap_selection'),latest)
        frozen=mm.invoke('aspect_message_enter',0)
        require(frozen==latest and mm.read(mm.addr('aspect_ap_pending'),'<Q')==(latest<<32)|1,
                '登记前改选导致未拥有的pending被冻结')
        mm.invoke('aspect_message_leave',frozen,0xf001)
        require(mm.invoke('aspect_get')==0 and not mm.mutex_held,'重读登记后的失败未撤选/解锁')
        count+=1;admission_cases+=1
        mm=Machine(raw,report,bias);mm.invoke('aspect_restore_once');mm.invoke('aspect_set',4)
        original=mm.token();mm.write(mm.addr('aspect_ap_pending'),(original<<32)|0xffffffff,'<Q')
        require(mm.invoke('aspect_message_enter',0)==original&~8 and not mm.mutex_held and
                mm.mutex_calls==['lock','unlock'],'准入计数上限未拒绝/释放已取得的锁')
        mm.invoke('aspect_set',5);newer=mm.token()
        require(mm.invoke('aspect_message_enter',0)==newer and
                mm.read(mm.addr('aspect_ap_pending'),'<Q')==(newer<<32)|1,'上限失败永久阻止新epoch重试')
        mm.invoke('aspect_message_leave',newer,0xf000)
        require(mm.invoke('aspect_get')==5 and not mm.mutex_held,'上限后的新epoch成功未恢复')
        count+=1;admission_cases+=1
        # 真实通用 apply 主体直接把 row+34 交给 broker，与 descriptor setter 分开覆盖。
        m.write(0x5945a40+bias,0x20007000,'<Q');m.write(0x20007000,0x20008000,'<Q')
        m.write(0x20008000,0x20009000,'<Q');m.write(0x20009000+8,0x20004018,'<Q')
        m.write(vt+0x790,0x20004010,'<Q')
        for i,alias in enumerate([126,127,128,129,0x1700,0x1701,0x1702,0x1703]):
            m.invoke('aspect_apply',self,alias)
            require(m.invoke('aspect_get')==i,'通用 apply 没有保持独立选择')
            require(m.calls[-1]==('broker',0x52b,i if i<4 else 0),'broker 值投影错误');count+=1
        # 真正的完成模型，确认双图像列清空、八个文字齐全。
        m.original_list=True;table=0x20010000;model=0x20011000;description=0x20015000
        m.write(table,28);m.write(table+8,model,'<Q');m.write(model+0xd30,8)
        m.u.mem_write(description,struct.pack('<4I',0,0,33,0));m.invoke('aspect_list',0,table,description)
        require([m.read(model+0x830+i*4) for i in range(8)]==[0x0200a094,0x0200ab60,0x0200a114,0x0200ab62,0x0200a095,0x0200ab63,0x0200ab61,0x0200a113],'文字列表顺序错误')
        require(all(m.read(model+0x30+i*4)==0xffffffff and m.read(model+0x430+i*4)==0xffffffff for i in range(8)),'列表原图像未清空')
        count+=4
        for payload in (record(4),record(7),record(0),record(8),record(4)+b'X',record(4)[:15],bytes(16)):
            r=Machine(raw,report,bias);r.files[path]=payload;r.invoke('aspect_restore_once')
            want=struct.unpack_from('<I',payload,8)[0] if payload in (record(4),record(7)) else 0
            require(r.invoke('aspect_get')==want,'恢复校验失败');count+=1
        r=Machine(raw,report,bias);r.files[path]=record(4)
        r.mutate=lambda mm:mm.write(mm.addr('aspect_ap_selection'),16)
        r.invoke('aspect_restore_once');require(r.token()==16,'迟到恢复覆盖显式取消');count+=1
        for fail in (56,64,82,57,38):
            r=Machine(raw,report,bias);r.files[path]=record(4);r.invoke('aspect_set',7);r.fail=fail
            r.invoke('aspect_commit',0x1703)
            require(r.files[path]==record(4),'失败保存损坏旧记录')
            require(r.read(r.addr('aspect_persist_status'))==2,'保存错误未报告');count+=1
        for fail in (56,82,57):
            r=Machine(raw,report,bias);r.files[path]=record(4);r.invoke('aspect_set',7)
            r.directory_fail=fail;r.invoke('aspect_commit',0x1703)
            require(r.files[path]==record(7),'rename 后文件状态判断错误')
            require(r.read(r.addr('aspect_persist_status'))==2,'目录阶段错误未报告')
            require(len(r.directory_syncs)==(0 if fail==56 else 1),'目录同步顺序错误');count+=1
    return dict(passed=True,camera_io=False,cases=count,admission_cases=admission_cases,load_biases=[0,0x10000000],
                actual_native_row_application=True,filesystem='SVC 模型，强制短写与错误注入',
                actual_native_broker_application=True,
                native_parameter_and_registry_services='模型',native_UI=False,
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ap',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('输出证据已存在')
    raw=args.ap.read_bytes();report=json.loads(args.report.read_text())
    require(hashlib.sha256(raw).hexdigest()==report['sha256'],'AP 与安装收据不匹配')
    result=verify(raw,report);result['AP_sha256']=report['sha256']
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
