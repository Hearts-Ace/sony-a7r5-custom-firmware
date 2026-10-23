"""Actual original caller branch, installed gate, matrix consumer and interpolation.
No bypass of selected(), common publication or original downstream arithmetic.
"""
from pathlib import Path
import sys,struct,json,hashlib
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from verify_r5_m4strict_cp_cpu import new_cpu,SCRATCH,SP
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
meta=json.loads((OUT/'build.json').read_text());raw=(OUT/'cp420-grid.NONINSTALLABLE.bin').read_bytes();assert hashlib.sha256(raw).hexdigest()==meta['candidate_sha256']
sy={k:int(v,16)for k,v in meta['symbols'].items()};assert 'r5_native418_b13_gate'in sy
u=new_cpu(raw);BANK=SCRATCH+0x10000;u.mem_map(BANK,0x10000);W=SCRATCH+0x100;ST=SCRATCH+0x1000;CT=SCRATCH+0x2000;FRAME=SP-0x1000
w=lambda a,x:u.mem_write(a,struct.pack('<I',x));rows=[];hits=[];minimum=[FRAME]
def guard(c,access,at,n,v,z):
 assert FRAME-0x1000<=at<at+n<=FRAME+0x400,(hex(c.reg_read(UC_ARM_REG_PC)),hex(at),n)
 minimum[0]=min(minimum[0],c.reg_read(UC_ARM_REG_SP))
def hook(c,at,n,z):
 if at in (0x71d6f2,0x71d6f8,0x71d6d0,0x71e41e,sy['r5_native418_matrix']&~1,0x71eccc):hits.append(hex(at))
 if at in (0x71d6f2,0x71d6d0):
  assert c.reg_read(UC_ARM_REG_R0)==CT and c.reg_read(UC_ARM_REG_R3)==u.mem_read(CT+0x25,1)[0] and c.reg_read(UC_ARM_REG_R6)==W and c.reg_read(UC_ARM_REG_SP)==FRAME,(n,fault,hex(at),*[hex(c.reg_read(r))for r in (UC_ARM_REG_R0,UC_ARM_REG_R3,UC_ARM_REG_R6,UC_ARM_REG_SP)])
u.hook_add(UC_HOOK_MEM_WRITE,guard);u.hook_add(UC_HOOK_CODE,hook)
wires=[0,3,2,1,16,15,19,20,17,18,5,13];still=[0,6,2,1,42,41,54,55,43,44,53,53];movie=[21,27,23,22,46,45,56,57,47,48,53,53]
for n,profile,wire in [(n,p,wires[n])for n in range(12)for p in (still[n],movie[n])]:
 for fault in ('none','unimported','notready','scene','badcontext','received','unsealed'):
  u.mem_write(ST,bytes(0x400));u.mem_write(CT,bytes(0x400));u.mem_write(W,struct.pack('<2I',ST,CT));u.mem_write(ST+0x2e,bytes([wire]));u.mem_write(CT+0x25,bytes([profile]));u.mem_write(CT+0x1a0,struct.pack('<3H',1024,1100,900));w(0x1a39448,BANK);w(0x1a3944c,28768);mask=0 if fault=='unimported'else 1<<n
  u.mem_write(BANK,struct.pack('<4I',0x35424c53,7,mask,mask)+bytes(48));coef=[(i*3-300)&65535 for i in range(288)];u.mem_write(BANK+64+n*2392+80,struct.pack('<288H',*coef));w(BANK+28768+23012,0 if fault=='notready'else 0x4186a11)
  if fault=='scene':u.mem_write(ST+3,b'\x01')
  elif fault=='badcontext':u.mem_write(CT+0x25,b'\xff')
  elif fault=='received':w(BANK+12,0)
  elif fault=='unsealed':w(BANK,0)
  u.mem_write(FRAME-0x1000,bytes(0x1400));w(FRAME+4,256);w(FRAME+0xc,FRAME+0x29e);w(FRAME,FRAME+0x2b0);w(FRAME+0x24,W);w(FRAME+0x28,7)
  u.reg_write(UC_ARM_REG_R6,W);u.reg_write(UC_ARM_REG_R5,7);u.reg_write(UC_ARM_REG_R8,256);u.reg_write(UC_ARM_REG_R9,0xffff8000);u.reg_write(UC_ARM_REG_R10,0);u.reg_write(UC_ARM_REG_SP,FRAME);hits.clear();u.emu_start(0x71d68b,0x71d816,count=10000)
  assert u.reg_read(UC_ARM_REG_PC)==0x71d816 and u.reg_read(UC_ARM_REG_SP)==FRAME
  valid=fault=='none';ordinary=valid or profile!=53 or fault=='badcontext';assert ('0x71d6f8'in hits)==ordinary,(n,fault,hits)
  if valid:
   h=7;a,b,c,d,f,g=coef[h*6:h*6+6];out=[1024+a+b,-a,-b,-c,1100+c+d,-d,-f,-g,900+f+g];expect=struct.pack('<9H',*[x&65535 for x in out]);assert bytes(u.mem_read(FRAME+0x248,18))==expect,(n,fault)
  elif profile==53 and fault!='badcontext':assert bytes(u.mem_read(FRAME+0x248,18))==bytes.fromhex('000400000000000000040000000000000004')
  rows.append(dict(ordinal=n+1,profile=profile,fault=fault,ordinary_matrix=ordinary,custom_B13=valid,hits=list(hits)))
q=dict(passed=True,CP_sha256=meta['candidate_sha256'],cases=len(rows),rows=rows,camera_io=False,actual_original_caller_interpolation=True,valid_BW_SE_B13_consumed=True,invalid_BW_SE_native_identity=True,gate_preserves_live_regs_SP=True,bank_never_written=True,minimum_SP=hex(minimum[0]),limits=['BW/SE original native selector and blackwhite/sepia downstream semantics remain; arbitrary full-color behavior on BW/SE not claimed.','Not full camera scheduler or ISP execution.'])
(OUT/'native53_replay.json').write_text(json.dumps(q,indent=2)+'\n');print(json.dumps({k:v for k,v in q.items()if k!='rows'}))
