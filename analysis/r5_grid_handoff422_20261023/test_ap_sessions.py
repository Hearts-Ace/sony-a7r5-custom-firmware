"""Actual AArch64 session, power hook and immutable name publication. Offline."""
from pathlib import Path
import sys,json,struct,hashlib
OUT=Path(__file__).resolve().parent
sys.path.insert(0,'/private/tmp/r5-grid419-deps')
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn import arm64_const as R
a=json.loads((OUT/'import/module_audit.json').read_text());code=(OUT/'import/runtime_rx.bin').read_bytes()
RAM=0x20000000;SP=RAM+0x100000;STOP=RAM+0x1ff000;SLEEP=0x32000000
G=[getattr(R,'UC_ARM64_REG_X'+str(i))for i in range(29)]+[R.UC_ARM64_REG_FP,R.UC_ARM64_REG_LR]
Q=[getattr(R,'UC_ARM64_REG_Q'+str(i))for i in range(32)]
rows=[]
for bias in (0,0x40000000):
 u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);u.mem_map(a['rx']+bias,0x10000);u.mem_write(a['rx']+bias,code)
 u.mem_map(a['rw']+bias,0x20000);u.mem_map(RAM,0x200000);u.mem_map(SLEEP,0x1000)
 sy={n:v+bias for n,v in a['symbols'].items()};u.mem_map(0x16da000+bias,0x2000)
 endpoint=[STOP];sleeps=[0]
 def ret(v):u.reg_write(R.UC_ARM64_REG_X0,v);u.reg_write(R.UC_ARM64_REG_PC,u.reg_read(R.UC_ARM64_REG_LR))
 def hook(cpu,pc,n,arg):
  if pc==sy['r5_stage411_dlsym']:
   ptr=cpu.reg_read(R.UC_ARM64_REG_X1);assert bytes(cpu.mem_read(ptr,10))==b'nanosleep\0';ret(SLEEP)
  elif pc==SLEEP:sleeps[0]+=1;ret(0)
 u.hook_add(UC_HOOK_CODE,hook,begin=sy['r5_stage411_dlsym'],end=sy['r5_stage411_dlsym']);u.hook_add(UC_HOOK_CODE,hook,begin=SLEEP,end=SLEEP)
 def call(name,*args):
  for i,r in enumerate(G):u.reg_write(r,0x12340000+i)
  u.reg_write(R.UC_ARM64_REG_SP,SP);u.reg_write(R.UC_ARM64_REG_LR,STOP)
  for i,v in enumerate(args):u.reg_write(G[i],v)
  before=[u.reg_read(r)for r in G]
  u.emu_start(sy[name],STOP,count=1000000)
  assert u.reg_read(R.UC_ARM64_REG_PC)==STOP,name
  assert u.reg_read(R.UC_ARM64_REG_SP)==SP
  assert [u.reg_read(r)for r in G[19:30]]==before[19:30]
  return u.reg_read(G[0])
 def power(event):u.mem_write(RAM,struct.pack('<I',event));call('r5_stage421_power',RAM)
 call('r5_session_cold');assert call('r5_session_prepare')==1 and call('r5_session_current')==1
 assert call('r5_session_new_transfer')==1;first=call('r5_session_token',123)
 assert call('r5_session_admit')==1
 power(0x920143);assert call('r5_session_current')==0 and call('r5_session_admit')==0
 power(0x92015a);assert call('r5_session_prepare')==0
 call('r5_session_leave');assert call('r5_session_prepare')==1
 assert call('r5_session_new_transfer')==1 and call('r5_session_token',123)!=first
 assert call('r5_session_epoch')==2
 for i in range(20):
  call('r5_session_finish');power(0x920143);power(0x92015a)
  assert call('r5_session_prepare')==1 and call('r5_session_new_transfer')==1
 # Power hook preserves the incoming machine state and replays native prologue.
 u.mem_map(0x35b2000+bias,0x2000);u.mem_write(RAM,struct.pack('<I',0x92015a))
 for i,r in enumerate(G):u.reg_write(r,0x1234567800000000+i)
 for i,r in enumerate(Q):u.reg_write(r,0x123456789abcdef00000000000000000+i)
 u.reg_write(G[0],RAM);u.reg_write(R.UC_ARM64_REG_SP,SP)
 u.reg_write(R.UC_ARM64_REG_NZCV,0xa0000000);u.reg_write(R.UC_ARM64_REG_FPCR,0x400000);u.reg_write(R.UC_ARM64_REG_FPSR,0x8000000)
 before=[u.reg_read(r)for r in G];qs=[u.reg_read(r)for r in Q]
 u.emu_start(sy['r5_stage411_power_hook'],0x35b2a7c+bias,count=100000)
 assert [u.reg_read(r)for r in G]==before and [u.reg_read(r)for r in Q]==qs
 assert u.reg_read(R.UC_ARM64_REG_SP)==SP-80
 assert bytes(u.mem_read(SP-80,16))==struct.pack('<QQ',before[29],before[30])
 assert u.reg_read(R.UC_ARM64_REG_NZCV)==0xa0000000 and u.reg_read(R.UC_ARM64_REG_FPCR)==0x400000 and u.reg_read(R.UC_ARM64_REG_FPSR)==0x8000000
 # Simulate successful matching ACK; name publication uses an immutable copy.
 state=sy['r5_stage413_transfer_state'];SET=RAM+0x10000
 u.mem_write(SET,bytes(28708));u.mem_write(state+16,struct.pack('<I',1));u.mem_write(state+32,struct.pack('<Q',SET));u.mem_write(state+44,struct.pack('<I',1))
 pointers=[]
 for i in range(16):
  name=('generation-%d'%i).encode()+b'\0';u.mem_write(SET+4,name.ljust(32,b'\0'))
  assert call('r5_stage421_parameters_ready')==1;p=call('r5_native12_name',1);pointers.append((p,name))
  assert call('r5_stage421_parameters_ready')==1 # reuse consumes no slot
 for p,n in pointers:assert bytes(u.mem_read(p,len(n)))==n
 u.mem_write(SET+4,b'overflow\0');assert call('r5_stage421_parameters_ready')==0xffffffff
 assert call('r5_native12_name',1)==0
 u.mem_write(state+44,bytes(4));assert call('r5_stage421_parameters_ready')==1 and call('r5_native12_name',1)==0
 rows.append(dict(bias=hex(bias),resume_cycles=21,reader_drain_checked=True,power_hook_GPR_SIMD_flags_preserved=True,name_generations=16,clear_at_limit=True))
r=dict(passed=True,camera_io=False,module_sha256=hashlib.sha256(code).hexdigest(),rows=rows,limits=['Sequential synthetic event scheduling with a held ACK reader; no device power/scheduler timing proof.','Native callback continuation is a boundary; real resume dispatch and hardware cache refresh unverified.'])
(OUT/'ap_session_replay.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
