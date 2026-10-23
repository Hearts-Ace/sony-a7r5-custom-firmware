"""Installed CC1 and native53 block13 branch seams with independent selection."""
from pathlib import Path
import json,hashlib,struct,sys,itertools
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from verify_r5_m4strict_cp_cpu import new_cpu,SCRATCH,SP,STOP
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
meta=json.loads((HERE/'build.json').read_text());cp=(HERE/'cp423.NONINSTALLABLE.bin').read_bytes();sha=hashlib.sha256(cp).hexdigest();assert sha==meta['candidate_sha256']
u=new_cpu(cp);BANK=0x3100000;u.mem_map(BANK,0x100000)
WRAP=SCRATCH+0x100;STATE=SCRATCH+0x1000;ENV=SCRATCH+0x2000;DST=SCRATCH+0x3000
def w(a,*v):u.mem_write(a,struct.pack('<'+'I'*len(v),*v))
w(WRAP,STATE,ENV);w(BANK,0x35424c53,9,4095,4095)
for s in range(12):
 u.mem_write(BANK+64+s*2392,bytes(32)+struct.pack('<24h',*[(s*61+i*37)%1001-500 for i in range(24)]))
 w(BANK+50896+24*(s+1),0x423f17e1,BANK,s+1,0,0,0)
w(BANK+50896,0x423f17e1,BANK,0,0,0,0)
capture={}
def hook(c,at,n,arg):
 if at==0x71e720:
  capture['original']=c.reg_read(UC_ARM_REG_R0);capture['adjust']=struct.unpack('<8H',c.mem_read(c.reg_read(UC_ARM_REG_R9),16))
u.hook_add(UC_HOOK_CODE,hook,begin=0x71e720,end=0x71e720)
WIRES=[0,3,2,1,16,15,19,20,17,18,5,13];P=[0,6,2,1,42,41,54,55,43,44,53,53];M=[21,27,23,22,46,45,56,57,47,48,53,53]
def setup(base,profile,selected):
 u.mem_write(STATE,bytes(0x500));u.mem_write(ENV,bytes(0x600));u.mem_write(STATE+0x2e,bytes([base]));u.mem_write(STATE+0x66,b'\2');u.mem_write(ENV+0x25,bytes([profile]));w(0x1a39458,BANK+50896+24*selected)
 u.mem_write(0x16b2f15,b'\1');u.mem_write(0x16afd20,b'\0');u.mem_write(0x195effc+0x34,struct.pack('<4b',-2,3,-1,1));u.mem_write(0x195effc+0x30,bytes([4,11,5,8]));u.mem_write(DST,b'\xa5'*80)
def call(at,*args,stop=STOP):
 for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
 u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,STOP|1);u.emu_start(at|1,stop,count=1000000)
 assert u.reg_read(UC_ARM_REG_PC)==stop and u.reg_read(UC_ARM_REG_SP)==SP
rows=[]
for n,selected,movie in itertools.product(range(12),(0,1,7,12),(False,True)):
 p=(M if movie else P)[n];setup(WIRES[n],p,selected);call(0x71e670,DST,p,WRAP)
 ptr=BANK+64+(selected-1)*2392+32 if selected else capture['original']
 k=struct.unpack('<24H',u.mem_read(ptr,48));a=capture['adjust'];b=[(k[i]+a[i])&65535 for i in range(8)]
 expected=struct.pack('<24H',*(b+[(b[i]+k[8+i])&65535 for i in range(8)]+[(b[i]+k[16+i])&65535 for i in range(8)]))
 assert bytes(u.mem_read(DST,48))==expected and bytes(u.mem_read(DST+48,32))==b'\xa5'*32
 rows.append(dict(base=WIRES[n],profile=p,selected=selected,installed_CC1_loop=True))
# The installed profile53 guard may only open the custom matrix path with an
# active custom config. It must retain native identity handling when off.
for base,selected in itertools.product((5,13),(0,1,7,12)):
 setup(base,53,selected);u.reg_write(UC_ARM_REG_R6,WRAP);u.reg_write(UC_ARM_REG_R3,53);u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,STOP|1)
 target=0x71d6f2 if selected else 0x71d6d0;u.emu_start(0x71d6cc|1,target,count=1000)
 assert u.reg_read(UC_ARM_REG_PC)==target and u.reg_read(UC_ARM_REG_SP)==SP
 rows.append(dict(base=base,selected=selected,installed_BW_SE_branch=True,target=hex(target)))
result=dict(passed=True,CP_sha256=sha,checks=len(rows),rows=rows,camera_io=False,limits=['Native installed CC1 loop and profile53 guard execute with caller-state fixtures; complete ISP, downstream BW/SE tint/monochrome and actual photographs are not covered.'])
(HERE/'cc1_hook423_replay.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS',len(rows),'423 installed CC1/BW-SE seams',sha)
