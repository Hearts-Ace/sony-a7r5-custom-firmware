"""Exact404 native table overwrite unit tests. No camera, loader or DAT."""
from pathlib import Path
import hashlib,json,struct,sys,itertools
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools'),str(ROOT/'research/r5_custom_lut/scripts'),str(HERE)]
from replay_gamma_owned_consumers import link
from verify_r5_m4strict_cp_cpu import new_cpu,SCRATCH,SP,STOP,w32
from patch_native_gamma import patches,SHA,initial_context
from getter_gates import build as build_gates
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
CP=ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin'
CTX=0x3104000;SIZE=23484;RX=0x1a3c000;AUX=SCRATCH+0x1000;WRAP=SCRATCH+0x3000;DST=SCRATCH+0x4000;Y=SCRATCH+0x6000
BASES=[0,3,2,1,16,15,19,20,17,18,5,13]
NAMES=['ST','PT','NT','VV','VV2','FL','FL2','FL3','IN','SH','BW','SE']
def main():
 out=HERE/('replay'+('_'+sys.argv[1]if len(sys.argv)>1 else''));out.mkdir(exist_ok=False)
 cp=CP.read_bytes();assert hashlib.sha256(cp).hexdigest()==SHA
 obj=HERE/'native_gamma.o';code,sy=link([obj],base=RX);gates=build_gates(out/'getter',CTX);pp=gates['patches']
 modified=bytearray(cp)
 for p in pp:modified[p['offset']:p['offset']+len(bytes.fromhex(p['after']))]=bytes.fromhex(p['after'])
 us=[new_cpu(cp),new_cpu(bytes(modified))];state={'checking':False,'min_sp':SP,'math':0,'logs':0};cases=[]
 for u in us:
  u.mem_map(0x3100000,0x10000);u.mem_write(0x1a39448,struct.pack('<2I',CTX-14128,14128))
  u.mem_write(RX,code)
 us[1].mem_write(int(gates['RX'],16),(out/'getter/gates.bin').read_bytes())
 for u in us:
  def hook(c,at,n,_):
   state['min_sp']=min(state['min_sp'],c.reg_read(UC_ARM_REG_SP))
   if at==0x6069b0:state['math']+=1
   if at==0xb0de92:state['logs']+=1;c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
   elif at==0x5f51bc:c.mem_write(c.reg_read(UC_ARM_REG_R0),bytes(c.mem_read(c.reg_read(UC_ARM_REG_R1),c.reg_read(UC_ARM_REG_R2))));c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
   elif at==0x5f58b0:c.mem_write(c.reg_read(UC_ARM_REG_R0),bytes(c.reg_read(UC_ARM_REG_R1)));c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
  def write(c,access,address,n,value,_):
   if state['checking']:
    assert CTX<=address and address+n<=CTX+SIZE or SP-0x1000<=address and address+n<=SP,('private builder write outside context/stack',hex(address),n)
  u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_MEM_WRITE,write)
 def call(u,entry,args):
  for r in range(UC_ARM_REG_R0,UC_ARM_REG_R3+1):u.reg_write(r,0)
  for r,v in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):u.reg_write(r,v)
  saved=[0x55550000+i for i in range(8)]
  for r,v in zip(range(UC_ARM_REG_R4,UC_ARM_REG_R11+1),saved):u.reg_write(r,v)
  u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,STOP|1);state['min_sp']=SP;state['logs']=0
  u.emu_start(entry|1,STOP,count=1000000)
  assert u.reg_read(UC_ARM_REG_PC)==STOP and u.reg_read(UC_ARM_REG_SP)==SP
  assert [u.reg_read(r)for r in range(UC_ARM_REG_R4,UC_ARM_REG_R11+1)]==saved
  return u.reg_read(UC_ARM_REG_R0),SP-state['min_sp']
 u=us[1];initial=initial_context(cp,CTX);u.mem_write(CTX,initial);state['checking']=True
 assert call(u,sy['r5_native_gamma418_begin'],[CTX])[0]==0;state['checking']=False
 initialized=bytes(u.mem_read(CTX,SIZE));table=initialized[:75*28];route=initialized[75*28:75*28+176]
 assert table[:51*28]==cp[0x107e968-0x108000:0x107e968-0x108000+51*28]
 original_route=cp[0x107eefc-0x108000:0x107eefc-0x108000+176]
 ids=[]
 for i,b in enumerate(BASES):
  old=struct.unpack_from('<2I',original_route,b*8);new=(51+2*i,52+2*i);assert struct.unpack_from('<2I',route,b*8)==old
  ptrs=[struct.unpack_from('<I',cp,0x107e968-0x108000+(old[0]*7+j)*4)[0]for j in [0,6]]+[struct.unpack_from('<I',cp,0x107e968-0x108000+(old[1]*7+6)*4)[0]]
  for k,p in enumerate(ptrs):assert initialized[2276+(i*3+k)*576:2276+(i*3+k+1)*576]==cp[p-0x108000:p-0x108000+576]
  ids.append(dict(index=i+1,name=NAMES[i],base=b,old_ids=old,new_ids=new,native_record_VAs=[hex(p)for p in ptrs]))
 assert route==original_route and initialized[:23012]==initial[:23012] and initialized[23020:]==initial[23020:]
 w32(u,CTX+23012,0x4186a11)
 # Native public partition5 availability function: old0..50 unchanged; new
 # still rows retain valid partitions0..5, new second-column rows stay null.
 for id in range(81):
  if id<51:
   ref=call(us[0],0xaa8a68,[id])[0];got=call(us[1],0xaa8a68,[id])[0];assert ref==got
  else:
   got=call(us[1],0xaa8a68,[id])[0];assert got==int(id<75 and (id-51)%2==0)
  cases.append(dict(kind='native_availability',id=id,result=got))
 def prep(m,id,part,domain,adjust,transform):
  m.mem_write(AUX,b'\xa5'*0x500);m.mem_write(DST,b'\xa5'*0x80);m.mem_write(WRAP,bytes(0x80));w32(m,WRAP+0x30,id)
  m.mem_write(WRAP+0x38,bytes([part,adjust[0],adjust[1]]));m.mem_write(WRAP+0x4d,bytes([transform]))
  m.mem_write(0x19d1309,bytes(32));m.mem_write(0x18d1c24,bytes(0x240));m.mem_write(0x19864fc,b'\0')
  call(m,0x413df0,[domain,WRAP,AUX,DST]);return bytes(m.mem_read(AUX,0x500)),bytes(m.mem_read(DST,0x80)),bytes(m.mem_read(0x1f69eac,2))
 # All three per-look native records; source table and target table share all
 # unchanged tail bytes, not just a synthetic reference metadata template.
 # Model sealed mode for direct appended-ID math tests. Native routes remain
 # the original22rows, so ordinary consumers still select original IDs.
 w32(u,CTX+23012,0x4186a11)
 for i,k,domain,adjust,transform in itertools.product(range(12),range(3),(0,1),((0,0),(2,3),(254,253)),(0,1)):
  old=ids[i]['old_ids'][int(k==2)];new=ids[i]['new_ids'][int(k==2)];part=0 if k==0 else 6
  ref=prep(us[0],old,part,domain,adjust,transform);got=prep(us[1],new,part,domain,adjust,transform)
  assert struct.unpack_from('<I',ref[0],0x10)[0]==old and struct.unpack_from('<I',got[0],0x10)[0]==new
  assert struct.unpack_from('<I',ref[1],0x18)[0]==old and struct.unpack_from('<I',got[1],0x18)[0]==new
  ref0=bytearray(ref[0]);got0=bytearray(got[0]);ref1=bytearray(ref[1]);got1=bytearray(got[1])
  ref0[0x10:0x14]=got0[0x10:0x14]=bytes(4);ref1[0x18:0x1c]=got1[0x18:0x1c]=bytes(4)
  assert (ref0,ref1,ref[2])==(got0,got1,got[2]),(NAMES[i],k,domain,adjust,transform)
  cases.append(dict(kind='native_equal_except_intentional_ID',index=i+1,variant=k,domain=domain,adjust=adjust,transform=transform))
 # Actual original route instruction fragment, all22bases/two columns.
 for b,column in itertools.product(range(22),(0,1)):
  w32(u,DST,b);u.reg_write(UC_ARM_REG_R3,b);u.reg_write(UC_ARM_REG_R4,WRAP);u.reg_write(UC_ARM_REG_R5,DST);u.reg_write(UC_ARM_REG_R11,column)
  u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,STOP|1);u.emu_start(0xaa8305,0xaa8338,count=100)
  expected=struct.unpack_from('<2I',route,b*8)
  assert tuple(struct.unpack('<I',u.mem_read(WRAP+p,4))[0]for p in [0x30,0x40,0x34])==(expected[column],expected[column],expected[0]);cases.append(dict(kind='native_route',base=b,column=column))
 w32(u,CTX+23012,0x4186b11)
 # All twelve independent records are overwritten privately before seal.
 for i in range(12):
  curve=struct.pack('<129I',*[x*(900+i*5)for x in range(129)]);u.mem_write(Y,curve);before=bytes(u.mem_read(CTX,SIZE));state['checking']=True
  assert call(u,sy['r5_native_gamma418_put'],[CTX,i+1,Y])[0]==0;state['checking']=False;after=bytes(u.mem_read(CTX,SIZE))
  allowed=set(range(23016,23020))
  for k in range(3):
   at=2276+(i*3+k)*576;allowed.update(range(at,at+516));assert after[at:at+516]==curve
   assert after[at+516:at+576]==initialized[at+516:at+576]
  assert all(a==b or j in allowed for j,(a,b)in enumerate(zip(before,after)))
  for k,domain in itertools.product(range(3),(0,1)):
   new=ids[i]['new_ids'][int(k==2)];part=0 if k==0 else 6
   w32(u,CTX+23012,0x4186a11);got=prep(u,new,part,domain,(0,0),1);w32(u,CTX+23012,0x4186b11)
   assert got[0][0x24c:0x24c+516]==curve,(i,k,domain)
   u.mem_write(Y,b'\xa5'*516);assert bytes(u.mem_read(AUX+0x24c,516))==curve
   cases.append(dict(kind='custom_owned129',index=i+1,variant=k,domain=domain))
 for fault in ['index0','index13','first_nonzero','descending','overrange','overlap','unaligned']:
  u.mem_write(Y,struct.pack('<129I',*[x*900 for x in range(129)]));n=1;y=Y
  if fault=='index0':n=0
  elif fault=='index13':n=13
  elif fault=='first_nonzero':w32(u,Y,1)
  elif fault=='descending':w32(u,Y+12,0)
  elif fault=='overrange':w32(u,Y+512,131072)
  elif fault=='overlap':y=CTX+2276
  elif fault=='unaligned':y=Y+1
  before=bytes(u.mem_read(CTX,SIZE));state['checking']=True;ret=call(u,sy['r5_native_gamma418_put'],[CTX,n,y])[0];state['checking']=False
  assert ret!=0 and bytes(u.mem_read(CTX,SIZE))==before;cases.append(dict(kind='reject_no_write',fault=fault))
 state['checking']=True;assert call(u,sy['r5_native_gamma418_seal'],[CTX])[0]==0;state['checking']=False
 before=bytes(u.mem_read(CTX,SIZE));assert call(u,sy['r5_native_gamma418_put'],[CTX,1,Y])[0]!=0;assert bytes(u.mem_read(CTX,SIZE))==before
 assert call(u,sy['r5_native_gamma418_begin'],[CTX])[0]!=0
 for mask in [1<<i for i in range(12)]+[0x555,0xaaa,0xfff]:
  u.mem_write(CTX,initial);assert call(u,sy['r5_native_gamma418_begin'],[CTX])[0]==0
  u.mem_write(Y,struct.pack('<129I',*[x*900 for x in range(129)]))
  for i in range(12):
   if mask&(1<<i):assert call(u,sy['r5_native_gamma418_put'],[CTX,i+1,Y])[0]==0
  assert bytes(u.mem_read(CTX+2100,176))==original_route
  assert call(u,sy['r5_native_gamma418_seal'],[CTX])[0]==0
  actual=bytes(u.mem_read(CTX+2100,176));expected=bytearray(original_route)
  for i,b in enumerate(BASES):
   if mask&(1<<i):struct.pack_into('<2I',expected,b*8,51+i*2,52+i*2)
  assert actual==expected
  normal=bytearray(cp[0xdcc514-0x108000:0xdcc514-0x108000+464])
  if mask&1:struct.pack_into('<2I',normal,0,51,52)
  assert bytes(u.mem_read(CTX+23020,464))==normal
  cases.append(dict(kind='selective_seal_route',mask=mask))
 (out/'initial_context.bin').write_bytes(initial)
 report=dict(schema='r5-native-gamma418-replay/1',passed=True,camera_io=False,installable=False,source_CP_sha256=SHA,context_bytes=SIZE,code_bytes=len(code),symbols={k:hex(v)for k,v in sy.items()},patches=pp,mapping=ids,checks=len(cases),cases=cases,math_calls=state['math'],alias_isolation=True,native_metadata_preserved=True,source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in [HERE/'native_gamma.c',HERE/'native_gamma.h',HERE/'native_gamma.o',HERE/'patch_native_gamma.py',HERE/'getter_gates.py',Path(__file__)]},limits=['Caller-owned context allocation/mapping/publication and parameter transport are integration obligations.','CP native math and route fragments execute; memory/logging ABIs are fixtures. No actual AP/CP import, camera/JPEG/preview or scheduler execution.','Native references use cold-zero-safe getter detours. Context is private until ready final release-store; original0..50 rows remain identical even after publishing.','One-shot cold-start write/seal only, reinitialization rejected. Existing Gamma hardware caches need native reload notification/reselection; warm runtime refresh is not implemented here.','Native aux+10 and output+18 intentionally carry new GammaID51..74; those IDs are separately checked. All other output bytes strictly match when parameters are unchanged.'])
 (out/'replay.json').write_text(json.dumps(report,indent=2)+'\n');(out/'module.bin').write_bytes(code);print('PASS',len(cases),'native Gamma overwrite cases;',len(code),'code bytes; no DAT')
if __name__=='__main__':main()
