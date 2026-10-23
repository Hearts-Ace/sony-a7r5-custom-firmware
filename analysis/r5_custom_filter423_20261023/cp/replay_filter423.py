"""Source-bound CP423 publish/select/base-tail replay, synthetic CPU RAM only.

No memory-read hooks: Unicorn 2.1.4 can retain ITSTATE across those hooks.
"""
from pathlib import Path
import hashlib,json,struct,sys,zlib,itertools
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from verify_r5_m4strict_cp_cpu import new_cpu,SCRATCH,SP,STOP
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
BANK=0x3100000;ALLOCATION=522152;VIEWS=50896
meta=json.loads((HERE/'build.json').read_text());cp=(HERE/'cp423.NONINSTALLABLE.bin').read_bytes()
sha=hashlib.sha256(cp).hexdigest();assert sha==meta['candidate_sha256']
sy={k:int(v,16)for k,v in meta['symbols'].items()};u=new_cpu(cp);u.mem_map(BANK,0x100000)
u.mem_write(0x1a39448,struct.pack('<2I',BANK,28768)+bytes(24))
def r(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def w(a,*v):u.mem_write(a,struct.pack('<'+'I'*len(v),*v))
def call(at,args,limit=25000000):
 for rr,v in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):u.reg_write(rr,v)
 u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,STOP|1)
 u.emu_start(at|1,STOP,count=limit)
 assert u.reg_read(UC_ARM_REG_PC)==STOP and u.reg_read(UC_ARM_REG_SP)==SP,hex(u.reg_read(UC_ARM_REG_PC))
 return u.reg_read(UC_ARM_REG_R0)
WIRES=[0,3,2,1,16,15,19,20,17,18,5,13];PROFILE=[0,6,2,1,42,41,54,55,43,44,53,53]
M=[21,27,23,22,46,45,56,57,47,48,53,53]
w(BANK,0x35424c44,123,4095,4095)
curves=[]
for n in range(12):
 y=struct.pack('<129I',*[i*(700+n*20)for i in range(129)]);curves.append(y)
 cc=struct.pack('<24h',*[(n+1)*10+i for i in range(24)])
 mat=struct.pack('<288h',*[(n+1)*3+i for i in range(288)])
 grid=bytes(((n*7+i)%128)-64&255 for i in range(1215))
 u.mem_write(BANK+64+2392*n,('Filter%02d'%(n+1)).encode().ljust(32,b'\0')+cc+mat+y+struct.pack('<I',1)+grid+b'\0')
assert call(sy['r5_native418_publish'],[BANK])==0
assert r(BANK)==0x35424c53 and r(0x1a39458)==0
call(sy['r5_filter423_accept'],[71,1])
payload=call(sy['r5_transfer_bank_crc'],[BANK]);old=bytes(u.mem_read(BANK,ALLOCATION))
REQ=SCRATCH+0x100;ACK=REQ+0x80;WRAP=SCRATCH+0x400;ROOTSTATE=SCRATCH+0x1000;ENV=SCRATCH+0x2000;DST=SCRATCH+0x3000
w(WRAP,ROOTSTATE,ENV)
seq=0;counts=dict(tails=0,curves=0,cc1=0,matrix=0,packed=0,selections=0,gate_rejections=0,gamma_getters=0)
def select(selected,sequence=None,alias=71,digest=None,status=0):
 global seq
 if sequence is None:seq+=1;sequence=seq
 p=bytearray(struct.pack('<4B7I',0xea,1,1,32,0x53463552,sequence,selected,payload if digest is None else digest,alias,0,0))
 struct.pack_into('<I',p,28,zlib.crc32(p));u.mem_write(REQ,bytes(p))
 assert call(sy['r5_filter423_select'],[REQ,32,ACK])==1
 a=bytearray(u.mem_read(ACK,32));crc=struct.unpack_from('<I',a,28)[0];a[28:32]=bytes(4)
 assert zlib.crc32(a)==crc and a[2]==0x81 and struct.unpack_from('<I',a,24)[0]==status
 if not status:assert r(0x1a39458)==BANK+VIEWS+24*selected;counts['selections']+=1
