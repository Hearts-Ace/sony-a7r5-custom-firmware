"""Execute native view::create_screen against the compiled private page styles.

Widget/param allocation and UX backends are explicit fixtures. The real native
type/mask dispatcher, name-offset selection, map population and style parameter
initialization execute, followed by the compiled private projection/text bridge.
No camera or filesystem device I/O.
"""
from pathlib import Path
import hashlib,json,runpy,struct,sys
HERE=Path(__file__).resolve().parent;CAND=HERE.parent;ROOT=CAND.parents[1]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(CAND),str(HERE)]
# Import the shared page VM without executing its separate 26-case suite.
scope=runpy.run_path(str(HERE/'replay_page425.py'),run_name='native_view_import')
PageVM=scope['PageVM'];X=scope['X'];R=scope['R']
from unicorn import UC_HOOK_CODE
NATIVE_VIEW=0x30000000;HEAP=0x30400000;STUB=0x30f00000
rows=[]
for bias in (0,0x40000000):
 for layout in (0,1):
  vm=PageVM(bias);c,p=vm.open()
  if layout:vm.call(vm.q(vm.q(p)+0x40),p,layout)
  style=vm.styles;masks=vm.masks
  vm.u.mem_map(NATIVE_VIEW,0x1000000)
  vm.w64(NATIVE_VIEW+0x3e98,HEAP);vm.w32(NATIVE_VIEW+0x3ea0,0x800000)
  dispatch={}
  for typ in range(150):
   dispatch.setdefault(vm.q(0x5020be8+bias+typ*8),[]).append((typ,False))
   dispatch.setdefault(vm.q(0x50210e0+bias+typ*8),[]).append((typ,True))
  allocations=[];widget_params={};captured_names=[]
  def hook(u,pc,size,arg):
   a=[u.reg_read(r)for r in X[:8]]
   if pc in dispatch:
    index=len(allocations);typ=vm.d(style+index*52);only=bool(masks[index])
    assert (typ,only) in dispatch[pc],(index,typ,only,hex(pc))
    # Real create_screen assembled this ctor param from name base+offset[index].
    nameptr=vm.q(a[4]+8)
    name=bytes(u.mem_read(nameptr,128)).split(b'\0')[0].decode()
    captured_names.append(name)
    obj=HEAP+0x10000+index*0x2000;param=obj+0x400
    u.mem_write(param,bytes(0x1000));u.mem_write(param+0x2c,b'\1')
    allocations.append(dict(index=index,type=typ,parameter_only=only,name=name,param=param))
    if only:vm.ret(param);return
    vm.w64(obj,STUB);widget_params[obj]=param
    vm.w64(STUB+0x140,STUB+0x800);vm.w64(STUB+0x148,STUB+0x804)
    vm.w64(STUB+0x18,STUB+0x808);vm.w64(STUB+0x30,STUB+0x80c)
    vm.ret(obj);return
   if pc==STUB+0x800:vm.ret(widget_params[a[0]]);return
   if pc in (STUB+0x804,STUB+0x808,STUB+0x80c):vm.ret();return
  vm.u.hook_add(UC_HOOK_CODE,hook)
  # Only ordinary memory is passed to the real native function. No SD/device.
  maskptr=STUB+0x1000;vm.u.mem_write(maskptr,masks)
  vm.call(0x182b41c+bias,NATIVE_VIEW,0xd9,style,34,layout,maskptr,0x4060b40+bias,0x4060ab8+bias)
  assert len(allocations)==34
  actual=[]
  for rec in allocations:
   i=rec['index'];assert vm.d(NATIVE_VIEW+0x10+16*i)==rec['type']
   assert vm.q(NATIVE_VIEW+0x18+16*i)==rec['param']
   if not rec['parameter_only']:actual.append((i,rec['type']))
  assert all(i not in (2,3,4,5,6,7,8,10,14,15,29,30,31,32,33)for i,t in actual),actual
  assert all(t in (0x6a,0x6b,2,0x14,0x1c)for i,t in actual),actual
  # The compiled projection must accept the map produced by the actual native
  # type dispatcher; an invented map cannot make the test pass.
  vm.w64(p+0x48,NATIVE_VIEW+0x10)
  vm.call(vm.q(vm.q(p)+0x10),p,1)
  update=vm.q(NATIVE_VIEW+0x18+14*16)
  assert vm.d(update+0x30)==0
  assert bytes(vm.u.mem_read(update+0x2c,1))==b'\0'
  assert all(i not in (14,15)for i,t in actual)
  full=vm.q(NATIVE_VIEW+0x18+11*16)
  assert vm.d(full+0x30)==0x02ff4400
  assert bytes(vm.u.mem_read(full+0x2c,1))==b'\1'
  vm.events.clear()
  vm.call(vm.sy['r5_filter_menu_name_draw'],STUB+0x3000,vm.d(full+0x30))
  assert ('name_char','关闭') in vm.events,vm.events
  # No primitive for the native right-side adjustments survives construction.
  assert [i for i,t in actual if t==2]==[11,12,13]
  rows.append(dict(bias=hex(bias),layout=layout,actual_constructed_widgets=actual,
   native_dispatch_entries=allocations,update_resource='0x0',
   update_visible_param=False,update_widgets_absent=True,full_resource='0x02ff4400',full_text_bridge='关闭',right_adjustment_widgets_absent=True,
   native_create_executed=True,compiled_project_accepted_native_param_map=True,
   name_offsets_resolved=captured_names))
report=dict(passed=True,version='4.34',AP_sha256=hashlib.sha256((CAND/'ap/appFw.so').read_bytes()).hexdigest(),
 cases=rows,native_create_entry='0x182b41c',native_create_vtable_slot='0x57830a8',
 source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 limitations=['Native widget and parameter allocator calls are fixtures; native create_screen dispatch/map/style initialization executes.',
 'Private page entry services/controller ctor and UX backend remain fixtures in the imported page VM.',
 'Text bridge executes compiled custom resource to UTF8 setter; no actual font rasterization, LCD geometry/occlusion, touch hit testing or GUI event scheduling.'],camera_io=False)
(HERE/'native_view426_verified.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(passed=True,AP_sha256=report['AP_sha256'],cases=len(rows))))
