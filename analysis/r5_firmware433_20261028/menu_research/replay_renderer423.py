"""A64 native list/string path with explicit widget backend/OS fixtures.
Runs the shipped native list update, native param builder/string rendering and
4.23 overlay lifecycle, observing final TextSprite strings/rectangles. No UI.
"""
from pathlib import Path
import hashlib,io,json,struct,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;CAND=OUT.parent
sys.path[:0]=[str(ROOT/'vendor/audit-python')]
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn import arm64_const as R
raw=(CAND/'ap/appFw.so').read_bytes();elf=ELFFile(io.BytesIO(raw));audit=json.loads((CAND/'import/module_audit.json').read_text());results=[]
RAM=0x20000000;STOP=RAM+0x7ff000;SP=RAM+0x7f0000;OWNER=RAM+0x10000;CTX=RAM+0x50000;HEAP=RAM+0x100000;STUB=RAM+0x600000
for bias in (0,0x40000000):
 u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']!='PT_LOAD':continue
  lo=(s['p_vaddr']+bias)&-4096;hi=(s['p_vaddr']+s['p_memsz']+bias+4095)&-4096
  u.mem_map(lo,hi-lo)
  if s['p_filesz']:u.mem_write(s['p_vaddr']+bias,s.data())
 u.mem_map(RAM,0x800000);sy={n:v+bias for n,v in audit['symbols'].items()}
 dynsym=elf.get_section_by_name('.dynsym');imports={};nextstub=STUB
 for sec in elf.iter_sections():
  if sec['sh_type']!='SHT_RELA':continue
  for rel in sec.iter_relocations():
   a=rel['r_offset']+bias;t=rel['r_info_type'];add=rel['r_addend']
   if t==1027:u.mem_write(a,struct.pack('<Q',add+bias))
   elif t in (257,1025,1026):
    sym=dynsym.get_symbol(rel['r_info_sym']);name=sym.name
    if sym['st_shndx']!='SHN_UNDEF':value=sym['st_value']+bias
    else:
     if name not in imports:imports[name]=nextstub;nextstub+=4
     value=imports[name]
    u.mem_write(a,struct.pack('<Q',value+add))
 names={v:k for k,v in imports.items()};st={'next':HEAP,'events':[],'fail':False,'backend':{},'texts':[]}
 def r32(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 def r64(a):return struct.unpack('<Q',u.mem_read(a,8))[0]
 def w32(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
 def w64(a,v):u.mem_write(a,struct.pack('<Q',v))
 def ret(v=0):u.reg_write(R.UC_ARM64_REG_X0,v);u.reg_write(R.UC_ARM64_REG_PC,u.reg_read(R.UC_ARM64_REG_LR))
 def alloc(n):p=st['next'];st['next']=(p+n+15)&-16;assert st['next']<RAM+0x500000;u.mem_write(p,bytes(n));return p
 def code(cpu,pc,size,arg):
  av=[cpu.reg_read(getattr(R,'UC_ARM64_REG_X'+str(i)))for i in range(8)];at=pc-bias
  if pc==STOP:cpu.emu_stop();return
  if pc in names:
   name=names[pc];st['last']=(st.get('last',[])+[(name,av[:3])])[-20:]
   if name=='__assert_fail':raise AssertionError('native assert')
   if name.startswith('_Znwm') or name in ('malloc','calloc'):ret(alloc(av[0]));return
   if name in ('memcpy','memmove'):cpu.mem_write(av[0],bytes(cpu.mem_read(av[1],av[2])));ret(av[0]);return
   if name=='memset':cpu.mem_write(av[0],bytes([av[1]&255])*av[2]);ret(av[0]);return
   # The frontend native widget constructor/vtables execute; external UX backend
   # operations are recorded fixtures. Scalar/vector result ABIs are explicit.
   if 'getPosition' in name or 'getLocalPos' in name:
    p=CTX+0x100;cpu.mem_write(p,struct.pack('<2f',0,0));ret(p);return
   if 'setPosition' in name or 'setSize' in name:ret();return
   if 'TextSprite9setStringEj' in name:st['texts'].append(('id',av[0],av[1]));ret();return
   if 'TextSprite9setStringEPKc' in name:st['texts'].append(('char',av[0],bytes(cpu.mem_read(av[1],96)).split(b'\0')[0].decode()));ret();return
   if name.startswith('_ZN2ux') or name.startswith('_ZNK2ux') or name.startswith('_Zdl') or name.startswith('_ZNSt') or name.startswith('_ZNKSt') or name.startswith('_ZN9') or name.startswith('_ZNSa'):ret();return
   st.setdefault('foreign',set()).add(name);ret();return
  if pc==sy['r5_osal_alloc']:
   if st['fail']:w64(av[1],0);ret(1)
   else:w64(av[1],alloc(av[2]));st['events'].append(('alloc',av[2]));ret()
   return
  if pc==sy['r5_osal_free']:st['events'].append(('free',av[1]));ret();return
  if pc in (sy['r5_filter_short_name'],sy['r5_filter_full_name']):
   value=('S' if pc==sy['r5_filter_short_name'] else 'Full filter name ')+str(av[0]);p=CTX+0x200;cpu.mem_write(p,value.encode()+b'\0');ret(p);return
  if at in (0x28e03b4,0x28e03c8):ret(CTX+0x300);return
  if at in (0x2e7d208,0x2e7cee4,0x17f7d68,0x185e908,0x185e8d4):ret();return
  if at in (0x181ad5c,0x17ffd0c,0x1800924,0x180093c,0x1816e4c):ret();return
  if at==0x35b858c:raise AssertionError('native assert at '+hex(pc)+' LR='+hex(cpu.reg_read(R.UC_ARM64_REG_LR))+' args='+str(av[:4]))
  if at==0x3694f64:
   cpu.mem_write(av[2],bytes(cpu.mem_read(av[3],av[4])));ret();return
 for at in [STOP,*names,sy['r5_osal_alloc'],sy['r5_osal_free'],sy['r5_filter_short_name'],sy['r5_filter_full_name']]:u.hook_add(UC_HOOK_CODE,code,begin=at,end=at)
 for at in [0x28e03b4,0x28e03c8,0x2e7d208,0x2e7cee4,0x17f7d68,0x185e908,0x185e8d4,0x181ad5c,0x35b858c,0x3694f64,0x17ffd0c,0x1800924,0x180093c,0x1816e4c]:u.hook_add(UC_HOOK_CODE,code,begin=at+bias,end=at+bias)
 def call(at,*args):
  for i in range(19,30):u.reg_write(getattr(R,'UC_ARM64_REG_X'+str(i)),0x12340000+i)
  for i,v in enumerate(args):u.reg_write(getattr(R,'UC_ARM64_REG_X'+str(i)),v)
  u.reg_write(R.UC_ARM64_REG_SP,SP);u.reg_write(R.UC_ARM64_REG_LR,STOP)
  try:u.emu_start(at,STOP,count=3000000)
  except Exception as e:raise RuntimeError(f'PC={u.reg_read(R.UC_ARM64_REG_PC):x} {e} last={st.get("last")}')from e
  assert u.reg_read(R.UC_ARM64_REG_PC)==STOP and u.reg_read(R.UC_ARM64_REG_SP)==SP
  for i in range(19,30):assert u.reg_read(getattr(R,'UC_ARM64_REG_X'+str(i)))==0x12340000+i
  return u.reg_read(R.UC_ARM64_REG_X0)
 # Constructor external UX base Widget fixture must supply virtual slots for
 # inherited methods. The ELF import relocations bind these to recorded UX stubs.
 
 for m in (0x1d8,0x210,0x248,0x280):w64(0x74d8000+bias+m,CTX+0x400);w64(0x74d8000+bias+m+8,1)
 call(0x16ea9a8+bias)
 call(0x185e980+bias,OWNER,CTX)
 scenarios=[]
 def draw(owner,start,animated=False):
  w32(owner+0xe0b0,0x1600+start);w32(owner+0xe0b4,13);w32(owner+0xe0b8,start)
  w32(owner+0x28b10,0x1600+start);w32(owner+0xe160,1);w32(owner+0x28b00,start)
  u.mem_write(owner+0x28b0c,bytes([int(animated)]))
  for i in range(75):w32(owner+0xdf84+4*i,0x1600+i)
  for i in range(13):
   w32(owner+0x208+i*4,0x1600+i);w32(owner+0x334+i*4,0x02ff4300+i)
  st['texts'].clear();call(sy['r5_filter_list_update'],owner)
  return list(st['texts'])
 def expected(n,full=False):return '关闭'if n==0 else ('Full filter name 'if full else 'S')+str(n)
 def check(owner,start,animated=False):
  texts=draw(owner,start,animated);count=7 if animated else 6
  pairs=texts[-2*count:];assert len(pairs)==2*count
  rects=[]
  for i in range(count):
   n=start+i;assert pairs[2*i][2]==expected(n) and pairs[2*i+1][2]==expected(n,True),(start,pairs)
   p=r64(owner+0x289a8+i*8)+0x1d8
   # TextSprite object is +830 from its owning native view_string.
   full=pairs[2*i+1][1]-0x830+0x1d8
   a=struct.unpack('<4I',u.mem_read(p+0x18,16));b=struct.unpack('<4I',u.mem_read(full+0x18,16))
   assert a[2]==112 and b==(a[0]+128,a[1],274,a[3]),(a,b)
   assert r32(full+0x30)==0x02ff4400+n and r64(full+0x38)==0
   rects.append(dict(number=n,short_rect=a,full_rect=b,texts=[pairs[2*i][2],pairs[2*i+1][2]]))
  scenarios.append(dict(owner=hex(owner),start=start,animated=animated,rects=rects))
 for start in (0,1,6,7):check(OWNER,start)
 check(OWNER,5,True)
 # A cached extra set is hidden when the same list carries stock resources.
 w32(OWNER+0x334,0x02000001);call(sy['r5_filter_list_update'],OWNER)
 ep=next(v[1]for v in st['events']if v[0]=='alloc')
 # A second independent native list gets a distinct overlay, then both close.
 other=OWNER+0x60000;call(0x185e980+bias,other,CTX);check(other,7)
 allocs=[e for e in st['events']if e[0]=='alloc'];assert len(allocs)==2 and all(e[1]==18496 for e in allocs)
 call(sy['r5_filter_list_destroy'],other);call(sy['r5_filter_list_destroy'],OWNER)
 assert len([e for e in st['events']if e[0]=='free'])==2
 # Genuine allocation failure degrades to single-column full labels; the list
 # and stock destructor still run and no nonexistent overlay is freed.
 last=OWNER+0xc0000;call(0x185e980+bias,last,CTX);st['fail']=True;texts=draw(last,0)
 assert [t[2]for t in texts[-6:]]==[expected(i,True)for i in range(6)]
 call(sy['r5_filter_list_destroy'],last)
 assert len([e for e in st['events']if e[0]=='free'])==2
 results.append(dict(bias=hex(bias),passed=True,scenarios=scenarios,allocation_bytes=18496,allocations=2,frees=2,oom_full_name_fallback=True,native_noncustom_path=True,external_fixture_symbols=sorted(st['foreign'])))

report=dict(passed=True,AP_sha256=hashlib.sha256(raw).hexdigest(),rows=results,camera_io=False,limits=['Native frontend instructions execute. External UX graphics and allocator backend are fixtures; no physical framebuffer, font glyph rasterization or display acceptance.'])
(OUT/'native_renderer423_replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='rows'}))
