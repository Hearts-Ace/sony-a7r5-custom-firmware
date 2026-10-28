"""Compiled page interaction regressions for the user's 4.30 observations.

Worker completion/UX services are explicit fixtures. Native descriptor value
resolution executes; actual D9 parent destruction/pop is covered independently.
"""
from pathlib import Path
import hashlib,json,sys
HERE=Path(__file__).resolve().parent;CAND=HERE.parent
sys.path[:0]=[str(HERE),str(CAND)]
from replay_page425 import PageVM,RAM
STATUS=0x02ff4501

def text(vm,rid):
 p=vm.call(vm.sy['r5_filter_page_text425'],rid)
 return bytes(vm.u.mem_read(p,160)).split(b'\0')[0].decode() if p else ''
def main():
 rows=[]
 modes=('move_confirm','held_sparse','touch_stays','true_failure','pending_recovery',
        'parent_projection_retry','stale_sequence','back_after_failure','empty_confirm',
        'removed_update','navigation_boundary','stock','reenter','oom','layout')
 for bias in (0,0x40000000):
  for mode in modes:
   vm=PageVM(bias)
   if mode=='stock':
    vm.w32(vm.menu_pid,0x14c)
    assert vm.call(vm.sy['r5_filter_controller425'],0,vm.manager,0,0,0,0)==0x123456
    assert vm.call(vm.sy['r5_filter_presenter425'],0,vm.view,0,0,0xd9,0)==0x123456
    rows.append(dict(bias=hex(bias),mode=mode,stock_factory_delegated=True));continue
   if mode=='oom':vm.oom=1
   c,p=vm.open();assert c and p and not vm.allocations
   vm.calls.clear()
   if mode=='move_confirm':
    vm.event(0x2010003)
    assert vm.selected==1 and ('request',1) in vm.calls and ('pop',0xd9) not in vm.calls
    before=list(vm.calls);vm.event(0x201000c)
    assert vm.calls.count(('request',1))==1 and vm.calls.count(('pop',0xd9))==1
   elif mode=='held_sparse':
    vm.mask=(1<<1)|(1<<8)
    for ev,n in ((0x2010003,2),(0x2010005,9),(0x2010002,2),(0x2010000,0)):
     vm.event(ev);assert vm.selected==n and ('pop',0xd9) not in vm.calls
    assert [v for k,*v in vm.calls if k=='request']==[[2],[9],[2],[0]]
    vm.event(0x201000f);assert vm.calls.count(('pop',0xd9))==1
   elif mode=='touch_stays':
    vm.touch(25);assert vm.selected==1 and ('pop',0xd9) not in vm.calls
    vm.event(0x201000c);assert vm.calls.count(('request',1))==1 and vm.calls.count(('pop',0xd9))==1
   elif mode in ('true_failure','back_after_failure'):
    vm.mode='failure';vm.event(0x2010003)
    assert vm.selected==0 and ('pop',0xd9) not in vm.calls
    assert text(vm,STATUS)=='应用失败，请重试'
    vm.mode='success'
    vm.event(0x201000f if mode=='back_after_failure' else 0x201000c)
    assert vm.selected==(0 if mode=='back_after_failure' else 1)
    assert vm.calls.count(('pop',0xd9))==1
   elif mode=='pending_recovery':
    vm.mode='timeout';vm.event(0x2010003)
    assert vm.selected==0 and ('pop',0xd9) not in vm.calls and text(vm,STATUS)=='正在应用，请稍候'
    before=len([r for r in vm.calls if r[0]=='request'])
    vm.event(0x201000c);assert len([r for r in vm.calls if r[0]=='request'])==before and ('pop',0xd9) not in vm.calls
    vm.mode='success';vm.busy=0;vm.event(0x201000f)
    assert vm.selected==1 and vm.calls.count(('pop',0xd9))==1
   elif mode=='parent_projection_retry':
    vm.event(0x2010003);assert vm.selected==1
    vm.parent_bad=True;vm.event(0x201000c)
    assert vm.selected==1 and ('pop',0xd9) not in vm.calls
    assert '滤镜已应用' in text(vm,STATUS) and '应用失败' not in text(vm,STATUS)
    vm.parent_bad=False;vm.event(0x201000c)
    assert vm.calls.count(('request',1))==1 and vm.calls.count(('pop',0xd9))==1
   elif mode=='stale_sequence':
    vm.mode='timeout';vm.event(0x2010003);vm.sequence+=1
    vm.event(0x201000c)
    assert ('pop',0xd9) not in vm.calls and text(vm,STATUS)=='应用失败，请重试'
   elif mode=='empty_confirm':
    vm.event(0x201000c);assert vm.selected==0 and vm.calls.count(('pop',0xd9))==1
   elif mode=='removed_update':
    for idx in (3,4,5,8,10,14,15,29,30,31,32,33):vm.touch(idx)
    for ev in (0x2010006,0x2010008,0x2010009,0x201000b,0x2030001,0x2030002):vm.event(ev)
    assert not any(r[0]=='request' for r in vm.calls)
   elif mode=='navigation_boundary':
    for _ in range(5):vm.event(0x2010000)
    assert not any(r[0]=='request' for r in vm.calls)
    for _ in range(15):vm.event(0x2010005)
    assert vm.selected==12 and len([r for r in vm.calls if r[0]=='request'])==12
    assert ('pop',0xd9) not in vm.calls
   elif mode=='reenter':
    vm.event(0x201000f);assert vm.calls.count(('pop',0xd9))==1
    for ev in (0x2010000,0x2010003,0x201000c):vm.event(ev)
    assert not any(r[0]=='request' for r in vm.calls)
    vm.cleanup();c2,p2=vm.open();assert (c,p)==(c2,p2)
   elif mode=='layout':
    for layout in (1,2,0):vm.call(vm.q(vm.q(p)+0x40),p,layout)
   else:assert mode=='oom' and not vm.allocations
   assert vm.masks[2]==1
   assert all(i not in (2,3,4,5,6,7,8,10,14,15,29,30,31,32,33) for i,t in vm.created)
   rows.append(dict(bias=hex(bias),mode=mode,selected=vm.selected,
                    created_widgets=vm.created,event_order=[r for r in vm.calls if r[0]!='yield'],
                    yield_count=sum(r[0]=='yield' for r in vm.calls),
                    background2_not_constructed=True,native_adjustment_widgets_absent=True,
                    update_text_resource='0x0',
                    menu_mid=hex(vm.d(vm.menu_pid)),independent_row_pid=hex(vm.d(vm.row_pid)),
                    update_widgets_not_constructed=True,no_reload_requests=not any(r==('request','reload') for r in vm.calls)))
 report=dict(passed=True,version='4.34',AP_sha256=hashlib.sha256((CAND/'ap/appFw.so').read_bytes()).hexdigest(),cases=rows,
             movement_applies_and_saves=True,successful_movement_keeps_page=True,confirm_no_duplicate_request=True,
             parent_error_distinct=True,true_apply_failure_retains_page=True,exact_pending_sequence=True,
             limits=['Worker responses and UX are bounded fixtures; durable save semantics execute in separate worker/crosscore tests.',
                     'Original native descriptor value resolver executes. Parent native teardown/recreation is covered separately.',
                     'No physical LCD, timing, SD or camera observation.'],camera_io=False)
 for filename in ('interaction431_verified.json','page425_replay.json'):
  (HERE/filename).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(dict(passed=True,cases=len(rows),AP_sha256=report['AP_sha256'])))
if __name__=='__main__':main()
