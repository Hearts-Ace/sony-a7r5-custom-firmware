"""Full native Gamma route bound to exact integrated final CP. No devices."""
from pathlib import Path
import hashlib,json,struct,sys,itertools
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from verify_r5_m4strict_cp_cpu import new_cpu,SCRATCH,SP,STOP,w32
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
P=HERE.parent/'cp';meta=json.loads((P/'build.json').read_text());candidate=(P/'cp423.NONINSTALLABLE.bin').read_bytes();sha=hashlib.sha256(candidate).hexdigest();assert sha==meta['candidate_sha256']
stock=(ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin').read_bytes();sy={k:int(v,16)for k,v in meta['symbols'].items()}
BANK=0x3100000;CTX=BANK+28768;Y=SCRATCH+0x6000;BASES=[0,3,2,1,16,15,19,20,17,18,5,13]
cpus=[new_cpu(stock),new_cpu(candidate)];state={'path':[],'low':SP}
for u in cpus:
 u.mem_map(BANK,0x100000)
 def hook(c,at,size,_):
  state['low']=min(state['low'],c.reg_read(UC_ARM_REG_SP))
  if at in (0xaa82d2,0xaa8304,0xaa833c,0xaa835e,0xaa839a,0xaa83f4,0xaa8416,0xaa8424,0xaa8436):state['path'].append(hex(at))
  if at==0xb0de92:c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
def call(u,at,args):
 for r,v in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):u.reg_write(r,v)
 u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,STOP|1);state.update(path=[],low=SP)
 u.emu_start(at|1,STOP,count=30000000);assert u.reg_read(UC_ARM_REG_PC)==STOP and u.reg_read(UC_ARM_REG_SP)==SP
 return u.reg_read(UC_ARM_REG_R0)
def prepare(selected):
 u=cpus[1];u.mem_write(BANK,bytes(522152));u.mem_write(0x1a39448,struct.pack('<2I',BANK,28768))
 w32(u,BANK,0x35424c44);w32(u,BANK+8,4095);w32(u,BANK+12,4095)
 for i in range(12):
  u.mem_write(BANK+64+i*2392+656,struct.pack('<129I',*[j*(700+i*20)for j in range(129)]))
  w32(u,BANK+64+i*2392+1172,1)
 assert call(u,sy['r5_native418_publish'],[BANK])==0
 w32(u,0x1a39458,BANK+50896+24*selected)
 return struct.unpack('<6I',u.mem_read(BANK+50896+24*selected,24))
def route(u,enum,transform,base=0,changes=None):
 a=SCRATCH;w=SCRATCH+0x1000;u.mem_write(a,bytes(0x80));u.mem_write(w,bytes(0x80));w32(u,a+4,enum);u.mem_write(a+8,bytes([transform]));u.mem_write(a+11,b'\1');w32(u,a+0x10,base);w32(u,a+0x34,3);w32(u,0xdcc4e0,0)
 u.mem_write(0x18d1c24,bytes(0x240));u.mem_write(0x19d1308,bytes(40))
 for off,val in (changes or {}).items():u.mem_write(a+off,val)
 call(u,0xaa81ca,[a,w]);return bytes(u.mem_read(w,0x54)),state['path'].copy()
rows=[]
for selected in (0,1,7,12):
 v=prepare(selected)
 for enum,t in itertools.product(range(58),(0,1)):
  ref,path=route(cpus[0],enum,t);got,gpath=route(cpus[1],enum,t)
  expected=struct.unpack('<I',cpus[1].mem_read(v[5]+enum*8+t*4,4))[0]
  assert struct.unpack_from('<I',got,0x30)[0]==expected,(selected,enum,t)
  if not(selected and enum==0):assert got==ref,(selected,enum,t)
  rows.append(dict(kind='normal',selected=selected,enum=enum,transform=t))
 for n,b in enumerate(BASES):
  for t in (0,1):
   ref,path=route(cpus[0],0,t,b);got,gpath=route(cpus[1],0,t,b)
   expected=51+2*n+t if selected else struct.unpack_from('<I',ref,0x30)[0]
   assert struct.unpack_from('<I',got,0x30)[0]==expected,(selected,n,t,got.hex())
   if not selected:assert got==ref
   rows.append(dict(kind='creative',selected=selected,base=b,transform=t,id=expected))
 specials=[('special_lut',{0x16:b'\1',0x18:struct.pack('<I',12)}),('forced45',{0xa:b'\1'}),('forced31',{0x2c:struct.pack('<I',2)}),('metadata_transform2',{0x34:struct.pack('<I',2)}),('disabled',{0xb:b'\0'})]
 for t,(name,ch)in itertools.product((0,1),specials):
  ref,path=route(cpus[0],0,t,0,ch);got,gpath=route(cpus[1],0,t,0,ch)
  if name in ('special_lut','forced45','forced31'):
   a=bytearray(got);b=bytearray(ref);a[0x34:0x38]=b[0x34:0x38]=bytes(4)
   assert a==b,(selected,name,t,got.hex(),ref.hex())
  rows.append(dict(kind=name,selected=selected,transform=t))
report=dict(passed=True,CP_sha256=sha,checks=len(rows),rows=rows,camera_io=False,limits=['Full native aa81ca routing with native logger fixture; synthetic RAM only. Other normal enum aliases remain original; only enum0 maps to custom ST because it is the proven base0 normal route. Special native overrides remain original.','No physical rendering, task dispatch or pixel comparison.'])
(HERE/'route423_replay.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(rows),'423 native Gamma routes',sha)
