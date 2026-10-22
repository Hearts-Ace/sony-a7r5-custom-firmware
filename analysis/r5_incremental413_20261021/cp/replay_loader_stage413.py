"""Strict404/stage413 native loader comparison with source-bound two reads."""
from pathlib import Path
import hashlib,json,struct,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor/audit-python'))
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
BASE=0x108000;RX=0x1196000;FIRST=0x500000
def sha(b):return hashlib.sha256(b).hexdigest()
def replay(image,mode):
 desc=(ROOT/'analysis/r5_405_failure_readback_20261020_F/diagnostics_audit/nor_ldr.current.img').read_bytes()
 start,sectors=struct.unpack_from('<II',desc,0x140);load=struct.unpack_from('<I',desc,0x150)[0]
 assert(start,sectors,load)==(0x1000,0x8669,BASE)
 total=sectors*512;staged=image+b'\xff'*(total-len(image))
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x100000,0x1f00000);u.mem_map(0x03e42000,4096)
 u.mem_write(BASE,staged[:FIRST]);u.mem_write(0x03e42000,bytes([mode,1]));u.reg_write(UC_ARM_REG_SP,0x1f00000)
 maps=[];copies=[];waits=[];clears=[]
 def hook(cpu,at,_size,_arg):
  a=[cpu.reg_read(r)for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if at==0x108768:maps.append(a)
  elif at==0x108a04:copies.append(a[:3])
  elif at==0x10897c:waits.append(bytes(cpu.mem_read(0x03e42001,1))[0])
  elif at==0x108c54:clears.append(a[:2])
 u.hook_add(UC_HOOK_CODE,hook)
 u.emu_start(0x108398,0x10897c,count=100);assert u.reg_read(UC_ARM_REG_PC)==0x10897c
 u.emu_start(0x10897c,0x1086d4,count=1000)
 assert not copies and not maps and waits and set(waits)=={1}
 continuation=u.reg_read(UC_ARM_REG_PC)
 u.mem_write(BASE+FIRST,staged[FIRST:]);assert bytes(u.mem_read(BASE,total))==staged
 u.mem_write(0x03e42001,b'\0')
 u.emu_start(continuation,0x1086d4,count=1500000);assert u.reg_read(UC_ARM_REG_PC)==0x1086d4
 assert copies==[[0x108da0,0x128000,0x17c]] and clears==[[0x1197000,0x418]]
 regs=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,
       UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,
       UC_ARM_REG_R12,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_CPSR]
 state=[u.reg_read(r)for r in regs]
 table=struct.unpack('<I',u.mem_read(0x108f1c,4))[0];assert table==0x1a3c000
 def pte(va):
  l1=struct.unpack('<I',u.mem_read(table+(va>>20)*4,4))[0];assert l1&3==1
  return struct.unpack('<I',u.mem_read((l1&0xfffffc00)+((va>>12)&255)*4,4))[0]
 pages={hex(v):hex(pte(v))for v in [0x128000,0x1195000,RX,0x1197000,0x1a39000]}
 before=bytes(u.mem_read(RX,4096));end=0x1197000+struct.unpack_from('<I',image,0x2014c)[0]
 assert end in (0x1a39448,0x1a39468)
 # Dirty all primary-clear bytes and the exact tail boundary. Header-only
 # extensions must not pass by inheriting Unicorn's initial zero memory.
 u.mem_write(0x1197418,b'\xa5'*(end-0x1197418+16))
 u.reg_write(UC_ARM_REG_SP,0x1f00000);u.emu_start(0x5e3ee4,0x5e3f08,count=4000000)
 assert u.reg_read(UC_ARM_REG_PC)==0x5e3f08 and bytes(u.mem_read(RX,4096))==before
 assert bytes(u.mem_read(0x1197418,end-0x1197418))==bytes(end-0x1197418)
 assert bytes(u.mem_read(end,16))==b'\xa5'*16
 return dict(EXEC_MODE=mode,source_sha256=sha(image),read_bytes=hex(total),waiting_before_second_read=True,
  native_EXEC_MODE_and_handoff=True,native_memcpy_and_mapper=True,native_BSS_clear=True,
  no_cache_helper_substitution=True,maps=maps,continuation_state=state,page_descriptors=pages,
  RX_bytes_match_file=before==image[RX-BASE:RX-BASE+4096],RX_preserved_after_primary_clear=True,
  primary_clear_end=hex(end),new_BSS_state_cleared=bytes(u.mem_read(0x1a39448,32))==bytes(32),
  exact_after_end_guard_preserved=True)
def main():
 base=(ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin').read_bytes()
 cp=(OUT/'cp413-stage5c.bin').read_bytes();build=json.loads((OUT/'build.json').read_text())
 assert sha(cp)==build['candidate_sha256']
 rows=[]
 for mode in [0,1]:
  a,b=replay(base,mode),replay(cp,mode)
  assert a['continuation_state']==b['continuation_state']
  assert len(b['maps'])==len(a['maps'])+1
  assert b['maps'][-1]==[RX,4096,RX,15]
  assert all(x==y for i,(x,y)in enumerate(zip(a['maps'],b['maps']))if i not in (3,4))
  assert a['maps'][3]==[0x107f000,0x116070,0x107f000,12]
  assert b['maps'][3]==[0x107f000,0x118000,0x107f000,12]
  assert a['maps'][4]==[0x1197000,0x8a2448,0x1197000,12]
  assert b['maps'][4]==[0x1197000,0x8a2468,0x1197000,12]
  assert not a['new_BSS_state_cleared'] and b['new_BSS_state_cleared']
  assert a['page_descriptors']['0x1a39000']==b['page_descriptors']['0x1a39000']
  assert b['page_descriptors']['0x1196000']=='0x119663e'
  assert a['page_descriptors']['0x1195000']==b['page_descriptors']['0x1195000']=='0x119541f'
  rows.append(dict(mode=mode,baseline=a,candidate=b,registers_and_APSR_preserved=True,
   original_BSS_base_and_page_table_layout_unchanged=True,single_extra_RX_mapping=True,
   same_BSS_final_page=True,BSS_extension_bytes=32))
 report=dict(schema='r5-stage413-native-loader-two-stage-replay/1',camera_io=False,DAT_generated=False,
  baseline_sha256=sha(base),candidate_sha256=sha(cp),rows=rows,
  static_state_bytes=32,BSS_extension_bytes=32,extra_runtime_memcpy=False,
  source_read_descriptor='F /nor_ldr.img+140/+144/+150 unchanged native descriptor',
  limits=['Source-bound hardware reads represented by two host writes.','MMU activation/cache and hardware delivery not simulated.',
   'Alternative WBI/wake paths and actual device acceptance unverified.'])
 (OUT/'loader_replay.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(modes=2,registers_preserved=True,RX_exact=True,BSS_extension_bytes=32,exact_zero_guards=True,extra_runtime_memcpy=False)))
if __name__=='__main__':main()