def view(n):return struct.unpack('<6I',u.mem_read(BANK+VIEWS+24*n,24))
for selected in range(1,13):
 select(selected);v=view(selected);table,route,normal=v[3:];assert v[:3]==(0x423f17e1,BANK,selected)
 for n,wire in enumerate(WIRES):
  oldid=struct.unpack_from('<2I',cp,0x107eefc-0x108000+wire*8)
  assert (r(route+wire*8),r(route+wire*8+4))==(51+2*n,52+2*n)
  for k,(oid,part)in enumerate([(oldid[0],0),(oldid[0],6),(oldid[1],6)]):
   record=r(table+(51+2*n+(k==2))*28+part*4)
   native=struct.unpack_from('<I',cp,0x107e968-0x108000+oid*28+part*4)[0]
   got=bytes(u.mem_read(record,576));assert got[:516]==curves[selected-1]
   assert got[516:]==cp[native-0x108000+516:native-0x108000+576]
   counts['tails']+=1;counts['curves']+=1
  for p in (PROFILE[n],M[n]):
   u.mem_write(ROOTSTATE,bytes(0x400));u.mem_write(ENV,bytes(0x300));u.mem_write(ROOTSTATE+0x2e,bytes([wire]));u.mem_write(ENV+0x25,bytes([p]))
   original=0xd00000;assert call(sy['r5_native418_cc1'],[original,WRAP,p])==BANK+64+2392*(selected-1)+32;counts['cc1']+=1
   u.mem_write(ENV+0x1a0,struct.pack('<3H',1024,1100,900))
   for hue in (0,7,15,255):
    assert call(sy['r5_native418_matrix'],[DST,hue,WRAP,p])>=0
    h=hue if hue<16 else 0;k=struct.unpack('<288h',u.mem_read(BANK+64+2392*(selected-1)+80,576));expected=[]
    for e in range(3):
     a,b,c,d,f,g=k[e*96+h*6:e*96+h*6+6];expected += [1024+a+b,-a,-b,-c,1100+c+d,-d,-f,-g,900+f+g]
    assert bytes(u.mem_read(DST,54))==struct.pack('<27H',*[x&65535 for x in expected]);counts['matrix']+=1
  u.mem_write(ROOTSTATE+3,b'\1');assert call(sy['r5_native418_cc1'],[original,WRAP,p])==original;counts['gate_rejections']+=1
  u.mem_write(ROOTSTATE+3,b'\0');u.mem_write(ENV+0x25,b'\xff');assert call(sy['r5_native418_cc1'],[original,WRAP,p])==original;counts['gate_rejections']+=1
 # Packed table every node/level against independent order model.
 order=struct.unpack_from('<405H',cp,0xe8c1d8-0x108000);grid=bytes(u.mem_read(BANK+64+(selected-1)*2392+1176,1215))
 for level in range(8):
  want=[0]*405
  for i in range(405):
   vv=[struct.unpack_from('<b',grid,c*405+i)[0]for c in range(3)];vv=[x*(level+1)>>3 if level<7 else x for x in vv]
   want[order[i]]=sum((x&127)<<(22-10*c)for c,x in enumerate(vv))
  assert bytes(u.mem_read(BANK+52360+(selected-1)*12960+level*1620,1620))==struct.pack('<405I',*want);counts['packed']+=405
select(0);v=view(0)
assert bytes(u.mem_read(v[4],176))==cp[0x107eefc-0x108000:0x107eefc-0x108000+176]
assert bytes(u.mem_read(v[5],464))==cp[0xdcc514-0x108000:0xdcc514-0x108000+464]
for n,wire in enumerate(WIRES):
 nativeids=struct.unpack_from('<2I',cp,0x107eefc-0x108000+wire*8)
 for part in range(7):
  for t in (0,1):
   got=r(v[3]+(51+2*n+t)*28+part*4)
   want=0 if t and part!=6 else struct.unpack_from('<I',cp,0x107e968-0x108000+nativeids[t]*28+(6 if part==6 else 0)*4)[0]
   assert got==want
# Rejections never change active. Duplicate latest success is idempotent.
before=r(0x1a39458);select(0,seq);select(1,seq,status=3);select(0,seq-1,status=3);select(13,status=4);select(0,alias=70,status=5);select(0,digest=payload^1,status=5);assert r(0x1a39458)==before
assert bytes(u.mem_read(BANK,ALLOCATION))==old,'SELECT mutated published generation'
# Actual installed getter shims preserve each destination and original flags.
gates=json.loads((HERE.parent/'gamma/getter_build423/gates.json').read_text())
for selected in (0,1,6,12):
 select(selected);v=view(selected)
 for g in gates['records']:
  for i in range(13):u.reg_write(UC_ARM_REG_R0+i,0x12340000+i)
  u.reg_write(UC_ARM_REG_CPSR,0xa00f01f3);u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,STOP|1)
  registers=[u.reg_read(UC_ARM_REG_R0+i)for i in range(13)];flags=u.reg_read(UC_ARM_REG_CPSR)
  site=int(g['site'],16);u.emu_start(site|1,int(g['resume'],16),count=1000)
  label='normal_route' if '_normal_route_' in g['symbol'] else 'table' if '_table_' in g['symbol'] else 'route'
  expected=v[3+['table','route','normal_route'].index(label)]
  registers[g['register']]=expected
  assert [u.reg_read(UC_ARM_REG_R0+i)for i in range(13)]==registers
  assert u.reg_read(UC_ARM_REG_SP)==SP and u.reg_read(UC_ARM_REG_LR)==STOP|1
  assert (u.reg_read(UC_ARM_REG_CPSR)&0xf80f0000)==(flags&0xf80f0000);counts['gamma_getters']+=1
result=dict(passed=True,CP_sha256=sha,allocation_bytes=ALLOCATION,counts=counts,all36_base_part_tails_each12_configs=True,selected0_expanded75_table_native_safe=True,SELECT_generation_immutable=True,devices=False,limits=['Synthetic native CPU execution and ABI fixtures; no camera heap/stack budget, physical cache, whole-frame selection atomicity or ISP/JPEG pixel claim.'])
(HERE/'filter423_replay.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
