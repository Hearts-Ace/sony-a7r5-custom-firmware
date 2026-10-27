"""427 release gate: compiled custom gates + native constructors/helpers/ABI.

Offline local files only. The graphics view/backend services remain explicit
fixtures; no device is connected and no hardware acceptance is claimed.
"""
from pathlib import Path
import sys,json,hashlib
HERE=Path(__file__).resolve().parent;CAND=HERE.parent;ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(HERE),str(CAND)]
from replay_page425 import PageVM,RAM,X,R
class LifecycleVM(PageVM):
 def __init__(self,bias):
  self.view_args=[];self.query_calls=[];self.check_private_input=False;self.native_entries={}
  super().__init__(bias)
  self.context=RAM+0x340000;self.contextvt=self.context+0x100
  # Explicit equivalent field getter service; the actual native getter runs.
  self.w64(self.context,self.contextvt);self.w64(self.contextvt+0x38,0x1cbfc9c+bias);self.w32(self.context+8,0x1234)
  self.callbacks[RAM+0x138]=0x38;self.w64(self.vvt+0x38,RAM+0x138)
 def pagehook(self,u,pc,size,arg):
  at=pc-self.bias;a=[u.reg_read(r)for r in X[:8]]
  if self.check_private_input and at in [0x1a6d8cc,0x2207930,0x220844c]:raise AssertionError(('private input entered native Look path',hex(at)))
  if at in [0x1d2e2f0,0x1cbfb80,0x22083ec,0x1b2ae4c,0x1bc3304]:self.native_entries[at]=self.native_entries.get(at,0)+1
  # Remove inherited native ctor/dtor/helper fixtures completely.
  if at in [0x1d2e2f0,0x1cbfb80,0x22083ec,0x1b2ae4c,0x1bc3304]:return
  if pc in self.callbacks:
   self.view_args.append(dict(offset=hex(self.callbacks[pc]),args=[hex(x)for x in a]))
   if self.callbacks[pc]==0x38:self.query_calls.append(a[1]);self.ret(0);return
  super().pagehook(u,pc,size,arg)
 def open(self):
  self.call(self.sy['r5_filter_parent_presenter425'],0,self.parentview,self.context,0,0x2d7,0)
  c=self.call(self.sy['r5_filter_controller425'],0,self.manager,self.context,0,0,0)
  p=self.call(self.sy['r5_filter_presenter425'],0,self.view,self.context,0,0xd9,0)
  self.controller=c;self.presenter=p;return c,p
 def manager_layout(self,layout):
  self.w64(self.manager+0x338,self.presenter)
  self.custom[0x1e98444+self.bias]=lambda a:self.ret(layout)
  self.custom[0x1ec4488+self.bias]=lambda a:self.ret(0)
  return self.native(0x1ec4908,self.manager,0,0)
 def private_inputs(self):
  before=len(self.calls);self.check_private_input=True
  try:
   for ev in [0x2010000,0x2010003,0x201000c,0x2030001,0x3010002]:self.event(ev)
  finally:self.check_private_input=False
  assert not any(x[0]=='request'for x in self.calls[before:])
