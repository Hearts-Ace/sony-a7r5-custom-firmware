"""Installed native12 CC1 and matrix instruction replay; no camera/ISP execution."""
from pathlib import Path
import hashlib,json,struct,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from verify_r5_m4strict_cp_cpu import new_cpu,SCRATCH,SP,STOP
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn import arm_const as R
REG=[getattr(R,'UC_ARM_REG_R'+str(i))for i in range(13)]
BANK=SCRATCH+0x10000; WRAP=SCRATCH+0x100;STATE=SCRATCH+0x1000;CTX=SCRATCH+0x2000;DST=SCRATCH+0x3000;BSS=0x1a39448
WIRES=[0,3,2,1,16,15,19,20,17,18,5,13];STILL=[0,6,2,1,42,41,54,55,43,44,53,53];MOVIE=[21,27,23,22,46,45,56,57,47,48,53,53]
raw=(OUT/'cp420-grid.NONINSTALLABLE.bin').read_bytes();meta=json.loads((OUT/'build.json').read_text());assert hashlib.sha256(raw).hexdigest()==meta['candidate_sha256']
sy={k:int(v,16)for k,v in meta['symbols'].items()};base=(ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin').read_bytes()
counts=dict(custom_CC1=0,native_CC1=0,custom_matrix=0,native_matrix=0,resolver_guards=0)
def machine(code):
 u=new_cpu(code);u.mem_map(BANK,0x10000);st={}
 def hook(c,at,n,arg):
  if at==0x71e720:st['ptr']=c.reg_read(REG[0]);st['adj']=struct.unpack('<8H',c.mem_read(c.reg_read(R.UC_ARM_REG_R9),16))
 def guard(c,access,at,n,val,arg):
  assert SP-0x5000<=at<at+n<=SP or DST<=at<at+n<=DST+54,(hex(c.reg_read(R.UC_ARM_REG_PC)),hex(at),n)
 u.hook_add(UC_HOOK_CODE,hook,begin=0x71e720,end=0x71e720);u.hook_add(UC_HOOK_MEM_WRITE,guard)
 return u,st
u,st=machine(raw);v,vs=machine(base)
def w(c,a,n):c.mem_write(a,struct.pack('<I',n))
def setup(c,n,p,mask=4095,ready=0x4186a11):
 c.mem_write(STATE,bytes(0x500));c.mem_write(CTX,bytes(0x600));c.mem_write(WRAP,struct.pack('<2I',STATE,CTX)+bytes(24));c.mem_write(STATE+0x2e,bytes([WIRES[n]]));c.mem_write(STATE+0x66,b'\x02');c.mem_write(CTX+0x25,bytes([p]));c.mem_write(CTX+0x1a0,struct.pack('<3H',1024,1100,900))
 c.mem_write(BSS,struct.pack('<2I',BANK,28768)+bytes(24));c.mem_write(BANK,struct.pack('<4I',0x35424c53,7,mask,mask)+bytes(48))
 for s in range(12):
  cc=[(s*61+i*37)%1001-500 for i in range(24)];mat=[(s*11+i*3-400)&65535 for i in range(288)]
  c.mem_write(BANK+64+s*2392,bytes(32)+struct.pack('<24h',*cc)+struct.pack('<288H',*mat)+bytes(516))
 w(c,BANK+28768+23012,ready);c.mem_write(0x16b2f15,b'\x01');c.mem_write(0x16afd20,b'\x00');c.mem_write(0x195effc+0x34,struct.pack('<4b',-2,3,-1,1));c.mem_write(0x195effc+0x30,bytes([4,11,5,8]))
def call(c,at,args,stop=STOP,fullabi=True):
 c.mem_write(DST,b'\xa5'*80)
 saved=[0xabc00000+i for i in range(8)]
 for r,z in zip(REG[4:12],saved):c.reg_write(r,z)
 for r,z in zip(REG,args):c.reg_write(r,z)
 c.reg_write(R.UC_ARM_REG_SP,SP);c.reg_write(R.UC_ARM_REG_LR,STOP|1);c.emu_start(at|1,stop,count=10000)
 assert c.reg_read(R.UC_ARM_REG_PC)==stop,(hex(at),hex(c.reg_read(R.UC_ARM_REG_PC)))
 assert c.reg_read(R.UC_ARM_REG_SP)==SP
 if fullabi:assert [c.reg_read(r)for r in REG[4:12]]==saved
 return bytes(c.mem_read(DST,80))
def cc(n,p,custom):
 got=call(u,0x71e670,[DST,p,WRAP]);ptr=BANK+64+n*2392+32 if custom else st['ptr'];k=struct.unpack('<24H',u.mem_read(ptr,48));a=st['adj'];b=[(k[i]+a[i])&65535 for i in range(8)];expect=struct.pack('<24H',*(b+[(b[i]+k[8+i])&65535 for i in range(8)]+[(b[i]+k[16+i])&65535 for i in range(8)]))
 assert got[:48]==expect,(n,p,custom,st);assert got[48:]==b'\xa5'*32;counts['custom_CC1' if custom else 'native_CC1']+=1
 if not custom:
  exp=call(v,0x71e670,[DST,p,WRAP]);assert got==exp,(n,p,'baseline CC1')
def matrix(n,p,h,custom,site=False):
 got=call(u,0x71d6f8 if site else sy['r5_native418_matrix'],[DST,h,WRAP,p],0x71d6fc if site else STOP,not site)
 if custom:
  k=struct.unpack('<288H',u.mem_read(BANK+64+n*2392+80,576));hh=h if h<=15 else 0;mat=[]
  for e in range(3):
   a,b,c,d,f,g=k[e*96+hh*6:e*96+hh*6+6];mat.extend([1024+a+b,-a,-b,-c,1100+c+d,-d,-f,-g,900+f+g])
  expect=struct.pack('<27H',*[x&65535 for x in mat]);assert got[:54]==expect,(n,p,h)
 else:
  expect=call(v,0x71e41e,[DST,h,WRAP,p]);assert got==expect,(n,p,h,'native matrix')
 assert got[54:]==b'\xa5'*26;counts['custom_matrix' if custom else 'native_matrix']+=1
for n in range(12):
 for p in (STILL[n],MOVIE[n]):
  for mask in (0,1<<n,4095,4095^(1<<n)):
   for ready in (0,0x4186a11):
    setup(u,n,p,mask,ready);setup(v,n,p);eligible=bool(mask&(1<<n) and ready);cc(n,p,eligible)
    for h in list(range(16))+[16,255]:matrix(n,p,h,eligible)
    matrix(n,p,7,eligible,True)
  for bad in ('scene','profile','context','seal','received','bytes','wire'):
   setup(u,n,p);setup(v,n,p)
   if bad=='scene':u.mem_write(STATE+3,b'\x01');v.mem_write(STATE+3,b'\x01')
   elif bad=='profile':p2=18;u.mem_write(CTX+0x25,bytes([p2]));v.mem_write(CTX+0x25,bytes([p2]))
   elif bad=='context':u.mem_write(CTX+0x25,b'\xff')
   elif bad=='seal':w(u,BANK,0)
   elif bad=='received':w(u,BANK+12,0)
   elif bad=='bytes':w(u,BSS+4,0)
   else:u.mem_write(STATE+0x2e,b'\xff')
   q=18 if bad=='profile' else p;cc(n,q,False);matrix(n,q,9,False)
# Explicit native special pointers survive imported slots and sealed publication.
for ptr in (0x16b1e34,0x16b1e64):
 for n in range(12):
  setup(u,n,STILL[n]);call(u,sy['r5_native418_cc1'],[ptr,WRAP,STILL[n]]);assert u.reg_read(REG[0])==ptr;counts['resolver_guards']+=1
q=dict(passed=True,camera_io=False,CP_sha256=meta['candidate_sha256'],counts=counts,actual_installed_CC1_loop=True,actual_installed_matrix_callsite=True,all_12_ordinals_still_movie=True,common_Gamma_ready_before_after=True,native_fallback_byte_equal404=True,SP_callee_saved_output_tail=True,bank_write_guard=True,limits=['Original native caller state/context constructed as ABI fixtures; no complete camera scheduler, ISP, JPEG or preview execution.','BW/SE original profile53 bypass observed in native_wrapper_evidence.json is repaired by installed native418_b13_gate; actual caller coverage is independently tested in native53_replay.json. This all12 suite alone tests helper mathematics and BL seam.','Matrix native hue values above15 checked against native fallback behavior, custom fallback hue0.'])
(OUT/'native_color_replay.json').write_text(json.dumps(q,indent=2)+'\n');print(json.dumps(q))
