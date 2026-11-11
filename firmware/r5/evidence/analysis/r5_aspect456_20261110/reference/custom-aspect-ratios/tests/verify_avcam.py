#!/usr/bin/env python3
"""AVCAM 原生 setter 等价、实际 slot 构造与 HEIF 几何窗口回放。"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import struct

from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn import arm64_const as A


def require(value,message):
    if not value:raise AssertionError(message)


class Replay:
    def __init__(self,raw):
        self.u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);self.u.mem_map(0,(len(raw)+4095)&~4095);self.u.mem_write(0,raw)
        self.u.mem_map(0x20000000,0x200000);self.u.mem_map(0x30000000,0x20000);self.u.mem_map(0x40000000,4096)
        self.u.reg_write(A.UC_ARM64_REG_CPACR_EL1,3<<20);self.errors=[]
        self.u.hook_add(UC_HOOK_CODE,self.hook)
    def hook(self,u,address,size,data):
        if address==0xd80:
            d,s,n=[u.reg_read(getattr(A,f'UC_ARM64_REG_X{i}')) for i in range(3)]
            require(n<=4096,'AVCAM memcpy 大小异常');u.mem_write(d,bytes(u.mem_read(s,n)))
            u.reg_write(A.UC_ARM64_REG_PC,u.reg_read(A.UC_ARM64_REG_LR))
        elif address==0x20bb10:
            self.errors.append(u.reg_read(A.UC_ARM64_REG_W2));u.reg_write(A.UC_ARM64_REG_PC,u.reg_read(A.UC_ARM64_REG_LR))
    def run(self,start,stop=0x40000000,args=()):
        for i,v in enumerate(args):self.u.reg_write(getattr(A,f'UC_ARM64_REG_X{i}'),v)
        self.u.reg_write(A.UC_ARM64_REG_SP,0x3001e000);self.u.reg_write(A.UC_ARM64_REG_LR,0x40000000)
        self.u.emu_start(start,stop,count=50000)
        require(self.u.reg_read(A.UC_ARM64_REG_PC)==stop,'AVCAM 路径未完成')
    def word(self,at):return struct.unpack('<I',self.u.mem_read(at,4))[0]


def verify(original,patched,report):
    before,after=Replay(original),Replay(patched);randomizer=random.Random(20261105)
    ctx=0x20001000;packet=0x20010000;cases=0
    for entry in (0x1f4dbc,0x1f4dfc):
        for main in (0,1,2,3,4,5,0xffffffff):
            for secondary in (0,1,2,3,4,0xffffffff):
                for slot in ((1,16,0,17) if entry==0x1f4dfc else (1,)):
                    buffer=bytearray(randomizer.randbytes(0x400))
                    struct.pack_into('<I',buffer,0xa4,main);struct.pack_into('<I',buffer,0x224,secondary)
                    for machine in (before,after):
                        machine.errors=[];machine.u.mem_write(ctx,bytes(buffer))
                        args=(ctx,slot,9504,5872) if entry==0x1f4dfc else (ctx,9504,5872)
                        machine.run(entry,args=args)
                    first=bytes(before.u.mem_read(ctx,0x400));second=bytes(after.u.mem_read(ctx,0x400))
                    require(first==second,f'等价 setter 改变原生结构 entry={entry:#x} formats={main}/{secondary} slot={slot}; '+str([(hex(i),a,b)for i,(a,b)in enumerate(zip(first,second))if a!=b][:12]))
                    require(before.errors==after.errors,'无效 slot 诊断改变');cases+=1
    setter_cases=cases
    wrapper=report['symbols']['aspect_avcam_jpeg']
    # 原生格式构造器真实执行；复制和诊断由模型完成。
    for aspect in range(4):
        for fmt in (0,1,2,4):
            for slot_offset,wh_offset in ((0xa4,0x1b6),(0x224,0x1c2)):
                buffer=bytes(0x1000);p=bytearray(0x800)
                struct.pack_into('<I',p,0,aspect);struct.pack_into('<HH',p,wh_offset,9504,5872)
                # 基于真实构造器的模板输入，尺寸原值 9504x6336。
                struct.pack_into('<II',p,0x1e8+0x12c+0x10,9504,6336)
                for m in (before,after):
                    m.u.mem_write(ctx,buffer);m.u.mem_write(packet,bytes(p))
                    m.u.reg_write(A.UC_ARM64_REG_X19,ctx);m.u.reg_write(A.UC_ARM64_REG_X20,packet)
                    m.run(0x1f4160 if m is before else wrapper,args=(ctx,fmt,0,aspect,0,0,packet+0x1e8,ctx+slot_offset))
                native=bytearray(before.u.mem_read(ctx,0x400));custom=bytes(after.u.mem_read(ctx,0x400))
                if aspect==2 and fmt==1:
                    # 期望由未经改写的原生单 slot setter 生成，逐字节对比。
                    before.run(0x1f4dfc,args=(ctx,1 if slot_offset==0xa4 else 16,9504,5872))
                    native=bytearray(before.u.mem_read(ctx,0x400))
                require(bytes(native)==custom,'JPEG wrapper 未隔离 RAW/HEIF 或尺寸字段错误')
                require(after.u.reg_read(A.UC_ARM64_REG_X19)==ctx and after.u.reg_read(A.UC_ARM64_REG_X20)==packet,'wrapper 破坏 owner')
                cases+=1
    wrapper_cases=cases-setter_cases
    # SCN 的实际 12 B 窗口，不依赖原 aspect 表。
    after.u.mem_write(ctx,struct.pack('<6H',2048,1200,2000,704,0,248))
    after.u.reg_write(A.UC_ARM64_REG_X27,ctx);after.run(0x2066b4,stop=0x206490)
    require(bytes(after.u.mem_read(0x3001e000+0xd8,4))==struct.pack('<2H',2000,704),'SCN 未使用 source valid WH')
    geometry_cases=1
    for width,height in ((9504,5872),(9504,3976),(9504,5136),(9504,3352),(9504,3512),(7920,6336),(7392,6336),(640,480),(16,8),(128,120),(160,106)):
        after.u.mem_write(ctx,struct.pack('<6H',9600,6336,width,height,0,0))
        after.u.reg_write(A.UC_ARM64_REG_X23,ctx);after.run(0x20684c,stop=0x2068b4)
        x,y,w,h=struct.unpack('<4H',after.u.mem_read(0x3001e000+0x144,8))
        if width*120>=height*160:expected=(160,(height*160//width)&~1)
        else:expected=((width*120//height)&~3,120)
        require((w,h)==expected and x==((160-w)//2)&~1 and y==(120-h)//2,'THM 居中 fit 错误')
        require(after.word(0x3001e000+0x58)==0x08000000,'THM fill 被改变');geometry_cases+=1
    return dict(passed=True,camera_io=False,native_setter_equivalence_cases=setter_cases,
        native_constructor_cases=wrapper_cases,HEIF_geometry_cases=geometry_cases,
        image_encoding=False,actual_native_constructor=True,memcpy_and_diagnostic='模型')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stock',type=Path,required=True);p.add_argument('--patched',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('输出证据已存在')
    raw=a.stock.read_bytes();patched=a.patched.read_bytes();report=json.loads(a.report.read_text())
    require(hashlib.sha256(raw).hexdigest()==report['input_sha256'] and hashlib.sha256(patched).hexdigest()==report['sha256'],'输入摘要不匹配')
    result=verify(raw,patched,report);result['AVCAM_sha256']=report['sha256'];result['test_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
