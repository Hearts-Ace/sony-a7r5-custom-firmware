from pathlib import Path
import sys,io,json,hashlib,struct
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT/'vendor/audit-python')]
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn import arm64_const as R
AP=HERE.parent/'ap/appFw.so';raw=AP.read_bytes();elf=ELFFile(io.BytesIO(raw));audit=json.loads((HERE.parent/'import/module_audit.json').read_text())
obj=ELFFile(io.BytesIO((HERE.parent/'import/objects/r5_filter_runtime423.o').read_bytes()))
local={}
for sym in obj.get_section_by_name('.symtab').iter_symbols():
 if sym.name in ['refresh_wait','refresh_done','refresh_object','refresh_request']:
  sec=obj.get_section(sym['st_shndx']);base=next(int(x['va'],16) for x in audit['sections'] if x['object'].endswith('r5_filter_runtime423.o') and x['index']==sym['st_shndx']);local[sym.name]=base+sym['st_value']
assert len(local)==4
rows=[]
for bias in [0,0x40000000]:
 u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']!='PT_LOAD':continue
  lo=(s['p_vaddr']+bias)&-4096;hi=(s['p_vaddr']+bias+s['p_memsz']+4095)&-4096
  u.mem_map(lo,hi-lo)
  if s['p_filesz']:u.mem_write(s['p_vaddr']+bias,s.data())
 RAM=0x20000000;STOP=RAM+0xff000;SP=RAM+0xe0000;OBJECT=RAM+0x1000;OTHER=RAM+0x2000
 u.mem_map(RAM,0x100000)
 def w32(name,v):u.mem_write(local[name]+bias,struct.pack('<I',v))
 def w64(name,v):u.mem_write(local[name]+bias,struct.pack('<Q',v))
 def r32(name):return int.from_bytes(u.mem_read(local[name]+bias,4),'little')
 state={}
 def hook(c,pc,n,a):
  if pc==STOP:c.emu_stop();return
  if pc==0x348292c+bias:
   assert c.reg_read(R.UC_ARM64_REG_X0)==state['object']
   if state.get('race'):w32('refresh_wait',8)
  for i in range(19):c.reg_write(getattr(R,'UC_ARM64_REG_X'+str(i)),0xd000+i)
  c.reg_write(R.UC_ARM64_REG_PC,c.reg_read(R.UC_ARM64_REG_LR))
 for at in [STOP,0x318e5c0+bias,0x348292c+bias]:u.hook_add(UC_HOOK_CODE,hook,begin=at,end=at)
 def call(name,*args):
  for i in range(31):u.reg_write(getattr(R,'UC_ARM64_REG_X'+str(i)),0xa000+i)
  for i,v in enumerate(args):u.reg_write(getattr(R,'UC_ARM64_REG_X'+str(i)),v)
  u.reg_write(R.UC_ARM64_REG_SP,SP);u.reg_write(R.UC_ARM64_REG_LR,STOP)
  before=[u.reg_read(getattr(R,'UC_ARM64_REG_X'+str(i))) for i in range(19,30)]
  u.emu_start(audit['symbols'][name]+bias,STOP,count=10000)
  assert u.reg_read(R.UC_ARM64_REG_PC)==STOP and u.reg_read(R.UC_ARM64_REG_SP)==SP
  assert before==[u.reg_read(getattr(R,'UC_ARM64_REG_X'+str(i))) for i in range(19,30)]
 for case in ['exact','foreign_constructor','foreign_executor','stale_during_execute','inactive_late']:
  w32('refresh_wait',7);w32('refresh_done',0);w64('refresh_object',0)
  param=local['refresh_request']+bias+16 if case!='foreign_constructor' else OTHER
  call('r5_filter_refresh_construct425',OBJECT,param)
  exact=int.from_bytes(u.mem_read(local['refresh_object']+bias,8),'little')
  assert exact==(0 if case=='foreign_constructor' else OBJECT)
  if case=='inactive_late':w32('refresh_wait',0)
  state.update(object=OTHER if case=='foreign_executor' else OBJECT,race=case=='stale_during_execute')
  call('r5_filter_refresh_execute425',state['object'])
  assert r32('refresh_done')==(7 if case=='exact' else 0)
  rows.append({'bias':hex(bias),'case':case,'done':r32('refresh_done')})
report={'passed':True,'AP_sha256':hashlib.sha256(raw).hexdigest(),'cases':len(rows),'rows':rows,'limits':['Actual final AArch64 wrapper bodies execute; native constructor/executor are call-clobbering fixtures. No native scheduling, hardware or display.','Separate exact_request replay executes actual native facade/factory/constructor/queue path.']}
(HERE/'refresh_wrapper425_verified.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'cases':len(rows),'AP_sha256':report['AP_sha256']}))
