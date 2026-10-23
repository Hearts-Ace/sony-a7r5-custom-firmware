"""Installed selection seam -> original builder -> uploader in synthetic RAM.
No camera access. Scheduler/controller reachability outside the seam is unknown.
"""
from pathlib import Path
import sys,json,struct,hashlib,random
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'research/r5_custom_lut/scripts'),'/tmp/r5-grid419-deps']
import replay_correction_builder as base
from unicorn.arm_const import *
from unicorn import UC_HOOK_CODE
raw=(OUT/'cp420-grid.NONINSTALLABLE.bin').read_bytes();meta=json.loads((OUT/'build.json').read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(raw)==meta['candidate_sha256']
BANK=0x32000000;WRAPPER=0x32010000;NATIVECTX=0x32011000
WIRES=[0,3,2,1,16,15,19,20,17,18,5,13];PROFILES=[0,6,2,1,42,41,54,55,43,44,53,53]
rng=random.Random(419);rows=[]
for slot in range(12):
 for pattern in ('zero','min','max','random'):
  engine=base.Replay('r5');u=engine.uc;u.mem_write(base.BASE,raw);u.mem_map(BANK,0x14000);u.mem_map(0x1a39000,0x1000)
  u.mem_write(BANK,struct.pack('<4I',0x35424c53,7,4095,4095)+bytes(48))
  p=bytes([0 if pattern=='zero' else 192 if pattern=='min' else 63 if pattern=='max' else rng.randrange(-64,64)&255 for _ in range(1215)])
  value=BANK+64+slot*2392
  base.w(u,value+1172,1);u.mem_write(value+1176,p)
  base.w(u,0x1a39448,BANK,28768);base.w(u,BANK+28768+23012,0x4186a11)
  base.w(u,base.CTX,base.PARAM,NATIVECTX);u.mem_write(base.PARAM+0x2e,bytes([WIRES[slot]]));u.mem_write(NATIVECTX+0x25,bytes([PROFILES[slot]]))
  base.w(u,base.OUT+8,base.STATE,base.WORK,base.META);base.w(u,base.WORK+0x6b0,base.BANK)
  u.mem_write(base.META+0xb,bytes([slot%3]));u.mem_write(base.PARAM+0x2f,b'\x08')
  # Actual installed B.W, replacement gate and original IT/STR tail.
  original=[0,0,0,0xabcdef01]
  for reg,v in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],original):u.reg_write(reg,v)
  for reg,v in [(UC_ARM_REG_R4,0),(UC_ARM_REG_R5,base.STATE),(UC_ARM_REG_R8,base.OUT),(UC_ARM_REG_R9,base.CTX),(UC_ARM_REG_SP,base.SP),(UC_ARM_REG_LR,base.STOP|1)]:u.reg_write(reg,v)
  u.emu_start(0x230ee1,0x230ef2,count=2000)
  assert u.reg_read(UC_ARM_REG_SP)==base.SP
  assert u.reg_read(UC_ARM_REG_R3)==original[3] and u.reg_read(UC_ARM_REG_R4)==u.mem_read(base.PARAM+1,1)[0]
  assert bytes(u.mem_read(base.STATE+0x184,6))==struct.pack('<IBB',value+1176,1,2)
  u.mem_write(base.BANK-16,b'\xa5'*16);u.mem_write(base.BANK+4860,b'\x5a'*16)
  engine.call(0x231654,base.CTX,base.OUT)
  packed=bytes(u.mem_read(base.BANK+slot%3*1620,1620));expected=base.model(p,engine.order,8)
  assert packed==expected and bytes(u.mem_read(value+1176,1215))==p
  base.w(u,base.SP,0,0);base.w(u,base.DEV+0x184,base.MMIO);u.mem_write(base.STATE+0x18,b'\x01');base.w(u,base.STATE+0x14,base.BANK+slot%3*1620)
  engine.call(0x414f44,base.DEV,base.DEV,base.CONTROL,base.STATE)
  actual=b''.join(bytes(u.mem_read(base.MMIO+at,n))for at,n in base.CHUNKS)
  assert actual==expected,(slot,pattern,[(i,a,b)for i,(a,b) in enumerate(zip(actual,expected))if a!=b][:8],engine.calls)
  assert bytes(u.mem_read(base.BANK-16,16))==b'\xa5'*16 and bytes(u.mem_read(base.BANK+4860,16))==b'\x5a'*16
  assert struct.unpack('<3I',bytes(u.mem_read(BANK+52252,12)))==(1<<slot,1<<slot,1<<slot)
  rows.append(dict(slot=slot+1,pattern=pattern,bank=slot%3,payload_sha256=sha(p),packed_sha256=sha(packed)))
# Disabled/mismatched/unsealed/import-not-ready are original table selection.
for fault in ('disabled','not-ready','wrong-profile','foreign-mode','not-sealed','missing-slot','special-transform','bank3'):
 engine=base.Replay('r5');u=engine.uc;u.mem_write(base.BASE,raw);u.mem_map(BANK,0x14000);u.mem_map(0x1a39000,0x1000)
 base.w(u,BANK,0x35424c53,7,1,1);base.w(u,0x1a39448,BANK,28768);base.w(u,BANK+28768+23012,0x4186a11)
 base.w(u,BANK+64+1172,1);base.w(u,base.CTX,base.PARAM,NATIVECTX);base.w(u,base.OUT+8,base.STATE,base.WORK,base.META)
 if fault=='disabled':base.w(u,BANK+64+1172,0)
 if fault=='not-ready':base.w(u,BANK+28768+23012,0)
 if fault=='wrong-profile':u.mem_write(NATIVECTX+0x25,b'\x07')
 if fault=='foreign-mode':u.mem_write(base.PARAM+3,b'\x01')
 if fault=='not-sealed':base.w(u,BANK,0)
 if fault=='missing-slot':base.w(u,BANK+8,2);base.w(u,BANK+12,2)
 if fault=='special-transform':u.mem_write(base.PARAM+0x36,b'\x01')
 if fault=='bank3':u.mem_write(base.META+0xb,b'\x03')
 sy={k:int(v,16)for k,v in meta['symbols'].items()}
 engine.call(sy['r5_native419_grid'],base.CTX,base.OUT);assert u.reg_read(UC_ARM_REG_R0)==0,fault
report=dict(passed=True,CP_sha256=sha(raw),camera_io=False,cases=len(rows),fallback_cases=8,rows=rows,
 limits=['Actual installed selection seam, original table packing and uploader execute; surrounding native controller eligibility/validator and asynchronous ISP consumption are not full-device verified.','MMIO is synthetic; no actual pixel effect, camera boot, persistence or Edit support is proved.'])
(OUT/'grid_replay.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='rows'}))
