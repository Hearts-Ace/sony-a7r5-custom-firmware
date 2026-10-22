"""Final CP native aa7186 -> aa7eea -> Gamma table/math; bounded sibling ABIs."""
from pathlib import Path
import hashlib,json,struct,sys,itertools
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from verify_r5_m4strict_cp_cpu import new_cpu,SCRATCH,SP,STOP,w32
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
P=HERE.parent/'cp';meta=json.loads((P/'build.json').read_text());cp=(P/'cp420-grid.NONINSTALLABLE.bin').read_bytes();sha=hashlib.sha256(cp).hexdigest();assert sha==meta['candidate_sha256'];sy={k:int(v,16)for k,v in meta['symbols'].items()}
BANK=0x3100000;CTX=BANK+28768;Q=0x3200000;G=0x1f6de00;Y=SCRATCH+0x6000;BASES=[0,3,2,1,16,15,19,20,17,18,5,13]
u=new_cpu(cp);u.mem_map(BANK,0x10000);u.mem_map(Q,0x10000);u.mem_write(0x1a39448,struct.pack('<2I',BANK,28768));state={'low':SP,'math':0,'native_consumer':0,'setup':None,'model':False}
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
 u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,STOP|1);u.emu_start(at|1,STOP,count=1000000);assert u.reg_read(UC_ARM_REG_PC)==STOP and u.reg_read(UC_ARM_REG_SP)==SP
 return u.reg_read(UC_ARM_REG_R0)
assert call(sy['r5_native_gamma418_begin'],[CTX])==0
for i in range(12):
 u.mem_write(Y,struct.pack('<129I',*[x*(800+i*5)for x in range(129)]));assert call(sy['r5_native_gamma418_put'],[CTX,i+1,Y])==0
assert call(sy['r5_native_gamma418_seal'],[CTX])==0
rows=[];state['model']=True
for i,domain,direct in itertools.product(range(12),(0,1),(0,1)):
 request=Q+0xda8;u.mem_write(Q,bytes(0x10000));u.mem_write(G,bytes(0x3500));u.mem_write(request,bytes([domain,direct,0,0]));w32(u,request+0x78+0x10,BASES[i]);u.mem_write(request+0x78+8,b'\1');u.mem_write(request+0x78+0xb,b'\1');w32(u,request+0x78+0x34,3);u.mem_write(request+0xb4,bytes([1,direct,0,0]));u.mem_write(0x19d1309,bytes(32));u.mem_write(0x18d1c24,bytes(0x240));state.update(low=SP,math=0,native_consumer=0,setup=None)
 call(0xaa7186,[request]);setup=state['setup'];assert setup is not None
 id=struct.unpack_from('<I',setup,0x30)[0];part=setup[0x38];assert id==51+i*2+(not direct) and part==6,(i,domain,direct,id,part)
 aux=G+domain*0xa80+0x2174
 curve=bytes(u.mem_read(aux+0x24c,516));expected=struct.pack('<129I',*[x*(800+i*5)for x in range(129)])
 assert curve==expected,(i,domain,direct,curve[:20].hex())
 assert state['native_consumer']>0
 rows.append(dict(native_consumer_calls=state['native_consumer'],index=i+1,base=BASES[i],domain=domain,direct=direct,selected_id=id,partition=part,math_calls=state['math'],stack_bytes=SP-state['low'],curve129_exact=True))
report=dict(schema='r5-final-native-gamma-request/1',passed=True,CP_sha256=sha,checks=len(rows),rows=rows,camera_io=False,installable=False,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),limits=['Native aa7186/aa7eea/Gamma math execute. Non-Gamma sibling functions and memory/lock ABIs use explicit fixtures.','Normal transform1/diagnostic-off only; native413df0 consumer executes, its direct ordinate path does not call6069b0 interpolation; diagnostic math separately covered by standalone651 cases.','No camera, real task scheduling/stack margin or actual preview/JPEG hardware.'])
(HERE/'final_request_replay.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(rows),'full native Gamma setup/math finalCP',sha)
