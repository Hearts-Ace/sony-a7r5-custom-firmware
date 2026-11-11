#!/usr/bin/env python3
"""真实 RAW extra-IFD 生产；SonyCrop 跟随冻结比例，DefaultCrop 保持原幅。"""
import argparse, hashlib, json, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE), str(HERE / 'tests')]
from verify_allocation_failure import Capture
from verify_cp import STACK, STOP, WORK
from unicorn import arm_const as A

HEADER, HEADER_BYTES = 0x50000000, 0x15000
ORIGINALS = ((9504,6336),(6240,4160),(4752,3168))
CROPS = (
    ((9504,5872,0,232),(6240,3856,0,152),(4752,2936,0,116)),
    ((9504,3976,0,1180),(6240,2608,0,776),(4752,1992,0,588)),
    ((7920,6336,792,0),(5200,4160,520,0),(3968,3168,392,0)),
    ((9504,5136,0,600),(6240,3376,0,392),(4752,2568,0,300)),
)


def sha(data): return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition: raise AssertionError(message)


class RawExif(Capture):
    def __init__(self, raw, patch):
        super().__init__(raw, patch)
        self.u.mem_map(HEADER, 0x18000)
        self.producers = []

    def hook(self, u, pc, size, unused):
        if pc in (0xade83c,0xadd162,0x45b0c0,0x45acbc): self.producers.append(hex(pc))
        if pc == 0x4e9304:
            # 附加元数据长度参数，不替代裁切标签值的实际来源。
            u.mem_write(u.reg_read(A.UC_ARM_REG_R1), b'\0\0')
            u.reg_write(A.UC_ARM_REG_R0, 0)
            u.reg_write(A.UC_ARM_REG_PC, u.reg_read(A.UC_ARM_REG_LR))
            return
        if pc == 0xb0de92: raise AssertionError('原生 RAW 头部构造触发诊断')
        return super().hook(u, pc, size, unused)

    def header(self, task, patched, unaligned=False):
        pointer = HEADER + int(unaligned)
        self.u.mem_write(HEADER, b'\xa5' * 0x18000)
        task_before = bytes(self.u.mem_read(task, 0x6688))
        self.producers = []
        if patched:
            result = self.resident(0x48a00a, task + 0x5b3c, pointer, task)
        else:
            for register, value in zip((A.UC_ARM_REG_R0,A.UC_ARM_REG_R1,A.UC_ARM_REG_R2),
                                       (task+0x5b3c,pointer,task)): self.u.reg_write(register,value)
            self.u.reg_write(A.UC_ARM_REG_SP, STACK+0xff00)
            self.u.reg_write(A.UC_ARM_REG_LR, STOP|1)
            self.u.emu_start(0xade83d, STOP, count=1000000)
            require(self.u.reg_read(A.UC_ARM_REG_PC)==STOP, '原生 RAW 构造未返回')
            require(self.u.reg_read(A.UC_ARM_REG_SP)==STACK+0xff00, '原生 RAW 构造栈不平衡')
            result = self.u.reg_read(A.UC_ARM_REG_R0)
        require(bytes(self.u.mem_read(task,0x6688))==task_before, 'RAW 修复改写照片 task')
        require(self.producers==['0xade83c','0xadd162','0x45b0c0','0x45acbc'], '未完整执行原生 RAW 头部链')
        require(bytes(self.u.mem_read(pointer+HEADER_BYTES,16))==b'\xa5'*16, '头部写出约定范围')
        return bytes(self.u.mem_read(pointer,HEADER_BYTES)),result


def tags(header):
    start=0x13fdc; count=struct.unpack_from('<I',header,start)[0]; result={}
    for k in range(count):
        tag,kind,number,offset=struct.unpack_from('<HHII',header,start+4+12*k)
        if tag in (0xc61f,0xc620,0x74c7,0x74c8):
            require((kind,number)==(4,2), 'RAW 裁切标签类型/数量不符')
            result[hex(tag)]=list(struct.unpack_from('<II',header,start+offset))
    require(len(result)==4, '原生裁切标签不全')
    return result


def prepare(r,number,selection,full,formats,raw_type):
    r.freeze(selection,number); task=r.bind(number%490,number)
    r.select(4+(selection-3)%4 if selection else 0)
    r.u.mem_write(task+0x30,struct.pack('<2H',*full))
    r.u.mem_write(task+0x234,struct.pack('<2H',*full))
    r.u.mem_write(task+0x6072,struct.pack('<2H',32,20))
    r.write(task+0x38,1); r.u.mem_write(task+0x726,b'\x0e')
    r.write(task+0x5980,formats[0]); r.write(task+0x5988,formats[1])
    offset=0x5984 if formats[0]==2 else 0x598c
    r.u.mem_write(task+offset,bytes((0 if raw_type<2 else raw_type,0 if raw_type==0 else 2)))
    r.write(task+0x98,1 if raw_type==1 else 0)
    return task


