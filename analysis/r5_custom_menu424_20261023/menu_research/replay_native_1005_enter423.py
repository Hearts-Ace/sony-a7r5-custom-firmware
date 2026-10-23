"""Native1005 setting-list Enter -> real close_screen -> menu action setter.

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
ROWREC=RAM+0x18000;MAP=RAM+0x19000;NODE=RAM+0x19100
OWNER=RAM+0x16010;ROWLOOK=RAM+0x16014;ROWDIS=RAM+0x16018
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
 def r32(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 w32(THIS+0x178,0x2ed);w64(THIS+0x180,ROUTER)
 # Resolve exactly the original vtable slot using its original ELF RELATIVE addend.
 w64(ROUTER,0x58d2fb8+bias);w64(0x58d2fd8+bias,0x1d15798+bias)
 w64(0x591f9a8+bias,VT-0x10);w64(VT+0x250,PRED);w64(VT+0x328,OWNER);w64(VT+0x790,ROWLOOK)
 w64(DESC+0x88,SELECT);u.mem_write(DESC+0x90,b'\0')
 w32(ROWREC+0x18,0x4cf);u.mem_write(ROWREC+0x72,struct.pack('<H',0x55))
 w64(0x59611f8+bias,MAP);w64(MAP+0x10,NODE);w64(NODE+0x10,0);w64(NODE+0x18,0)
 w32(NODE+0x20,0x635);w64(NODE+0x28,DESC)
 events=[];trace=[]
 def ret(v=0):
  lr=u.reg_read(R.UC_ARM64_REG_LR)
  for i in range(1,19):u.reg_write(GPRS[i],0xdead0000+i)
  u.reg_write(R.UC_ARM64_REG_X0,v&((1<<64)-1));u.reg_write(R.UC_ARM64_REG_PC,lr)
 def code(cpu,pc,size,arg):
  if pc==STOP:cpu.emu_stop();return
  av=[cpu.reg_read(r)for r in GPRS[:5]]
  if pc in (PRED,OWNER,ROWLOOK,SELECT):
   if pc==PRED:events.append(('predicate',));ret(0)
   elif pc==OWNER:events.append(('row_owner_fixture',av[1]));assert av[1]==r32(ROW);ret(0x635)
   elif pc==ROWLOOK:events.append(('row_lookup_fixture',av[1]));assert av[1]==r32(ROW);ret(ROWREC)
   elif pc==SELECT:events.append(('selected',av[0]));ret()
   return
  at=pc-bias
  trace.append(at)
  if at==0x1d15798:
   events.append(('native_close_screen',av[0],av[1]));assert av[:2]==[ROUTER,THIS+0x178]
  if at==0x369360c:
   events.append(('screen_validate',av[0]));assert av[0]==0x2ed;ret();return
  pointers={0x21e0128:MENU,0x21e0140:ROW}
  if at in pointers:ret(pointers[at]);return
  if at==0x1bd5d50:events.append(('row_disabled_fixture',av[0]));ret(0);return
  if at==0x1bd851c:assert av[0]==0x635;events.append(('menu_normalize_fixture',av[0]));ret(0x635);return
  if at==0x3694f64:
   cpu.mem_write(av[2],bytes(cpu.mem_read(av[3],av[4])));ret();return
  if at in (0x2e7d208,0x2e7cee4,0x2542a30,0x2542a40,0x252d80c):ret();return
  if at==0x35b858c:raise AssertionError('native controller invariant failed')
 for at in [STOP,PRED,OWNER,ROWLOOK,SELECT]:u.hook_add(UC_HOOK_CODE,code,begin=at,end=at)
 for at in [0x21e0128,0x21e0140,0x1bd5d50,0x1bd851c,0x2e7d208,0x2e7cee4,0x35b858c,0x21e1b7c,0x21e1c90,0x21e03e0,0x1d15798,0x1d157ec,0x369360c,0x1bd9348,0x1bd906c,0x1bd90c4,0x1bc990c]:
  u.hook_add(UC_HOOK_CODE,code,begin=at+bias,end=at+bias)
 for selected in range(13):
  events.clear();trace.clear();w32(MENU,0x635);w32(ROW,0x1600+selected);w32(MODE,2)
  w32(ROUTER+0x1e8,0x4cf);u.mem_write(ROUTER+0x43c,b'\x01')
  for i,r in enumerate(GPRS):u.reg_write(r,0x123450000000+i)
  u.reg_write(R.UC_ARM64_REG_SP,SP);u.reg_write(R.UC_ARM64_REG_LR,STOP)
  u.reg_write(R.UC_ARM64_REG_X0,THIS);u.reg_write(R.UC_ARM64_REG_X1,RAM+0x18000)
  before=[u.reg_read(r)for r in GPRS]
  u.emu_start(0x21e1b7c+bias,STOP,count=30000)
  assert u.reg_read(R.UC_ARM64_REG_PC)==STOP and u.reg_read(R.UC_ARM64_REG_SP)==SP
  assert u.reg_read(R.UC_ARM64_REG_X0)==1
  assert [u.reg_read(r)for r in GPRS[19:30]]==before[19:30]
  assert events==[('row_disabled_fixture',0x1600+selected),('row_lookup_fixture',0x1600+selected),('native_close_screen',ROUTER,THIS+0x178),('screen_validate',0x2ed),('predicate',),('row_owner_fixture',0x1600+selected),('menu_normalize_fixture',0x635),('selected',0x1600+selected)],events
  assert all(a in trace for a in (0x21e1b7c,0x21e1c90,0x21e03e0,0x1d15798,0x1d157ec,0x1bd9348,0x1bd906c,0x1bd90c4,0x1bc990c))
  assert struct.unpack('<I',u.mem_read(ROUTER+0x1e8,4))[0]==0x2ed
  results.append(dict(bias=hex(bias),selected=selected,row=hex(0x1600+selected),events=events,native_default_dispatch=True,native_back_dispatch=True,real_router_close_queued=hex(0x2ed),callee_saved=True))
report=dict(passed=True,source=str(SOURCE.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest(),cases=len(results),rows=results,limits=['Original1005 Enter, native row child-screen read including callback sentinel55, native descriptor action dispatch+88, actual tree find/access, router and native close_screen execute. Row availability, row lookup, owner, menu normalizer and selected callback are explicit fixtures.','The actual router vtable+0x20 slot is resolved from its original ELF relocation and executes native close_screen, queuing screen2ed at manager+1e8. This bounded test does not execute the event loop close consumer or renderer.','Descriptor selected callback is a tracing fixture, not the new AP selection/save service. No device, display, ISP or loader execution.'])
(OUT/'native_1005_enter423_replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items()if k!='rows'},ensure_ascii=False))
