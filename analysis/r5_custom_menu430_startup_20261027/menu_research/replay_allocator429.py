"""Execute actual app-level widget/parameter allocators and view creation.
Imported libObj/libc/GUI services remain named, explicit fixtures, not widget
constructors or app-level widget vtables. No device IO.
"""
from pathlib import Path
import io,sys,json,hashlib
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'analysis/r5_custom_menu430_startup_20261027/menu_research')]
from replay_page425 import PageVM,RAM,X,R
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_CODE
MEM=0x30000000;STUB=0x31000000;ARENA=MEM+0x200000

class AllocVM(PageVM):
 def pagehook(self,u,pc,size,arg):
  if pc-self.bias in (0x1b2ae4c,0x1bc3304):return
  super().pagehook(u,pc,size,arg)
 def __init__(self,bias):
  super().__init__(bias);self.extern={};self.extcalls=[];self.nextalloc=MEM+0x300000;self.u.mem_map(MEM,0x400000);self.u.mem_map(STUB,0x100000)
  elf=ELFFile(io.BytesIO(self.im.data));dyn=elf.get_section_by_name('.dynsym')
  for at,(info,ad)in self.im.relocs.items():
   if info&0xffffffff in (257,1025,1026):
    sy=dyn.get_symbol(info>>32)
    if sy.entry.st_shndx=='SHN_UNDEF':
     ptr=STUB+len(self.extern)*8;self.extern[ptr]=sy.name;self.w64(at+bias,ptr+ad)
    else:self.w64(at+bias,sy.entry.st_value+bias+ad)
  self.shell_init=set();self.draw_methods=set();self.draw_calls=[]
  for got in (0x5984738,0x59280a8):
   vt=self.q(got+bias)+16;self.shell_init.add(self.q(vt+0x148))
  self.u.hook_add(UC_HOOK_CODE,self.nativehook)
 def nativehook(self,u,pc,size,arg):
  at=pc-self.bias;a=[u.reg_read(r)for r in X[:5]]
  # Liveview shell low-level constructors require the running GUI singleton;
  # keep their real arena allocator and real per-type param initializer.
  if at in (0x1879dd0,0x187986c):
   self.w64(a[0],self.q((0x5984738 if at==0x1879dd0 else 0x59280a8)+self.bias)+16);self.ret(a[0]);return
  if pc in self.shell_init:self.ret();return
  if pc in self.draw_methods:
   self.draw_calls.append(dict(pc=hex(pc-self.bias),obj=hex(a[0])));self.ret();return
  if pc in self.extern:
   name=self.extern[pc];a=[u.reg_read(r)for r in X[:5]];self.extcalls.append((name,a[:2]))
   if name in ('_Znwm','_Znam','_ZnwmRKSt9nothrow_t','_ZnamRKSt9nothrow_t','malloc'):
    at=self.nextalloc;self.nextalloc=(at+a[0]+127)&~127;self.ret(at);return
   if name in ('memcpy','memmove'):
    u.mem_write(a[0],bytes(u.mem_read(a[1],a[2])));self.ret(a[0]);return
   if name=='memset':u.mem_write(a[0],bytes([a[1]&255])*a[2]);self.ret(a[0]);return
   # These are the UX/libObj import boundary. App-owned allocators, String/
   # touch constructors and per-type parameter initialization are NOT stubbed.
   if name.startswith('_ZN2ux') or name.startswith('_ZNK2ux') or name.startswith('_ZN5alcor') or name.startswith('_ZNK5alcor') or name.startswith('_ZN5libra') or name.startswith('_ZNK5libra'):
    self.ret(0);return
   self.failed=dict(name=name,pc=hex(pc),lr=hex(u.reg_read(R.UC_ARM64_REG_LR)));u.emu_stop()

