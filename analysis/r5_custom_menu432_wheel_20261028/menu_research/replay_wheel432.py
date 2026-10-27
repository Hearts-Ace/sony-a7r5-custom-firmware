"""Compiled wheel input + native normalization, with explicit worker/UI fixtures.

The old page is replayed as a regression witness at the original D9 mutation
helper. No camera, filesystem worker, LCD or ISP frame is exercised here.
"""
from pathlib import Path
import hashlib,json,sys
HERE=Path(__file__).resolve().parent;CAND=HERE.parent;ROOT=CAND.parents[1]
sys.path[:0]=[str(HERE),str(CAND),str(CAND/'style_evidence')]
import replay_page425 as page
from replay_page425 import PageVM,RAM,X
from replay_candidate_list431 import publication_offsets,seed_names
from unicorn import UC_HOOK_CODE

class WheelVM(PageVM):
 def __init__(self,bias,old=False):
  prior=page.CAND
  if old:page.CAND=ROOT/'analysis/r5_custom_menu431_interaction_20261027'
  try:super().__init__(bias)
  finally:page.CAND=prior
  self.escape=[];self.guard=False
  self.u.hook_add(UC_HOOK_CODE,self.wheelhook)
 def wheelhook(self,u,pc,size,arg):
  at=pc-self.bias
  if at in (0x1a6d8cc,0x2207480,0x2207fe0,0x2207930,0x220844c,0x1b2bffc):
   self.escape.append(hex(at))
   if self.guard:raise AssertionError(('wheel escaped private page',hex(at)))
  # End the old-page witness at the first native mutation helper. Its side
  # effects are not faked as a successful custom application.
  if at in (0x2207fe0,0x1b2bffc):self.ret(1)

def snap(vm):
 param=vm.q(vm.pmap+9*16+8)
 rid=vm.d(vm.q(vm.pmap+11*16+8)+0x30)
 available=[0]+[i for i in range(1,13) if vm.mask&(1<<(i-1))]
 assert rid==0x02ff4400+vm.selected,(rid,vm.selected)
 assert vm.d(param+0xd38)==available.index(vm.selected)
 assert vm.d(param+0x830+4*available.index(vm.selected))==0x02ff4300+vm.selected
 return dict(selected=vm.selected,native_list_focus=vm.d(param+0xd38),full_name_resource=hex(rid))

def main():
 rows=[];old_rows=[];offsets=publication_offsets()
 for bias in (0,0x40000000):
  for event in (0x2050000,0x2050001,0x2050004,0x2050005):
   vm=WheelVM(bias,True);vm.open();vm.calls.clear();before=vm.d(vm.q(vm.pmap+11*16+8)+0x30)
   vm.event(event)
   assert '0x1a6d8cc' in vm.escape and not any(r[0]=='request' for r in vm.calls)
   assert vm.d(vm.q(vm.pmap+11*16+8)+0x30)==before
   old_rows.append(dict(bias=hex(bias),event=hex(event),native_escape=vm.escape,private_projection_unchanged=True))
  for layout in (0,1):
   for mask in (0xfff,(1<<1)|(1<<8),0,1<<11):
    vm=WheelVM(bias);vm.mask=mask;seed_names(vm,mask,offsets);c,p=vm.open();vm.guard=True
    if layout:vm.call(vm.q(vm.q(p)+0x40),p,layout)
    vm.calls.clear();available=[0]+[i for i in range(1,13) if mask&(1<<(i-1))]
    states=[]
    # Standard wheel events arrive once per native dispatch. The private page
    # follows the original handler's single-step contract regardless of data.
    for i in range(len(available)+3):
     vm.w32(RAM+0x820,0x7fffffff);vm.w32(RAM+0x82c,i*37)
     vm.event(0x2050000 if i%2==0 else 0x2050004)
     assert vm.selected==available[min(i+1,len(available)-1)]
     states.append(snap(vm))
    for i in range(len(available)+3):
     vm.event(0x2050001 if i%2==0 else 0x2050005)
     assert vm.selected==available[max(len(available)-2-i,0)]
     states.append(snap(vm))
    before=sum(r[0]=='request' for r in vm.calls)
    for event in (0x2050002,0x2050003,0x2050006,0x2050fff):vm.event(event)
    assert sum(r[0]=='request' for r in vm.calls)==before
    vm.event(0x2010003);snap(vm);vm.event(0x2050001);snap(vm)
    vm.event(0x201000c)
    assert vm.calls.count(('pop',0xd9))==1
    before=len(vm.calls)
    for event in (0x2050000,0x2050001,0x2050004,0x2050005):vm.event(event)
    assert len(vm.calls)==before and not vm.escape
    rows.append(dict(bias=hex(bias),layout=layout,mask=hex(mask),mode='bidirectional_burst_boundary_mixed_closing',states=states,private_requests=sum(r[0]=='request' for r in vm.calls),no_original_look_setter=True))
  for mode in ('pending','failure','stale_serial','wrong_mid','stock'):
   vm=WheelVM(bias);vm.open();vm.guard=True;vm.calls.clear()
   if mode=='pending':
    vm.mode='timeout';vm.event(0x2050000);count=sum(r[0]=='request' for r in vm.calls)
    vm.event(0x2050004);assert sum(r[0]=='request' for r in vm.calls)==count
    vm.mode='success';vm.busy=0;vm.event(0x2050000);assert vm.selected==2;snap(vm)
   elif mode=='failure':
    vm.mode='failure';vm.event(0x2050000);assert vm.selected==0
    assert vm.d(vm.q(vm.pmap+11*16+8)+0x30)==0x02ff4401
    vm.mode='success';vm.event(0x2050001);assert vm.selected==0;snap(vm)
   elif mode=='stale_serial':
    vm.mode='timeout';vm.event(0x2050000);vm.sequence+=1;count=sum(r[0]=='request' for r in vm.calls)
    vm.event(0x2050004);assert sum(r[0]=='request' for r in vm.calls)==count and vm.selected==0
   elif mode=='wrong_mid':
    vm.w32(vm.menu_pid,0x14c)
    for ev in (0x2050000,0x2050001,0x2050004,0x2050005):vm.event(ev)
    assert not any(r[0]=='request' for r in vm.calls)
   else:
    vm.guard=False
    # An unrelated native controller still delegates to original dispatcher.
    other=RAM+0x2f0000;vm.w32(other+0x178,0xd9);vm.w64(other+0x180,vm.manager)
    vm.call(vm.q(vm.q(vm.controller)+0x10),other,RAM+0x820,0x2050000)
    assert '0x1a6d8cc' in vm.escape
   rows.append(dict(bias=hex(bias),mode=mode,selected=vm.selected,no_original_look_setter=mode!='stock'))
 report=dict(passed=True,version='4.32',AP_sha256=hashlib.sha256((CAND/'ap/appFw.so').read_bytes()).hexdigest(),cases=rows,baseline431=old_rows,
  wheel_updates_focus_and_preview=True,same_request_path=True,no_original_look_setter=True,batched_steps_verified=True,
  batch_contract='Repeated native wheel events each advance one available item, clamped at boundaries. No unverified message count is interpreted.',
  limits=['Worker completion and view painting are explicit fixtures; preview flag denotes submission to the existing worker, not a physical preview-frame observation.','Native normalization and old D9 dispatch/handlers execute. Input hardware, LCD rendering, camera timing and frame/JPG await user acceptance.'],camera_io=False)
 (HERE/'wheel432_verified.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(dict(passed=True,cases=len(rows),baseline431=len(old_rows),AP_sha256=report['AP_sha256'])))
if __name__=='__main__':main()
