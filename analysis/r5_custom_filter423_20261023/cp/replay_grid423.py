"""Native wrapper/controller/packet/AA/MMIO using independent base/config axes."""
from pathlib import Path
import sys,json,hashlib,struct,itertools
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'analysis/r5_grid_restore422_20261023'),str(ROOT/'vendor/audit-python')]
import replay_handoff422 as original
from unicorn.arm_const import *
original.ALLOCATION=522152
cp=(HERE/'cp423.NONINSTALLABLE.bin').read_bytes();build=json.loads((HERE/'build.json').read_text());sha=hashlib.sha256(cp).hexdigest();assert sha==build['candidate_sha256']
sy={k:int(v,16)for k,v in build['symbols'].items()};raw=(ROOT/'exports/fl2_fl3_grid_compare_20261023/R5NATIVE.BIN').read_bytes()
class Harness(original.Harness):
 def call(self,entry,*args):
  u=self.u
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
  u.reg_write(UC_ARM_REG_SP,original.SP);u.reg_write(UC_ARM_REG_LR,original.STOP|1)
  u.emu_start(entry|1,original.STOP,count=30000000)
  assert u.reg_read(UC_ARM_REG_PC)==original.STOP,hex(u.reg_read(UC_ARM_REG_PC))
 def publish_fixture(self,at,grid=None,mask=4095):
  u=self.u;grid=self.grid if grid is None else grid
  u.mem_write(at,bytes(522152));original.w(u,at,0x35424c44,7,mask,mask)
  for i in range(12):
   value=bytearray(self.raw[132:2524]);value[:32]=('Config%02d'%(i+1)).encode().ljust(32,b'\0')
   value[1172:1176]=struct.pack('<I',1)
   value[1176:2391]=bytes((((int.from_bytes(grid[j:j+1],'little',signed=True)+i+64)%128)-64)&255 for j in range(1215))
   u.mem_write(at+64+2392*i,bytes(value))
  original.w(u,0x1a39448,at,28768);self.call(self.symbols['r5_native418_publish'],at)
  assert original.r32(u,at)==0x35424c53
  self.generation=at;self.grids[at]=grid;self.select(7)
 def select(self,n):
  original.w(self.u,0x1a39458,self.generation+50896+24*n)
  if n:self.grid=bytes(self.u.mem_read(self.generation+64+2392*(n-1)+1176,1215))
 def hook(self,c,pc,n,data):
  super().hook(c,pc,n,data)
  if pc==0x24273c and self.context:c.mem_write(self.context['root']+0x2e,bytes([self.case.get('base',19)]))
  if pc==0x230da8 and self.case.get('switch_selection') is not None:
   original.w(c,0x1a39458,self.generation+50896+24*self.case['switch_selection'])

e=Harness(cp,raw,'candidate',sy);rows=[]
routes=[dict(root1=1,direct=0,domain=6),dict(root1=0,direct=0,domain=6),dict(root1=1,direct=1,domain=6),dict(root1=1,direct=0,domain=11),dict(root1=1,direct=0,domain=8)]
for base,selected,copy in itertools.product((0,3,2,1,16,15,19,20,17,18,5,13),(1,7,12),(False,True)):
 e.select(selected);r=e.frame(dict(look='FL2',base=base,copy=copy));want=original.model.model(e.grid,e.order,8)
 assert r['bank_sha256']==original.sha(want) and r['final']['state_submit']==1 and int(r['final']['state_bank'],16)==e.generation+52360+(selected-1)*12960+7*1620
 assert all(x['enable']==1 for x in r['lanes']);rows.append(dict(base=base,selected=selected,copy=copy,enable=True,packed=True))
for route,root3,copy in itertools.product(routes,(0,1),(False,True)):
 e.select(7);a=e.frame(dict(look='FL2',base=3,copy=copy,root3=root3,**route));assert a['final']['state_submit']==1
 e.select(0);b=e.frame(dict(look='FL2',base=3,copy=copy,root3=root3,**route));want=original.model.model(original.NATIVE_RAW,e.order,8)
 assert b['bank_sha256']==original.sha(want) and b['final']['state_submit']==1
 assert int(b['final']['state_bank'],16)>=e.generation+207888
 rows.append(dict(base=3,selected0_restore=True,route=route,root3=root3,copy=copy))
# Capture the old selected configuration before native controller; delayed
# handoff may not use a new global selection, and the next request must.
for old,new in ((1,12),(12,0),(7,1)):
 e.select(old);oldgrid=e.grid;r=e.frame(dict(look='FL2',base=0,switch_selection=new))
 assert r['bank_sha256']==original.sha(original.model.model(oldgrid,e.order,8))
 e.select(new);n=e.frame(dict(look='FL2',base=0))
 expected=original.model.model(original.NATIVE_RAW if not new else e.grid,e.order,8)
 assert n['bank_sha256']==original.sha(expected);rows.append(dict(captured=old,new_global=new,old_source_kept=True,next_request_updated=True))
report=dict(passed=True,CP_sha256=sha,checks=len(rows),rows=rows,camera_io=False,native_wrapper_controller_packet_AA_double_lane=True,all12_base_profiles_three_independent_configs=True,limits=['Original constructor context/owner wiring and unrelated sibling functions remain explicit fixtures from frozen422 harness. Selection pointer is installed as a fixture; SELECT protocol is exercised separately.','No physical ISP pixel output, task concurrency, cache or actual SD JPEG evidence.'])
(HERE/'grid423_replay.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(rows),'423 native grid paths',sha)