class JpegCallbacks(RawExif):
    def hook(self,u,pc,size,unused):
        if pc in (0x4727f4,0xaea0e4):
            # 任务前序记账/进度通知，不替代尺寸或格式选择。
            u.reg_write(A.UC_ARM_REG_R0,0)
            u.reg_write(A.UC_ARM_REG_PC,u.reg_read(A.UC_ARM_REG_LR)); return
        if pc==0xaeb5d8:
            # 原生资源查表边界；回放停在真实几何copy之后、硬件配置之前。
            p=u.reg_read(A.UC_ARM_REG_R1)
            u.mem_write(p,bytes(0xd8));u.mem_write(p+0x18,struct.pack('<QI',0x60000000,160000000))
            u.reg_write(A.UC_ARM_REG_R0,0)
            u.reg_write(A.UC_ARM_REG_PC,u.reg_read(A.UC_ARM_REG_LR)); return
        return super().hook(u,pc,size,unused)

    def request(self,task,substep):
        job=WORK+0x6000;self.write(job,task);self.u.mem_write(job+0x27,bytes((substep,)))
        self.u.reg_write(A.UC_ARM_REG_R0,job)
        self.u.reg_write(A.UC_ARM_REG_SP,STACK+0xff00)
        self.u.reg_write(A.UC_ARM_REG_LR,STOP|1)
        stop=0x473566 if substep==1 else 0x472a12
        self.u.emu_start(0x469a49,stop,count=300000)
        require(self.u.reg_read(A.UC_ARM_REG_PC)==stop, 'JPEG dispatcher未到实际request copy')
        sp=self.u.reg_read(A.UC_ARM_REG_SP)
        at=sp+(0x40 if substep==1 else 0x38)
        return struct.unpack('<6H',self.u.mem_read(at,12))


def jpeg_callbacks(raw,patch):
    r=JpegCallbacks(raw,patch);rows=[];number=1000
    for selection in (0,4,5,6,7):
        for formats in ((2,0),(2,1),(1,2),(2,4),(4,2),(1,0),(4,0)):
            number+=1;task=prepare(r,number,selection,(9504,6336),formats,1)
            main=(9600,6336,9504,6336,0,0);scn=(1664,1080,1616,1080,0,0)
            r.u.mem_write(task+0x5f78,struct.pack('<6H',*main))
            r.u.mem_write(task+0x5fdc,struct.pack('<6H',*scn))
            first=r.request(task,1);second=r.request(task,3)
            private=bool(selection and (1 in formats or 2 in formats))
            require((first!=main)==private and (second!=scn)==private, 'RAW/JPEG局部预览裁切隔离错误')
            if private:require(first[2:4]==CROPS[selection-4][0][:2], 'RAW/JPEG MAIN几何尺寸错误')
            require(bytes(r.u.mem_read(task+0x5f78,12))==struct.pack('<6H',*main), '共享MAIN源被改')
            require(bytes(r.u.mem_read(task+0x5fdc,12))==struct.pack('<6H',*scn), '共享SCN源被改')
            for heif_flag in (0,4):
                r.write(task+0x3c,heif_flag)
                source=struct.pack('<10H',1664,1080,0,0,1616,1080,0,0,1616,1080)
                target=struct.pack('<10H',256,120,0,0,160,120,0,0,160,120)
                r.u.mem_write(WORK+0x70,source);r.u.mem_write(WORK+0xf8,target)
                r.resident(0x46e07e,WORK+0x12c,0x20,owner=task)
                changed=bytes(r.u.mem_read(WORK+0x70,20))!=source
                require(changed==(private and not heif_flag), 'RAW/JPEG THM格式或HEIF门错误')
                out=struct.unpack('<10H',r.u.mem_read(WORK+0xf8,20))
                require(out[:6]==(256,120,0,0,160,120), 'THM canvas被改变')
            rows.append(dict(selection=selection,formats=list(formats),MAIN=list(first),SCN=list(second),
                             shared_source_unchanged=True,THM_HEIF_gate_preserved=True))
    return rows


