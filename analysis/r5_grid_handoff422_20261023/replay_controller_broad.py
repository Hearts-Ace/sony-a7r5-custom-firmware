"""Bounded complete R5 grid controller schedules in synthetic RAM."""
from pathlib import Path
import sys,json,struct,hashlib,itertools
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path[:0]=['/private/tmp/r5-grid419-deps',str(ROOT/'research/r5_custom_lut/scripts')]
import numpy,unicorn,capstone
import replay_correction_builder as b
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_INVALID
from unicorn.arm_const import *
CP=OUT/'cp/cp420-grid.NONINSTALLABLE.bin'
image=CP.read_bytes();BANK=0x32000000;CACHE=0x3000b000
rows=[]
for slot,(flag,direct),domain in itertools.product(range(12),[(0,0),(1,0),(1,1)],[0,8,11]):
 base=[0,3,2,1,16,15,19,20,17,18,5,13][slot]
 profile=[0,6,2,1,42,41,54,55,43,44,53,53][slot]
 e=b.Replay('r5');u=e.uc;u.mem_write(b.BASE,image);u.mem_map(0x16a0000,0x20000);u.mem_map(BANK,0x14000);u.mem_map(0x1a39000,0x1000)
 b.w(u,BANK,0x35424c53,7,1<<slot,1<<slot);b.w(u,BANK+64+2392*slot+1172,1);p=bytes([7])*405+bytes([253])*405+bytes([11])*405;u.mem_write(BANK+64+2392*slot+1176,p)
 b.w(u,0x1a39448,BANK,28768);b.w(u,BANK+28768+23012,0x4186a11)
 b.w(u,b.CTX,b.PARAM,b.ENV);u.mem_write(b.PARAM+1,bytes([flag]));u.mem_write(b.PARAM+0x2f,b'\x08');u.mem_write(b.PARAM+0x2e,bytes([base]));u.mem_write(b.ENV+0x25,bytes([profile]));u.mem_write(b.ENV+6,bytes([direct]));u.mem_write(b.ENV+0xc,bytes([domain]));u.mem_write(b.STATE+4,b'\xff')
 b.w(u,b.OUT+4,0x30003800,b.STATE,b.WORK,b.META,CACHE);b.w(u,b.WORK+0x6b0,b.BANK);b.w(u,b.PARAM+0x1f4,b.DEV);b.w(u,b.PARAM+0x1fc,b.DEV);b.w(u,b.PARAM+0x1ec,b.DEV);b.w(u,b.DEV+0x184,b.MMIO)
 count={'builder':0,'uploader':0};bad=[];checks=[]
 def trace(cpu,at,size,_):
  if at==0x231654:count['builder']+=1
  if at in (0x231296,0x2312c2,0x2315c0):checks.append(dict(at=hex(at),r0=cpu.reg_read(UC_ARM_REG_R0),r5=cpu.reg_read(UC_ARM_REG_R5)))
  if at==0x757068:count['uploader']+=1
 def invalid(cpu,access,addr,size,value,_):
  bad.append(hex(addr));return False
 u.hook_add(UC_HOOK_CODE,trace);u.hook_add(UC_HOOK_MEM_INVALID,invalid)
 steps=[]
 try:
  for frame in range(6):
   e.call(0x230da8,b.CTX,b.OUT)
   enabled=u.mem_read(b.STATE+0x18,1)[0];dirty=u.mem_read(b.STATE+0x24,1)[0];ptr=struct.unpack('<I',u.mem_read(b.STATE+0x20,4))[0]
   if frame>0:
    b.w(u,b.DEV+0x184,b.MMIO);b.w(u,b.SP,0,0);e.call(0x414f44,b.DEV,b.DEV,b.CONTROL,b.STATE+0xc)
   expected=b.model(p,e.order,8);seen=b''.join(bytes(u.mem_read(b.MMIO+at,n))for at,n in b.CHUNKS)
   steps.append(dict(frame=frame,submitted=frame>0,enabled=enabled,dirty=dirty,pointer=hex(ptr),bytes_match=seen==expected,counts=dict(count),selected_pointer=hex(struct.unpack('<I',u.mem_read(b.STATE+0x184,4))[0]),diag=list(struct.unpack('<8I',u.mem_read(BANK+52252,32)))))
  rows.append(dict(slot=slot+1,domain=domain,flag=flag,direct=direct,meta_index=u.mem_read(b.META+11,1)[0],steps=steps,checks=checks))
 except Exception as err:rows.append(dict(slot=slot+1,domain=domain,flag=flag,direct=direct,error=str(err),pc=hex(u.reg_read(UC_ARM_REG_PC)),invalid=bad,steps=steps))
for row in rows:
 assert 'error' not in row,row
 first=row['steps'][0]
 if row['meta_index']==3 and not row['direct']:
  assert all(z['counts']['builder']==0 and z['pointer']=='0x0' for z in row['steps']),row
  row['expected_native_ineligible_index3']=True;continue
 assert first['counts']['builder']==1 and first['dirty']==1,row
 assert all(z['bytes_match'] for z in row['steps'][1:]),row
r=dict(passed=True,looks=12,domains=[0,8,11],cases=len(rows),initial_upload_intentionally_omitted=True,source_cp_sha256=hashlib.sha256(image).hexdigest(),camera_io=False,rows=rows,limits=['Synthetic root/global/device contexts; no actual camera mode labels or hardware scheduling.','No actual mode names or concurrent consumer scheduling coverage.','First frame is deliberately not submitted; this is a controlled failure trigger, not an observation of real camera scheduling.'])
(OUT/'r5_controller_broad_replay.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items()if k!='rows'}))