rows=[]
for bias in (0,0x40000000):
 for layout in (0,1):
  vm=AllocVM(bias);c,p=vm.open()
  if layout:vm.call(vm.q(vm.q(p)+0x40),p,layout)
  view=MEM;vm.w64(view,0x5783098+bias);vm.w64(view+0x3e98,ARENA);vm.w32(view+0x3ea0,0x20000)
  # View ctor's embedded empty vector storage contract.
  for off in (0x18ce50,0x18ce88,0x18cec0):vm.w64(view+off,view+off+0x30);vm.w64(view+off+8,1)
  maskptr=STUB+0xf0000;vm.u.mem_write(maskptr,vm.masks);vm.failed=None
  try:
   vm.call(0x182b41c+bias,view,0xd9,vm.styles,34,layout,maskptr,0x4060b40+bias,0x4060ab8+bias)
   vm.call(0x182c56c+bias,view)
   allocs=[]
   for i in range(34):
    typ=vm.d(view+0x10+i*16);param=vm.q(view+0x18+i*16)
    allocs.append(dict(index=i,type=typ,param=hex(param),widget=hex(vm.q(view+0x3ec8+8*i)),resource=hex(vm.d(param+0x30)) if typ==2 else None,font_style=vm.d(param+0x348)if typ==2 else None))
   row=dict(bias=hex(bias),layout=layout,passed=vm.failed is None,arena_used=vm.d(view+0x3ea4),allocations=allocs,unresolved=vm.failed,external_calls=vm.extcalls)
   if vm.failed is None:
    assert 0<vm.d(view+0x3ea4)<45184
    vm.w64(p+0x48,view+0x10)
    # Compiled projection uses real allocated map; first call uses mode0.
    vm.call(vm.q(vm.q(p)+0x10),p,0)
    for i in [9,11,12,13,16,17,18,19,20,21]:assert vm.d(vm.q(view+0x18+16*i)+0x30)!=0xffffffff
    # Actual view update, with only per-widget drawing methods bounded.
    # This tests mode0 propagation and proves mode0 still invokes backend.
    for rec in allocs:
     obj=int(rec['widget'],16)
     if obj:
      vt=vm.q(obj)
      for off in (0x150,0x158,0x188):vm.draw_methods.add(vm.q(vt+off))
    vm.call(0x182c000+bias,view,0)
    assert vm.draw_calls,("no draw",vm.d(view+0x5e08),len(vm.draw_methods),allocs)
    for rec in allocs:
     if int(rec['widget'],16) and rec['type']==2:assert bytes(vm.u.mem_read(int(rec['param'],16)+0x2d,1))==b'\0',('mode0',rec)
    row['first_mode0_draw_calls']=list(vm.draw_calls);vm.draw_calls.clear()
    vm.call(0x182c000+bias,view,1)
    for rec in allocs:
     if int(rec['widget'],16) and rec['type']==2:assert bytes(vm.u.mem_read(int(rec['param'],16)+0x2d,1))==b'\1',('mode1',rec)
    row['later_mode1_draw_calls']=len(vm.draw_calls)
    row['real_helpers_executed']=all(a in vm.trace for a in (0x1b2ae4c,0x1bc3304))
    assert row['real_helpers_executed']
    # A cap equal to the first shell's raw size must trigger Sony's genuine
    # native size assertion (cmp uses strict <), proving cap check is live.
    check_cursor=MEM+0x1f0000;vm.w32(check_cursor,0)
    try:
     vm.call(0x181d3d4+bias,0x2b0,ARENA+0x10000,check_cursor,STUB+0xf1000,STUB+0xf2000)
    except Exception as ex:
     assert vm.u.reg_read(R.UC_ARM64_REG_PC)==0x35b858c+bias,ex
     row['native_capacity_assert_executed']=True
    else:raise AssertionError('native capacity check did not fire')
    assert all(a in vm.trace for a in (0x182b41c,0x181d3d4,0x181d318,0x1829360,0x18209d0,0x1884cd0,0x18901ec,0x182c000))
    row['native_allocator_executed']=True;row['native_create_executed']=True;row['first_update_mode_zero_executed']=True
    row['passed']=True
  except Exception as ex:
   row=dict(bias=hex(bias),layout=layout,passed=False,exception=repr(ex),unresolved=vm.failed,external_calls=vm.extcalls,recent=list(vm.recent)[-30:])
  rows.append(row)
report=dict(AP_sha256=hashlib.sha256(vm.im.data).hexdigest(),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),passed=all(r['passed']for r in rows),cases=rows,
 native_allocator_executed=all(r.get('native_allocator_executed',False)for r in rows),native_create_executed=all(r.get('native_create_executed',False)for r in rows),first_update_mode_zero_executed=all(r.get('first_update_mode_zero_executed',False)for r in rows),
 limitations=['Actual app native allocator, String/touch constructors, map getter, parameter init and view create execute; liveview shell low-level ctor/init are fixtures, size/cursor allocation and params remain real. Named external libObj/GUI calls remain fixtures.',
 'Per-widget draw callbacks are bounded fixtures; real view update loop and String mode-byte propagation execute. Mode0 still invokes drawing callbacks.',
 'External UX constructors are not equivalent to real libObj startup or font/backend validation.', 'Projection executes against actual allocated parameter map. No camera IO.'])
(HERE/'native_allocator429_verified.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(passed=report['passed'],AP_sha256=report['AP_sha256'],cases=[dict(bias=r['bias'],layout=r['layout'],passed=r['passed'],arena_used=r.get('arena_used'),first_mode0_draw_calls=len(r.get('first_mode0_draw_calls',[])))for r in rows])))
