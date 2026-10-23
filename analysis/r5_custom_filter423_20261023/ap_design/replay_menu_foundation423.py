"""Compiled A64 registration and private-menu callbacks; no renderer acceptance."""
from pathlib import Path
import hashlib,io,json,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];CAND=HERE.parent
sys.path[:0]=[str(ROOT/'vendor/audit-python')]
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn import arm64_const as R
raw=(CAND/'ap/appFw.so').read_bytes();audit=json.loads((CAND/'import/module_audit.json').read_text());elf=ELFFile(io.BytesIO(raw));rows=[]
for bias in(0,0x40000000):
 u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']!='PT_LOAD':continue
  lo=(s['p_vaddr']+bias)&-4096;hi=(s['p_vaddr']+s['p_memsz']+bias+4095)&-4096
  u.mem_map(lo,hi-lo)
  if s['p_filesz']:u.mem_write(s['p_vaddr']+bias,s.data())
 RAM=0x20000000;STOP=RAM+0xff000;SP=RAM+0xf0000;u.mem_map(RAM,0x100000)
 sy={n:v+bias for n,v in audit['symbols'].items()};st={'events':[],'mask':0x805,'selected':7,'request':None}
 def ret(v=0):u.reg_write(R.UC_ARM64_REG_X0,v);u.reg_write(R.UC_ARM64_REG_PC,u.reg_read(R.UC_ARM64_REG_LR))
 names=('r5_native_menu_insert','r5_native_row_insert','r5_native_menu_normalize','r5_native_row_normalize','r5_native_row_available','r5_native_row_available_direct','r5_native_row_parent','name_id','name_char','r5_filter_request','r5_filter_selected','r5_filter_available_mask','r5_filter_short_name','r5_filter_full_name')
 native={sy[n]:n for n in names}
 def hook(cpu,pc,n,_):
  kind=native[pc];a=[cpu.reg_read(x)for x in (R.UC_ARM64_REG_X0,R.UC_ARM64_REG_X1,R.UC_ARM64_REG_X2)]
  if kind.endswith('_insert'):
   st['events'].append((kind,*a));ret();return
  if kind in('r5_native_menu_normalize','r5_native_row_normalize','r5_native_row_available','r5_native_row_available_direct','r5_native_row_parent'):st['fallback']=(kind,a[:2]);ret(0x3456);return
  if kind=='r5_filter_selected':ret(st['selected']);return
  if kind=='r5_filter_available_mask':ret(st['mask']);return
  if kind=='r5_filter_request':st['request']=a[0];ret();return
  if kind in('r5_filter_short_name','r5_filter_full_name'):
   value=('short'if kind.endswith('short_name')else'full')+str(a[0]);u.mem_write(RAM,value.encode()+b'\0');ret(RAM);return
  if kind=='name_id':st['text']=('id',a[0],a[1]);ret();return
  if kind=='name_char':st['text']=('char',a[0],bytes(cpu.mem_read(a[1],96)).split(b'\0')[0].decode());ret();return
 for at in native:u.hook_add(UC_HOOK_CODE,hook,begin=at,end=at)
 def call(name,*args):
  for i in range(19,30):u.reg_write(getattr(R,'UC_ARM64_REG_X'+str(i)),0x12340000+i)
  for i,v in enumerate(args):u.reg_write(getattr(R,'UC_ARM64_REG_X'+str(i)),v)
  u.reg_write(R.UC_ARM64_REG_SP,SP);u.reg_write(R.UC_ARM64_REG_LR,STOP)
  u.emu_start(sy[name],STOP,count=1000000)
  assert u.reg_read(R.UC_ARM64_REG_PC)==STOP and u.reg_read(R.UC_ARM64_REG_SP)==SP
  for i in range(19,30):assert u.reg_read(getattr(R,'UC_ARM64_REG_X'+str(i)))==0x12340000+i
  return u.reg_read(R.UC_ARM64_REG_X0)
 call('r5_filter_menu_register',RAM+0x100,RAM+0x200,RAM+0x210)
 events=st['events'];assert len(events)==2 and events[0][1:]==(RAM+0x100,RAM+0x200,RAM+0x210)
 pair=bytes(u.mem_read(events[1][2],16));assert struct.unpack('<2Q',pair)==(0x635,sy['r5_filter_menu_descriptor'])
 call('r5_filter_rows_register',RAM+0x300,RAM+0x400,RAM+0x410)
 pair_event=st['events'][-1];assert pair_event[3]-pair_event[2]==13*16
 for i in range(13):
  key,ptr=struct.unpack('<2Q',u.mem_read(pair_event[2]+16*i,16));assert key==0x1600+i and ptr==sy['r5_filter_menu_rows']+128*i
  rec=bytes(u.mem_read(ptr,128));assert struct.unpack_from('<I',rec,0x34)[0]==i and struct.unpack_from('<I',rec,0x38)[0]==0x39fc
  assert struct.unpack_from('<2H',rec,0x74)==(0x1086,0x12)
  assert struct.unpack_from('<I',rec,0x18)[0]==0x4cf
 d=bytes(u.mem_read(sy['r5_filter_menu_descriptor'],0xc0));assert struct.unpack_from('<I',d,0x54)[0]==13
 assert struct.unpack_from('<2I',d,0x20)==(0x2ed,0x4cf)
 assert struct.unpack_from('<Q',d,0x78)[0]==sy['r5_filter_menu_selected'] and struct.unpack_from('<Q',d,0x80)[0]==sy['r5_filter_menu_select']
 assert call('r5_filter_menu_normalize',0,0x635)==0x635 and call('r5_filter_menu_normalize',0,0x1e6)==0x3456
 for i in range(13):
  assert call('r5_filter_row_normalize',0,0x1600+i)==0x1600+i
  assert call('r5_filter_row_parent',0,0x1600+i)==0x635
  for f in ('r5_filter_row_available','r5_filter_row_available_direct'):assert call(f,0,0x1600+i)==(1 if i==0 else(st['mask']>>(i-1))&1)
 for f in('r5_filter_row_normalize','r5_filter_row_parent','r5_filter_row_available','r5_filter_row_available_direct'):assert call(f,0,0x84c)==0x3456
 assert call('r5_filter_menu_selected')==7
 st['mask']=4095
 for n in range(13):
  call('r5_filter_menu_select',n);assert st['request']==n
  call('r5_filter_menu_select',0x1600+n);assert st['request']==n
 st['mask']=0x805;missing=0
 for n in range(1,13):
  if st['mask']&(1<<(n-1)):continue
  for value in(n,0x1600+n):
   st['request']=None;call('r5_filter_menu_select',value);assert st['request'] is None;missing+=1
 st['mask']=0;st['request']=None;call('r5_filter_menu_select',0);assert st['request']==0
 st['request']=None;call('r5_filter_menu_select',13);assert st['request'] is None
 for resource,text in((0x02ff4230,'自定义滤镜'),(0x02ff4300,'关闭'),(0x02ff4302,'short2'),(0x02ff4402,'full2')):
  call('r5_filter_menu_name_draw',RAM+0x500,resource);assert st['text']==('char',RAM+0x500,text)
 call('r5_filter_menu_name_draw',RAM+0x500,0x021c6e10);assert st['text']==('id',RAM+0x500,0x021c6e10)
 rows.append({'bias':hex(bias),'registrations':14,'row_callbacks':13,'selection_callbacks':26,'missing_selection_callbacks_rejected':missing,'off_with_empty_mask':True,'private_names':4,'native_fallback_preserved':True})
report={'passed':True,'camera_io':False,'AP_sha256':hashlib.sha256(raw).hexdigest(),'rows':rows,'limits':['Registry containers, native fallbacks and AP selection/name state are explicit fixtures.','This tests compiled foundation only; full renderer, navigation, actual UI display and device behavior are separate.']}
(HERE/'menu_foundation_replay.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
