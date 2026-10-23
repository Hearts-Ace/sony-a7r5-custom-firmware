"""Bounded native generic-list Enter -> descriptor setter -> back dispatch.

Executes original AP AArch64 controller and descriptor-dispatch instructions.
Model values, locks, notification, router and descriptor lookup are fixtures;
this does not execute a physical screen or establish actual router pop meaning.
"""
from pathlib import Path
import hashlib,io,json,struct,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python')]
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn import arm64_const as R
SOURCE=ROOT/'build_r5_m4strict_4.04_20261015/patched/appFw.so'
raw=SOURCE.read_bytes();elf=ELFFile(io.BytesIO(raw))
RAM=0x20000000;STOP=RAM+0x1ff000;SP=RAM+0x100000
THIS=RAM+0x10000;ROUTER=RAM+0x12000;ROUTERVT=RAM+0x13000
VT=RAM+0x14000;DESC=RAM+0x15000;PRED=RAM+0x16000
LOOKUP=RAM+0x16004;SELECT=RAM+0x16008;BACK=RAM+0x1600c
MENU=RAM+0x17000;ROW=RAM+0x17004;MODE=RAM+0x17008
MISC=RAM+0x17010;PROP=RAM+0x17100;META=RAM+0x17200
GPRS=[getattr(R,'UC_ARM64_REG_X'+str(i))for i in range(29)]+[R.UC_ARM64_REG_FP,R.UC_ARM64_REG_LR]
results=[]
for bias in (0,0x40000000):
 u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
 for seg in elf.iter_segments():
  if seg['p_type']!='PT_LOAD':continue
  lo=(seg['p_vaddr']+bias)&-4096;hi=(seg['p_vaddr']+bias+seg['p_memsz']+4095)&-4096
  if hi>lo:u.mem_map(lo,hi-lo)
  if seg['p_filesz']:u.mem_write(seg['p_vaddr']+bias,seg.data())
 u.mem_map(RAM,0x200000)
 def w32(a,v):u.mem_write(a,struct.pack('<I',v))
 def w64(a,v):u.mem_write(a,struct.pack('<Q',v))
 w64(THIS+0x180,ROUTER);w64(ROUTER,ROUTERVT);w64(ROUTERVT+0x20,BACK)
 w64(0x591f9a8+bias,VT-0x10);w64(VT+0x248,PRED);w64(VT+0x10,LOOKUP)
 w64(DESC+0x80,SELECT);w64(META,0);w64(META+8,0)
 events=[];trace=[]
 def ret(v=0):
  lr=u.reg_read(R.UC_ARM64_REG_LR)
  for i in range(1,19):u.reg_write(GPRS[i],0xdead0000+i)
  u.reg_write(R.UC_ARM64_REG_X0,v&((1<<64)-1));u.reg_write(R.UC_ARM64_REG_PC,lr)
 def code(cpu,pc,size,arg):
  if pc==STOP:cpu.emu_stop();return
  av=[cpu.reg_read(r)for r in GPRS[:5]]
  if pc in (PRED,LOOKUP,SELECT,BACK):
   if pc==PRED:events.append(('predicate',));ret(0)
   elif pc==LOOKUP:events.append(('lookup',av[1]));assert av[1]==0x635;ret(DESC)
   elif pc==SELECT:events.append(('selected',av[0]));ret()
   else:events.append(('back_virtual_0x20',av[0],av[1]));assert av[:2]==[ROUTER,THIS+0x178];ret()
   return
  at=pc-bias
  trace.append(at)
  pointers={0x21e2b7c:MODE,0x21e2b4c:MENU,0x21e2b64:ROW,0x28bfdcc:MISC,0x28a80b8:PROP,0x28a80cc:META}
  if at in pointers:ret(pointers[at]);return
  if at==0x269700c:events.append(('refresh',));ret();return
  if at==0x3694f64:
   cpu.mem_write(av[2],bytes(cpu.mem_read(av[3],av[4])));ret();return
  if at in (0x2e7d208,0x2e7cee4,0x2542a30,0x2542a40,0x252d80c):ret();return
  if at==0x35b858c:raise AssertionError('native controller invariant failed')
 for at in [STOP,PRED,LOOKUP,SELECT,BACK]:u.hook_add(UC_HOOK_CODE,code,begin=at,end=at)
 for at in [0x21e2b7c,0x21e2b4c,0x21e2b64,0x28bfdcc,0x28a80b8,0x28a80cc,0x269700c,0x3694f64,0x2e7d208,0x2e7cee4,0x2542a30,0x2542a40,0x252d80c,0x35b858c,0x21e5244,0x21e52b0,0x21e2fb0]:
  u.hook_add(UC_HOOK_CODE,code,begin=at+bias,end=at+bias)
 for selected in range(13):
  events.clear();trace.clear();w32(MENU,0x635);w32(ROW,0x1600+selected);w32(MODE,2)
  for i,r in enumerate(GPRS):u.reg_write(r,0x123450000000+i)
  u.reg_write(R.UC_ARM64_REG_SP,SP);u.reg_write(R.UC_ARM64_REG_LR,STOP)
  u.reg_write(R.UC_ARM64_REG_X0,THIS);u.reg_write(R.UC_ARM64_REG_X1,RAM+0x18000)
  before=[u.reg_read(r)for r in GPRS]
  u.emu_start(0x21e45c8+bias,STOP,count=30000)
  assert u.reg_read(R.UC_ARM64_REG_PC)==STOP and u.reg_read(R.UC_ARM64_REG_SP)==SP
  assert u.reg_read(R.UC_ARM64_REG_X0)==1
  assert [u.reg_read(r)for r in GPRS[19:30]]==before[19:30]
  assert events==[('predicate',),('lookup',0x635),('selected',0x1600+selected),('refresh',),('back_virtual_0x20',ROUTER,THIS+0x178)],events
  assert all(a in trace for a in (0x21e5244,0x21e52b0,0x21e2fb0))
  results.append(dict(bias=hex(bias),selected=selected,row=hex(0x1600+selected),events=events,native_default_dispatch=True,native_back_dispatch=True,callee_saved=True))
report=dict(passed=True,source=str(SOURCE.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest(),cases=len(results),rows=results,limits=['Original controller and 1bd5444/1bcf4a0 descriptor dispatcher execute. Model storage/lookup, renderer refresh, notification, OS locks and router target are explicit synthetic fixtures.','Back is the original controller vtable+0x20 dispatch; this test does not execute the router implementation or prove the destination screen.','Descriptor selected callback is a tracing fixture, not the new AP selection/save service. No device, display, ISP or loader execution.'])
(OUT/'native_enter423_replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items()if k!='rows'},ensure_ascii=False))
