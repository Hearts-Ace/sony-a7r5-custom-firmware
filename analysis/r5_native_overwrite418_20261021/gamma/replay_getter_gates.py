"""Full GPR/APSR proof of each fixed MOVT detour, including zero cold BSS."""
from pathlib import Path
import hashlib,json,random,struct,sys
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from verify_r5_m4strict_cp_cpu import new_cpu,SP,STOP
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
BUILD=HERE/'getter_build_dynamic'
cp=(ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin').read_bytes();meta=json.loads((BUILD/'gates.json').read_text())
assert hashlib.sha256(cp).hexdigest()==meta['source_CP_sha256']
raw=(BUILD/'gates.bin').read_bytes();u=new_cpu(cp);rx=int(meta['RX'],16);bank=0x3100000;ctx=bank+14128;u.mem_map(bank,0x10000);u.mem_write(rx,raw);state={'stop':0,'low':SP}
def hook(c,at,n,_):
 state['low']=min(state['low'],c.reg_read(UC_ARM_REG_SP))
 if at==state['stop']:c.emu_stop()
u.hook_add(UC_HOOK_CODE,hook);random.seed(418);checks=[]
regs=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12,UC_ARM_REG_SP,UC_ARM_REG_LR]
for record in meta['records']:
 site=int(record['site'],16);u.mem_write(site,bytes.fromhex(record['after']))
 for capacity,pointer,ready in [(0,0,0),(1,bank,0),(14128,0,0),(14128,bank,0),(14128,bank,0x4186b11),(14128,bank,0x4186a11),(14128,bank,0xffffffff)]:
  u.mem_write(0x1a39448,struct.pack('<2I',pointer,capacity))
  u.mem_write(ctx+23012,struct.pack('<I',ready))
  for flags in range(32):
   values=[random.getrandbits(32)for _ in regs];values[13]=SP;values[14]|=1
   for r,v in zip(regs,values):u.reg_write(r,v)
   u.reg_write(UC_ARM_REG_CPSR,(flags<<27)|0x1f3);state.update(stop=int(record['resume'],16),low=SP)
   u.emu_start(site|1,STOP,count=100)
   expected=values.copy();expected[record['register']]=bank+record['custom_bank_offset']if capacity==14128 and pointer and ready==0x4186a11 else int(record['original_pointer'],16)
   assert [u.reg_read(r)for r in regs]==expected,(record['symbol'],hex(ready),flags)
   assert u.reg_read(UC_ARM_REG_PC)==state['stop'] and u.reg_read(UC_ARM_REG_CPSR)&0xf8000000==flags<<27
   assert SP-state['low']==24
   checks.append(dict(site=record['site'],ready=hex(ready),capacity=capacity,pointer=hex(pointer),flags=flags))
assert rx+len(raw)<=0x1196000
out=dict(schema='r5-native-gamma418-getters/2',passed=True,camera_io=False,installable=False,checks=len(checks),cases=checks,code_bytes=len(raw),context=hex(ctx),common_ready=hex(ctx+23012),source_CP_sha256=meta['source_CP_sha256'],RX=dict(start=hex(rx),end=hex(rx+len(raw))),source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in[HERE/'getter_gates.py',Path(__file__),BUILD/'getter_gates.S',BUILD/'getter_gates.o']},limits=['Only nativeMOVT detours executed; integrated37612B heap lifetime/zero/STATE publication must be separately proven.','Native input semantics and hardware/render scheduling not established by register/flags preservation.'])
(HERE/'getter_replay_dynamic.json').write_text(json.dumps(out,indent=2)+'\n');print('PASS',len(checks),'dynamic getter full GPR/APSR states;',len(raw),'bytes RX')