def verify(raw,patch):
    require(sha(raw)==patch['output_sha256'], 'CP 组件摘要不符')
    require(patch['gate_bytes']<=0x110, '常驻门覆盖原生代码')
    require('aspect_raw_exif_build' in patch['module']['symbols'], '组件缺少 RAW SonyCrop 修复')
    r=RawExif(raw,patch); rows=[]; controls=[]; number=0
    for selection in range(4,8):
        for index,full in enumerate(ORIGINALS):
            for formats in ((2,0),(2,1),(1,2),(2,4),(4,2)):
                for raw_type in (0,1,2,3):
                    number+=1; task=prepare(r,number,selection,full,formats,raw_type)
                    old,a=r.header(task,False,bool(number&1)); new,b=r.header(task,True,bool(number&1))
                    width,height,x,y=CROPS[selection-4][index]
                    expected={'0xc61f':[32,20],'0xc620':list(full),
                              '0x74c7':[32+x,20+y],'0x74c8':[width,height]}
                    require(tags(new)==expected, 'SonyCrop 未跟随冻结比例')
                    require(a==b, '原生 RAW 构造返回值变化')
                    require(all(a==b for i,(a,b) in enumerate(zip(old,new))
                                if not (0x1421c<=i<0x1422c or 0x14a2c<=i<0x14a34)), 'RAW 非目标头部字节改变')
                    require(struct.unpack_from('<2I',new,0x14a2c)==(width,height), 'RAW EMB 声明未同步')
                    require(tags(old)['0x74c8']==list(full) and tags(old)!=expected,
                            '原生旧行为未形成裁切负例')
                    rows.append(dict(selection=selection,full_WH=list(full),formats=list(formats),
                        raw_type_fixture=raw_type,tags=tags(new),frozen_task_menu_changed=True,
                        native_header_sha256=sha(old),fixed_header_sha256=sha(new),
                        unaligned_header=bool(number&1),only_raw_crop_and_EMB_WH_changed=True,
                        RAW_EMB_WH=[width,height]))
    for name,wh in (('3:2',(9504,6336)),('4:3',(8448,6336)),
                    ('16:9',(9504,5344)),('1:1',(6336,6336))):
        number+=1; task=prepare(r,number,0,(9504,6336),(2,0),1)
        r.u.mem_write(task+0x30,struct.pack('<2H',*wh))
        old,a=r.header(task,False); new,b=r.header(task,True)
        require(old==new and a==b, '原生 RAW 比例被改写')
        controls.append(dict(aspect=name,task_WH=list(wh),tags=tags(new),header_exact=True))
    number+=1; task=prepare(r,number,5,(9504,6336),(2,0),1)
    r.write(r.symbols['aspect_cp_ready'],0)
    old,a=r.header(task,False); new,b=r.header(task,True)
    require(old==new and a==b, '未 ready 常驻门改变原生 RAW 头部')
    controls.append(dict(ready=False,header_exact=True))
    callbacks=jpeg_callbacks(raw,patch)
    return dict(passed=True,CP_sha256=sha(raw),cases=len(rows),controls=len(controls),
        rows=rows,control_rows=controls,camera_io=False,device_tested=False,
        JPEG_callback_cases=len(callbacks),JPEG_callback_rows=callbacks,
        gate_bytes=patch['gate_bytes'],native_executed=[
            '48a00a installed callsite/resident dispatch',
            'ade83c→ae96ca→add162→45b0c0→45acbc complete producer',
            'actual generated extra-IFD table and four native tag payloads',
            '469a48 actual dispatcher→4734ac/472994→473562/472a0e installed local request copies',
            '46e07e installed thumbnail request clear and per-photo geometry helper'],
        models=['4e9304 supplementary metadata-length parameter returns zero',
            'WH/origin/raw type/native aspect task fields are explicit fixtures',
            'JPEG resource lookup and bookkeeping boundary supplies descriptors; no codec executed',
            'existing OS/allocator/selection models in verify_cp/Capture'],
        limitations=['No sensor encoding/card writing/camera playback',
            'Adobe DNG Converter sample consumption is separate evidence; PS UI not executed',
            'M/S original WH/origin are producer fixtures, not new camera samples'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); require(not args.output.exists(), '拒绝覆盖已有验证证据')
    report=verify((args.build/'cp/cpapp-b.bin').read_bytes(),
                  json.loads((args.build/'cp/patch.json').read_text()))
    report['script_sha256']=sha(Path(__file__).read_bytes())
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','cases','controls','gate_bytes')}))


if __name__=='__main__': main()
