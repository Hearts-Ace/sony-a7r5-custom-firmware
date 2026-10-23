"""Actual main title producers and resource-to-char dispatch, isolated services.

No UI/event loop, display pixels, UXC loading or camera execution is claimed.
"""
from pathlib import Path
import hashlib, io, json, struct, sys
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'analysis/r5_custom_filter423_20261023/menu_research')]
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn import arm64_const as R
from read_menu import Image
BASE=ROOT/'analysis/r5_custom_filter423_20261023'
source=(Path(sys.argv[1]) if len(sys.argv)>1 else BASE/'ap/appFw.so').resolve()
raw=source.read_bytes();elf=ELFFile(io.BytesIO(raw));im=Image(source)
audit=json.loads((BASE/'import/module_audit.json').read_text())
RAM,SP,STOP=0x20000000,0x203f0000,0x203ff000
G=[getattr(R,'UC_ARM64_REG_X'+str(i)) for i in range(29)]+[R.UC_ARM64_REG_FP,R.UC_ARM64_REG_LR]
rows=[]
for bias in (0,0x40000000):
 u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
 for seg in elf.iter_segments():
  if seg['p_type']!='PT_LOAD':continue
  lo=(seg['p_vaddr']+bias)&-4096;hi=(seg['p_vaddr']+bias+seg['p_memsz']+4095)&-4096
  if hi>lo:u.mem_map(lo,hi-lo)
  if seg['p_filesz']:u.mem_write(seg['p_vaddr']+bias,seg.data())
 u.mem_map(RAM,0x400000)
 def w32(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
 def w64(a,v):u.mem_write(a,struct.pack('<Q',v))
 def r32(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 def r64(a):return struct.unpack('<Q',u.mem_read(a,8))[0]
 for section in elf.iter_sections():
  if section['sh_type']=='SHT_RELA':
   for rel in section.iter_relocations():
    if rel['r_info_type']==1027:w64(rel['r_offset']+bias,rel['r_addend']+bias)
 sy={n:a+bias for n,a in audit['symbols'].items()}
 state=dict(records={},text=None,trace=[],slice=False)
 def ret(v=0):
  lr=u.reg_read(R.UC_ARM64_REG_LR)
  for i in range(1,19):u.reg_write(G[i],0xdead0000+i)
  u.reg_write(G[0],v);u.reg_write(R.UC_ARM64_REG_PC,lr)
 def hook(cpu,pc,size,arg):
  at=pc-bias
  if pc==STOP or state['slice'] and at==0x1885b3c:cpu.emu_stop();return
  args=[cpu.reg_read(r)for r in G[:4]]
  if pc==sy['r5_native_menu_insert']:
   for q in range(args[1],args[2],16):state['records'][r64(q)]=r64(q+8)
   ret();return
  if pc==sy['r5_native_menu_normalize']:
   assert args[1]==0x1f2;ret(args[1]);return # stock alias control only; custom wrapper executes
  if at==0x1bd55fc:ret(0xffffffff);return # dynamic subtitle service boundary
  if at in (0x1bd7018,0x1bde9d8):ret(0);return # title special/style services
  if at in (0x17ffd0c,0x1800924,0x180093c):ret(0);return # locale/mode service inputs
  if at==0x16d9370:
   state['text']=bytes(cpu.mem_read(args[1],512)).split(b'\0')[0].decode('utf8');ret();return
  if at==0x16db4f0:state['text']=args[1];ret();return
  if at in (0x1bd559c,0x1bc4b34,0x1bc49c8,0x1bd912c,0x1885178,0x1885b38) or pc==sy['r5_filter_menu_name_draw']:state['trace'].append(at)
 watched=(STOP,sy['r5_native_menu_normalize'],sy['r5_native_menu_insert'],sy['r5_filter_menu_name_draw'],*[a+bias for a in (0x1bd55fc,0x1bd7018,0x1bde9d8,0x17ffd0c,0x1800924,0x180093c,0x16d9370,0x16db4f0,0x1bd559c,0x1bc4b34,0x1bc49c8,0x1bd912c,0x1885178,0x1885b38,0x1885b3c)])
 for at in set(watched):u.hook_add(UC_HOOK_CODE,hook,begin=at,end=at)
 def call(a,*args):
  state['slice']=False
  for i,r in enumerate(G):u.reg_write(r,0x123450000000+i)
  for i,v in enumerate(args):u.reg_write(G[i],v)
  u.reg_write(R.UC_ARM64_REG_SP,SP);u.reg_write(R.UC_ARM64_REG_LR,STOP)
  saved=[u.reg_read(r)for r in G[19:30]]
  u.emu_start(a,STOP,count=200000)
  assert u.reg_read(R.UC_ARM64_REG_PC)==STOP,hex(u.reg_read(R.UC_ARM64_REG_PC))
  assert u.reg_read(R.UC_ARM64_REG_SP)==SP
  assert saved==[u.reg_read(r)for r in G[19:30]]
  return u.reg_read(G[0])
 MMAP,NODES=RAM+0x1000,RAM+0x2000
 call(sy['r5_filter_menu_register'],MMAP,RAM,RAM)
 state['records'][0x1f2]=0x5858b08+bias
 cursor=[NODES]
 def tree(records,parent):
  if not records:return 0
  middle=len(records)//2;k,p=records[middle];node=cursor[0];cursor[0]+=0x40
  w32(node,1);w64(node+8,parent);w64(node+0x10,tree(records[:middle],node));w64(node+0x18,tree(records[middle+1:],node));w32(node+0x20,k);w64(node+0x28,p);return node
 root=tree(sorted(state['records'].items()),MMAP+8)
 w64(MMAP+0x10,root);w64(MMAP+0x18,root);w64(MMAP+0x20,root);w64(MMAP+0x28,len(state['records']))
 w64(0x59611f8+bias,MMAP)
 PRES,VARIANTS,PARAMS,INDEX,VIEW,SPRITE=RAM+0x10000,RAM+0x11000,RAM+0x12000,RAM+0x16000,RAM+0x18000,RAM+0x19000
 w64(PRES+0x40,VARIANTS)
 for i in range(2):w32(VARIANTS+i*16,2);w64(VARIANTS+i*16+8,PARAMS+i*0x1000)
 w32(INDEX,0);w32(INDEX+4,1)
 for facade in (0x582ca68,0x582d618):
  w64(0x591f9a8+bias,facade-0x10+bias)
  for producer in (0x2218cc8,0x221eee0):
   for mid,expected in ((0x635,0x02ff4230),(0x1f2,0x0200a2fd)):
    state['trace']=[];u.mem_write(PARAMS,bytes(0x2000))
    call(producer+bias,PRES,mid,INDEX)
    actual=r32(PARAMS+0x30);assert actual==expected,(hex(producer),hex(mid),hex(actual))
    # Native view_string getter establishes the payload identity; TextRow kind2
    # payload points directly at self+1d8, therefore +30 == self+208.
    assert call(0x18847c4+bias,VIEW)==VIEW+0x1d8
    w32(VIEW+0x208,actual);w64(VIEW+0x210,0)
    u.reg_write(G[19],VIEW);u.reg_write(G[20],SPRITE);u.reg_write(R.UC_ARM64_REG_SP,SP);u.reg_write(R.UC_ARM64_REG_LR,STOP)
    state['slice']=True;state['text']=None
    u.emu_start(0x1885b20+bias,STOP,count=200000)
    assert u.reg_read(R.UC_ARM64_REG_PC)==0x1885b3c+bias
    assert state['text']==('自定义滤镜' if mid==0x635 else expected),state['text']
    for at in (0x1bd559c,0x1bc4b34,0x1bc49c8,0x1bd912c,0x1885178,0x1885b38):assert at in state['trace'],hex(at)
    rows.append(dict(bias=hex(bias),facade=hex(facade),producer=hex(producer),MID=hex(mid),title_resource=hex(actual),dispatch=state['text'],native_registry=True))
windows=[('main_title_standard',0x2218cc8,0x128),('main_title_alternate',0x221eee0,0xd8),('title_public_wrapper',0x1bd559c,0x30),('title_descriptor_getter',0x1bc4b34,0x30),('normalized_leaf_lookup',0x1bc49c8,0x38),('view_factory_type2',0x182b5c0,0x58),('type2_view_string_factory',0x1829360,0xb0),('view_params_getter',0x18847c4,8),('view_resource_dispatch',0x1885b20,0x20)]
ranges=[dict(name=n,VA=hex(a),bytes=z,sha256=hashlib.sha256(im.read(a,z)).hexdigest(),disassembly=im.dis(a,z))for n,a,z in windows]
report=dict(passed=True,AP=str(source.relative_to(ROOT)),AP_sha256=hashlib.sha256(raw).hexdigest(),cases=len(rows),rows=rows,
 static_bindings=dict(type2_factory_slot='0x5020bf8',type2_factory='0x1829360',native_string_constructor='0x1884cd0',native_string_param_getter_slot='0x57914d0',native_string_param_getter='0x18847c4',parameter_offset='0x1d8',TextRow_title_offset='0x30',view_resource_offset='0x208',existing_name_draw_callsite='0x1885b38'),
 ranges=ranges,
 limits=['Main title producers, title getter, patched main alias and registry lookup execute actual candidate bytes at two PIE bases and ordinary/cached facades.', 'Native registry insert allocation is an explicit balanced-tree fixture retaining only actual candidate registration plus one real stock descriptor; subtitle, special-title, style and locale mode services are fixtures. The stock creative control alone uses an explicit identity alias fixture; the private MID uses the actual candidate wrapper.', 'The framework type2 factory and returned payload identity are static native-byte evidence; the test explicitly copies the produced title resource into that payload, then executes the actual dispatch slice. This is not a complete widget/event-loop test.', 'No camera, physical LCD, font rasterizer, UXC resource bank loading or full Sony event loop execution.'])
(OUT/('title_native_verification424.json' if 'r5_custom_menu424_' in str(source) else 'title_native_verification423.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
(OUT/('title_native_disassembly424.txt' if 'r5_custom_menu424_' in str(source) else 'title_native_disassembly423.txt')).write_text('\n\n'.join(r['name']+' '+r['VA']+'\n'+r['disassembly']for r in ranges)+'\n')
print(json.dumps({k:v for k,v in report.items()if k not in ('ranges','rows')},ensure_ascii=False))
