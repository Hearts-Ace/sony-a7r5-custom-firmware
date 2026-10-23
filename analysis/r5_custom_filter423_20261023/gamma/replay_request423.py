"""Final CP native aa7186 -> aa7eea -> Gamma table/math; bounded sibling ABIs."""
from pathlib import Path
import hashlib,json,struct,sys,itertools
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from verify_r5_m4strict_cp_cpu import new_cpu,SCRATCH,SP,STOP,w32
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
P=HERE.parent/'cp';meta=json.loads((P/'build.json').read_text());cp=(P/'cp423.NONINSTALLABLE.bin').read_bytes();sha=hashlib.sha256(cp).hexdigest();assert sha==meta['candidate_sha256'];sy={k:int(v,16)for k,v in meta['symbols'].items()}
BANK=0x3100000;CTX=BANK+28768;Q=0x3200000;G=0x1f6de00;Y=SCRATCH+0x6000;BASES=[0,3,2,1,16,15,19,20,17,18,5,13]
u=new_cpu(cp);u.mem_map(BANK,0x100000);u.mem_map(Q,0x10000);u.mem_write(0x1a39448,struct.pack('<2I',BANK,28768));state={'low':SP,'math':0,'native_consumer':0,'setup':None,'model':False}
modeled=(0x40ff24,0x40f93c,0xaaa4b2,0x40fe2c,0x40f854,0xaaa3c4,0xa9d7a0,0xaaa45a,0xa9dd70,0xaad642,0xab1242)
def ret(c):c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
def hook(c,at,size,_):
 state['low']=min(state['low'],c.reg_read(UC_ARM_REG_SP))
 if at==0x6069b0:state['math']+=1
 if at==0x413df0:state['native_consumer']+=1
 if at==0xaa7208:state['setup']=bytes(c.mem_read(c.reg_read(UC_ARM_REG_R6)+4,0x50))
 if state['model'] and at in modeled:ret(c)
 elif at==0x5f51bc:c.mem_write(c.reg_read(UC_ARM_REG_R0),bytes(c.mem_read(c.reg_read(UC_ARM_REG_R1),c.reg_read(UC_ARM_REG_R2))));ret(c)
 elif at==0x5f58b0:c.mem_write(c.reg_read(UC_ARM_REG_R0),bytes(c.reg_read(UC_ARM_REG_R1)));ret(c)
 elif at in (0x5ea594,0x5ea6d8):ret(c)
 elif at==0xb0de92:raise AssertionError(('native_logger',hex(c.reg_read(UC_ARM_REG_LR))))
u.hook_add(UC_HOOK_CODE,hook)
def call(at,args):
 for r,v in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):u.reg_write(r,v)
 u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,STOP|1);u.emu_start(at|1,STOP,count=30000000);assert u.reg_read(UC_ARM_REG_PC)==STOP and u.reg_read(UC_ARM_REG_SP)==SP
 return u.reg_read(UC_ARM_REG_R0)
w32(u,BANK,0x35424c44);w32(u,BANK+8,4095);w32(u,BANK+12,4095)
for n in range(12):
 u.mem_write(BANK+64+n*2392+656,struct.pack('<129I',*[x*(700+n*20)for x in range(129)]));w32(u,BANK+64+n*2392+1172,1)
assert call(sy['r5_native418_publish'],[BANK])==0
rows=[];state['model']=True
for selected,i,domain,direct in itertools.product((1,7,12),range(12),(0,1),(0,1)):
 w32(u,0x1a39458,BANK+50896+24*selected)
 request=Q+0xda8;u.mem_write(Q,bytes(0x10000));u.mem_write(G,bytes(0x3500));u.mem_write(request,bytes([domain,direct,0,0]));w32(u,request+0x78+0x10,BASES[i]);u.mem_write(request+0x78+8,b'\1');u.mem_write(request+0x78+0xb,b'\1');w32(u,request+0x78+0x34,3);u.mem_write(request+0xb4,bytes([1,direct,0,0]));u.mem_write(0x19d1309,bytes(32));u.mem_write(0x18d1c24,bytes(0x240));state.update(low=SP,math=0,native_consumer=0,setup=None)
 call(0xaa7186,[request]);setup=state['setup'];assert setup is not None
 gid=struct.unpack_from('<I',setup,0x30)[0];part=setup[0x38];assert gid==51+i*2+(not direct) and part==6,(selected,i,domain,direct,gid,part)
 aux=G+domain*0xa80+0x2174
 curve=bytes(u.mem_read(aux+0x24c,516));expected=struct.pack('<129I',*[x*(700+(selected-1)*20)for x in range(129)])
 assert curve==expected,(selected,i,domain,direct,curve[:20].hex())
 assert state['native_consumer']>0
 rows.append(dict(selected=selected,base=BASES[i],domain=domain,direct=direct,id=gid,part=part,curve_exact=True,math_calls=state['math'],stack_bytes=SP-state['low']))
report=dict(passed=True,CP_sha256=sha,checks=len(rows),rows=rows,camera_io=False,limits=['Native aa7186/aa7eea/Gamma math execute. Non-Gamma siblings and memcpy/memset/lock ABIs are explicit fixtures; no memory-read hooks used.','No physical frame, task scheduling, cache, ISP or JPEG pixel proof.'])
(HERE/'request423_replay.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(rows),'423 native full Gamma requests',sha)
