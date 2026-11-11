"""Final CP native RAW header producer; change only EMB WH, never SonyCrop."""
from pathlib import Path
import argparse,json,hashlib,struct
from unicorn import *
from unicorn.arm_const import *
H=Path(__file__).resolve().parent;p=argparse.ArgumentParser();p.add_argument('--build',type=Path,default=H/'integrated-o');p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists();RAW=(a.build/'cp/cp423.NONINSTALLABLE.bin').read_bytes();J=json.loads((a.build/'cp/build.json').read_text());BASE=0x108000;TASK=0x2200000;HEADER=0x50000000;SP=0x3000000;STOP=0x31ff000;STATE=0x1a394a0;N=J['sound_page_guard']['code_bytes'];sha=lambda b:hashlib.sha256(b).hexdigest();rows=[]
regs=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2]
def put(u,at,*values):u.mem_write(at,struct.pack('<'+'I'*len(values),*values))
def fresh(mode):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A9);u.mem_map(0x100000,0x3100000);u.mem_map(HEADER,0x18000);u.mem_write(BASE,RAW);u.mem_write(0x1a3a000,RAW[0x1198000-BASE:0x1198000-BASE+N]);put(u,0x1a3c068,0x1a40001);put(u,0x1a400e8,0x1a3a63e,0x1a3b63e);u.reg_write(UC_ARM_REG_CP_REG,(15,0,0,2,0,0,0,0x1a3c000));put(u,0x1112c58,3);put(u,0x1112c64,TASK,3*0x6688)
 if mode=='missing':put(u,0x1a400ec,0);u.mem_unmap(0x1a3b000,4096)
 if mode=='corrupt':u.mem_write(0x1a3a000+N-1,bytes([u.mem_read(0x1a3a000+N-1,1)[0]^1]))
 seen=[]
 def hook(cpu,pc,size,data):
  if pc in (0xade83c,0xadd162,0x45b0c0,0x45acbc):seen.append(hex(pc))
  if pc==0x4e9304:cpu.mem_write(cpu.reg_read(UC_ARM_REG_R1),b'\0\0');cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
  if pc==0xb0de92:raise AssertionError('native header diagnostic')
 u.hook_add(UC_HOOK_CODE,hook);return u,seen
def call(u,entry,end,ptr):
 for r,v in zip(regs,[TASK+0x5b3c,ptr,TASK]):u.reg_write(r,v)
 u.reg_write(UC_ARM_REG_CPSR,0x13);u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,STOP|1);u.emu_start(entry|1,end,count=4000000);assert u.reg_read(UC_ARM_REG_PC)==end and u.reg_read(UC_ARM_REG_SP)==SP
 return u.reg_read(UC_ARM_REG_R0)
for mode in ('good','missing','corrupt'):
 for choice in range(4,8):
  for size in ((9504,6336),(6240,4160),(4752,3168)):
   for formats in ((2,0),(2,1),(1,2),(2,4),(4,2)):
    for rawtype in (0,1,2,3):
     u,seen=fresh(mode);put(u,STATE,choice,choice,41);u.mem_write(STATE+12,bytes([choice]));u.mem_write(TASK+0x30,struct.pack('<2H',*size));u.mem_write(TASK+0x234,struct.pack('<2H',*size));u.mem_write(TASK+0x6072,struct.pack('<2H',32,20));put(u,TASK+0x38,1);u.mem_write(TASK+0x726,b'\x0e');put(u,TASK+0x5980,formats[0]);put(u,TASK+0x5988,formats[1]);off=0x5984 if formats[0]==2 else 0x598c;u.mem_write(TASK+off,bytes((0 if rawtype<2 else rawtype,0 if rawtype==0 else 2)));put(u,TASK+0x98,int(rawtype==1));ptr=HEADER+int(rawtype&1);task=bytes(u.mem_read(TASK,0x6688));u.mem_write(HEADER,b'\xa5'*0x18000);native_result=call(u,0xade83c,STOP,ptr);native=bytes(u.mem_read(ptr,0x15000));seen.clear();u.mem_write(HEADER,b'\xa5'*0x18000);result=call(u,0x48a00a,0x48a00e,ptr);after=bytes(u.mem_read(ptr,0x15000));assert native_result==result and bytes(u.mem_read(TASK,0x6688))==task;assert seen==['0xade83c','0xadd162','0x45b0c0','0x45acbc'];assert native[:0x14a2c]==after[:0x14a2c] and native[0x14a34:]==after[0x14a34:];assert bytes(u.mem_read(ptr+0x15000,16))==b'\xa5'*16
     actual=struct.unpack_from('<2I',after,0x14a2c)
     if mode=='good':assert actual!=size
     else:assert after==native
     rows.append(dict(mode=mode,choice=choice,size=size,formats=formats,raw_type=rawtype,EMB_WH=actual,native_header_sha256=sha(native),header_sha256=sha(after),only_EMB_WH_changes=True,task_exact=True,full_native_producer=seen.copy()))
report=dict(schema='r5-raw-embedded-only-header/1',passed=True,CP_sha256=sha(RAW),script_sha256=sha(Path(__file__).read_bytes()),cases=len(rows),rows=rows,SonyCrop_DefaultCrop_Bayer_native=True,native_producer='ade83c→ae96ca→add162→45b0c0→45acbc',fixtures=['task RAW size234 is native source; paired JPEG size is not used','raw type/header origin/format task fields input fixtures','4e9304 supplementary parameter length returnszero; no output header bytes substituted','flat TTBR/PTE fixtures and same final page guards'],limits=['No Bayer pixels/real files/encoding/camera; proves header producer and only8 permitted declaration bytes.'])
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(rows),CP=sha(RAW))))
