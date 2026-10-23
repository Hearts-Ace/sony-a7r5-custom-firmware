"""Native generic-list Enter -> setter -> real manager close_screen.

Executes original AP instructions and real router vtable+0x20 target.
Screen/model state and selected service remain explicit synthetic fixtures.
No physical display or OS loop is executed.
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
 w32(THIS+0x178,0x2ee);w64(THIS+0x180,ROUTER)
 # Resolve exactly the original vtable slot using its original ELF RELATIVE addend.
 w64(ROUTER,0x58d2fb8+bias);w64(0x58d2fd8+bias,0x1d15798+bias)
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
  if pc in (PRED,LOOKUP,SELECT):
   if pc==PRED:events.append(('predicate',));ret(0)
   elif pc==LOOKUP:events.append(('lookup',av[1]));assert av[1]==0x635;ret(DESC)
   elif pc==SELECT:events.append(('selected',av[0]));ret()
   return
  at=pc-bias
  trace.append(at)
  if at==0x1d15798:
   events.append(('native_close_screen',av[0],av[1]));assert av[:2]==[ROUTER,THIS+0x178]
  if at==0x369360c:
   events.append(('screen_validate',av[0]));assert av[0]==0x2ee;ret();return
  pointers={0x21e2b7c:MODE,0x21e2b4c:MENU,0x21e2b64:ROW,0x28bfdcc:MISC,0x28a80b8:PROP,0x28a80cc:META}
  if at in pointers:ret(pointers[at]);return
  if at==0x269700c:events.append(('refresh',));ret();return
  if at==0x3694f64:
   cpu.mem_write(av[2],bytes(cpu.mem_read(av[3],av[4])));ret();return
  if at in (0x2e7d208,0x2e7cee4,0x2542a30,0x2542a40,0x252d80c):ret();return
  if at==0x35b858c:raise AssertionError('native controller invariant failed')
 for at in [STOP,PRED,LOOKUP,SELECT]:u.hook_add(UC_HOOK_CODE,code,begin=at,end=at)
 for at in [0x21e2b7c,0x21e2b4c,0x21e2b64,0x28bfdcc,0x28a80b8,0x28a80cc,0x269700c,0x3694f64,0x2e7d208,0x2e7cee4,0x2542a30,0x2542a40,0x252d80c,0x35b858c,0x21e5244,0x21e52b0,0x21e2fb0,0x1d15798,0x1d157ec,0x369360c]:
  u.hook_add(UC_HOOK_CODE,code,begin=at+bias,end=at+bias)
 for selected in range(13):
  events.clear();trace.clear();w32(MENU,0x635);w32(ROW,0x1600+selected);w32(MODE,2)
  w32(ROUTER+0x1e8,0x4cf);u.mem_write(ROUTER+0x43c,b'\x01')
  for i,r in enumerate(GPRS):u.reg_write(r,0x123450000000+i)
  u.reg_write(R.UC_ARM64_REG_SP,SP);u.reg_write(R.UC_ARM64_REG_LR,STOP)
  u.reg_write(R.UC_ARM64_REG_X0,THIS);u.reg_write(R.UC_ARM64_REG_X1,RAM+0x18000)
  before=[u.reg_read(r)for r in GPRS]
  u.emu_start(0x21e45c8+bias,STOP,count=30000)
  assert u.reg_read(R.UC_ARM64_REG_PC)==STOP and u.reg_read(R.UC_ARM64_REG_SP)==SP
  assert u.reg_read(R.UC_ARM64_REG_X0)==1
  assert [u.reg_read(r)for r in GPRS[19:30]]==before[19:30]
  assert events==[('predicate',),('lookup',0x635),('selected',0x1600+selected),('refresh',),('native_close_screen',ROUTER,THIS+0x178),('screen_validate',0x2ee)],events
  assert all(a in trace for a in (0x21e5244,0x21e52b0,0x21e2fb0,0x1d15798,0x1d157ec))
  assert struct.unpack('<I',u.mem_read(ROUTER+0x1e8,4))[0]==0x2ee
  results.append(dict(bias=hex(bias),selected=selected,row=hex(0x1600+selected),events=events,native_default_dispatch=True,native_back_dispatch=True,real_router_close_queued=hex(0x2ee),callee_saved=True))
report=dict(passed=True,source=str(SOURCE.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest(),cases=len(results),rows=results,limits=['Original Enter, descriptor dispatcher, router dispatch, and real manager close_screen 1d15798 execute. Model storage/lookup, renderer refresh, notification, OS locks and screen-ID validation are explicit synthetic fixtures.','The actual router vtable+0x20 slot is resolved from its original ELF relocation and executes native close_screen, queuing screen2ee at manager+1e8. This bounded test does not execute the event loop close consumer or renderer.','Descriptor selected callback is a tracing fixture, not the new AP selection/save service. No device, display, ISP or loader execution.'])
(OUT/'native_enter_real_router423_replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items()if k!='rows'},ensure_ascii=False))