def main():
 rows=[]
 for bias in [0,0x40000000]:
  vm=LifecycleVM(bias);c,p=vm.open();vt=vm.q(p)
  assert vm.q(vt+0x30)==0x1cbfbb0+bias and vm.q(vt+0x40)!=0x1d0a970+bias
  assert int.from_bytes(vm.u.mem_read(c+0x300,2),'little')==0x1234
  assert all(a in vm.trace for a in [0x1d2e2f0,0x1b2b690,0x1af57c0,0x1af3d78,0x1b2ae4c,0x1bc3304])
  helpers=[dict(offset=hex(o),count648=vm.d(p+o+0x648),count64c=vm.d(p+o+0x64c),field650=vm.q(p+o+0x650))for o in [0x4d30,0x5388]]
  initial_updates=[a for a in vm.view_args if a['offset']=='0x20'];assert len(initial_updates)==1 and initial_updates[0]['args'][1]=='0x0'
  old=vm.d(p+8);vm.calls.clear();vm.native(0x1e1e3b4,p);assert vm.d(p+8)==old and not vm.calls
  # Exercise the full native query's widget loop as well as the pi<=2 guard.
  vm.w32(p+0x59e8,3);vm.native(0x1e1e3b4,p);assert vm.d(p+8)==old and len(vm.query_calls)==34 and not vm.calls;vm.w32(p+0x59e8,0)
  layouts=[]
  for target,expect in [(1,'recreate'),(2,'same_class'),(0,'recreate')]:
   vm.calls.clear();ret=vm.manager_layout(target);assert ret==1 and vm.d(p+8)==target
   if expect=='recreate':assert ('view',0x18)in vm.calls and ('view',0x10)in vm.calls
   else:assert ('view',0x60)in vm.calls and ('view',0x18)not in vm.calls
   assert 0x1d0a970 not in vm.trace and 0x220844c not in vm.trace
   assert all(typ in [2,20]for i,typ in vm.created if i not in [0,1]) and all(i!=2 for i,t in vm.created)
   layouts.append(dict(target=target,kind=expect,native_manager_returned=ret,view_calls=vm.calls.copy()))
  vm.w32(vm.menu_pid,0x14c);vm.private_inputs();vm.w32(vm.menu_pid,0x635)
  # Enter closing through the real custom handler, then try user input again.
  vm.event(0x201000f);vm.private_inputs()
  before_frees=len(vm.frees);before_native=dict(vm.native_entries);d1p=vm.q(vm.q(p));d1c=vm.q(vm.q(c));d0p=vm.q(vm.q(p)+8);d0c=vm.q(vm.q(c)+8)
  vm.call(d1p,p);vm.call(d1c,c);vm.call(d1p,p);vm.call(d0p,p);vm.call(d1c,c);vm.call(d0c,c)
  assert len(vm.frees)==before_frees==0 and not vm.allocations
  assert vm.native_entries[0x1cbfb80]-before_native.get(0x1cbfb80,0)==1 and vm.native_entries[0x22083ec]-before_native.get(0x22083ec,0)==1
  for count in [2,3]:
   c2,p2=vm.open();assert(c2,p2)==(c,p);vm.cleanup()
   assert vm.native_entries[0x1cbfb80]-before_native.get(0x1cbfb80,0)==count and vm.native_entries[0x22083ec]-before_native.get(0x22083ec,0)==count
  assert not vm.allocations and not vm.frees
  assert all(a in vm.trace for a in [0x1cbfb80,0x22083ec,0x1af1bc0,0x1b2b9c8])
  rows.append(dict(bias=hex(bias),compiled_custom_gates=True,full_native_controller_ctor=True,real_helpers=helpers,context_field_getter_service=True,first_view_update_argument=initial_updates[0]['args'][1],native_query_preserves_layout=True,native_query_full_widget_loop_count=len(vm.query_calls),native_manager_layouts=layouts,native_original_layout_and_param9_not_reached=True,mid_change_and_closing_inputs_isolated=True,full_native_dtor=True,allocations=vm.allocations,frees=vm.frees,static_objects_reused=True,each_object_cleaned_once_per_lifetime=True,no_OSAL_allocation_or_free=True))
 report=dict(passed=True,AP_sha256=hashlib.sha256((CAND/'ap/appFw.so').read_bytes()).hexdigest(),cases=rows,limits=['Compiled427 custom controller/presenter gates execute with complete original controller constructor/base/control helper/profile setter, both presenter helpers, and original controller/presenter destructors; none are fixture-substituted.','Native scene-manager loop/getters/VT+40 dispatch and real original bounds consumer/VT+30 query execute. Product orientation resolver and preparation helper are bounded fixtures.','Native graphics view/widget creation, display backend, OSAL heap, mutex/model/IO command services and parent presentation capture remain explicit PageVM fixtures. Parent selected-value path is covered separately by page425_replay.json.','UI context VT+38 uses actual native field getter1cbfc9c on a bounded context object; the concrete camera context class has not been identified. No camera crash dump, physical LCD/SD/ISP or hardware acceptance.'])
 (HERE/'native_lifecycle429_verified.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('PASS native lifecycle',len(rows),report['AP_sha256'])

if __name__=="__main__": main()
