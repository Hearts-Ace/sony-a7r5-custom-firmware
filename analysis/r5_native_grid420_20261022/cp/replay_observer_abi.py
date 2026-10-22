"""Compare original uploader and wrapped uploader with both stack arguments."""
from pathlib import Path
import sys,json,hashlib,struct
H=Path(__file__).resolve().parent;ROOT=H.parents[2]
sys.path.insert(0,str(ROOT/'research/r5_custom_lut/scripts'))
import replay_correction_builder as b
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
raw=(H/'cp420-grid.NONINSTALLABLE.bin').read_bytes();rows=[]
for arg5 in (0,1):
 outputs=[]
 for patched in (False,True):
  e=b.Replay('r5');u=e.uc
  if patched:u.mem_write(b.BASE,raw)
  u.mem_map(0x1a39000,0x1000) # no custom bank: observer must leave native path intact
  b.w(u,b.DEV+0x184,b.MMIO);b.w(u,b.STATE+0x14,b.BANK);u.mem_write(b.STATE+0x18,b'\x01')
  u.mem_write(b.BANK,bytes((i*17+3)&255 for i in range(1620)))
  b.w(u,b.SP,arg5,b.TABLE)
  seen=[]
  def hook(cpu,pc,n,_):
   sp=cpu.reg_read(UC_ARM_REG_SP);assert bytes(cpu.mem_read(sp+20,8))==struct.pack('<II',arg5,b.TABLE);seen.append(True)
  u.hook_add(UC_HOOK_CODE,hook,begin=0x414f48,end=0x414f48)
  regs=[UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11]
  saved=[0x98760000+i for i in range(8)]
  for reg,v in zip(regs,saved):u.reg_write(reg,v)
  e.call(0x414f44,b.DEV,b.DEV,b.CONTROL,b.STATE)
  assert seen and [u.reg_read(r)for r in regs]==saved
  outputs.append((bytes(u.mem_read(b.CTX,0x18000)),bytes(u.mem_read(b.MMIO,0x10000)),u.reg_read(UC_ARM_REG_R0)))
 assert outputs[0]==outputs[1]
 rows.append(dict(copy_only=arg5,stack_arg6=hex(b.TABLE),native_memory_MMIO_return_and_callee_saved_equal=True))
q=dict(passed=True,CP_sha256=hashlib.sha256(raw).hexdigest(),rows=rows,camera_io=False)
(H/'observer_abi_replay.json').write_text(json.dumps(q,indent=2)+'\n');print('PASS original/wrapped upload; two stack arguments and callee-saved registers')
