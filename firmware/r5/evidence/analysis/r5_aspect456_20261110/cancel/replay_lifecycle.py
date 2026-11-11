#!/usr/bin/env python3
"""Actual Fn wheel, ordinary confirmation, retained cache and CAS boundaries."""
from pathlib import Path
import sys,json,struct,traceback
HERE=Path(__file__).resolve().parent
import replay_cancel as c
from unicorn.arm64_const import *
candidate=sys.argv[2] if len(sys.argv)>2 else 'candidate-f'
c.AP=HERE/candidate/'ap/appFw-NONINSTALLABLE.so';c.BUILD=HERE/candidate/'module'
checks=[];results=[]
def ck(ok,name):
 assert ok,name
 checks.append(name)
def init(r,i):
 r.call('r5_aspect_menu_commit',c.alias(i));r.u.mem_write(r.call(r.bias+0x2170958),c.p32(c.alias(i)))
 ck(r.call('r5_aspect_menu_get')==i,'initial visible %d'%i)
def saved(r):return struct.unpack('<4I',r.files['custom_aspect_v2.dat'])[2]
def pause(r,at):
 def stop():r.u.emu_stop()
 r.callbacks[r.bias+at]=stop
 for i,v in enumerate((c.P,0x20050000,0x0201000f)):r.putx(i,v)
 r.putx(30,c.STOP);r.u.reg_write(UC_ARM64_REG_SP,c.STACK+0x1f000)
 r.u.emu_start(r.bias+0x1a5e4b8,c.STOP,count=500000)
 ck(r.u.reg_read(UC_ARM64_REG_PC)==r.bias+at,'pause reaches '+hex(at))
 del r.callbacks[r.bias+at];return r.u.context_save()
def isolated(r,ctx,name,*args):
 # call uses top of main stack, so preserve entire stack (callback-independent).
 stack=bytes(r.u.mem_read(c.STACK,0x20000));v=r.call(name,*args)
 r.u.mem_write(c.STACK,stack);r.u.context_restore(ctx);return v
def resume(r,at,ctx):
 r.u.context_restore(ctx);r.u.emu_start(r.bias+at,c.STOP,count=500000)
 ck(r.u.reg_read(UC_ARM64_REG_PC)==c.STOP,'resume completes')
try:
 for bias in (0x4000000000,0x6000000000):
  r=c.Cancel(bias)
  for initial in range(8):
   init(r,initial);r.capture()
   r.call(bias+0x2175e7c,c.P)
   browsed=r.call('r5_aspect_menu_get');r.event()
   ck(r.call('r5_aspect_menu_get')==initial,'actual wheel MENU restores %d'%initial)
   ck(saved(r)==(initial if initial>=4 else 0),'actual wheel cancel saves initial')
   results.append(dict(kind='wheel',bias=hex(bias),initial=initial,browsed=browsed,after=initial))
  # Ordinary native return commits the browsed choice, not the capture.
  for initial in (0,4,7):
   init(r,initial);r.capture();r.call(bias+0x2175e7c,c.P)
   browsed=r.call('r5_aspect_menu_get')
   r.u.mem_write(r.call(bias+0x28a4df4),c.p32(1))
   r.call(bias+0x2173028,c.P,0x20050000)
   ck(r.call('r5_aspect_menu_get')==browsed,'ordinary return retains browsed choice')
   ck(saved(r)==(browsed if browsed>=4 else 0),'ordinary return saves browsed choice')
  # Cache follows native helper lifetime, not a synthetic transaction stack.
  for initial in (0,4,7):
   init(r,initial);r.call(bias+0x2adfd3c)
   cache=r.u32(bias+c.CACHE);side=r.u32(r.sy['r5_aspect_saved_selection'])
   for browse in (1,5,3):
    r.call('r5_aspect_menu_set',browse);before=r.token()
    r.call(bias+0x2adfd5c)
    ck(r.call('r5_aspect_menu_get')==initial,'repeated native restore preserves cached private ID')
    ck(r.token()!=before,'restore publishes fresh epoch')
    ck(r.u32(bias+c.CACHE)==cache and r.u32(r.sy['r5_aspect_saved_selection'])==side,'native/private cache both retained')
  # Empty capture must not manufacture a private restoration.
  r.u.mem_write(r.sy['r5_aspect_saved_selection'],c.p32(0));r.call('r5_aspect_menu_set',7);token=r.token()
  r.call(bias+0x2adfd5c);ck(r.token()==token,'uncaptured helper does not publish')
  # ABI: both helpers preserve X19..X29 and SP, including trampoline frames.
  for entry in (0x2adfd3c,0x2adfd5c):
   values=[0xabc000+i for i in range(19,29)]
   for i,v in zip(range(19,29),values):r.putx(i,v)
   r.call(bias+entry)
   ck([r.x(i) for i in range(19,29)]==values,'helper callee-saved X19-X28')
   ck(r.x(29)==0 and r.u.reg_read(UC_ARM64_REG_SP)==c.STACK+0x1f000,'helper X29 and SP preserved')
  # A different descriptor callback receives only its original low alias.
  foreign=[];cb=c.FIX+0x8100
  r.callbacks[cb]=lambda:(foreign.append(r.x(0)),r.ret())
  token=r.token();r.call('r5_aspect_restore_commit',(token<<32)|0x335,cb)
  ck(foreign==[0x335] and r.token()==token,'foreign callback unchanged')
  # A newer private publication while original restore executes must survive.
  init(r,4);r.capture();r.call('r5_aspect_menu_set',5)
  ctx=pause(r,0x2adfd60);isolated(r,ctx,'r5_aspect_menu_set',7)
  resume(r,0x2adfd60,ctx)
  ck(r.call('r5_aspect_menu_get')==7,'newer private publication during native restore wins')
  # Between alias return and restored commit: same ID/new epoch must also win.
  for initial in (0,4):
   for newer in (0,4,5,7):
    init(r,initial);r.capture();r.call(bias+0x1bd9318,c.alias(6))
    ctx=pause(r,0x1bd64d4)
    isolated(r,ctx,'r5_aspect_menu_set',newer)
    token=r.token();commits=len([x for x in r.calls if x[0]=='native_commit'])
    resume(r,0x1bd64d4,ctx)
    ck(r.token()==token,'stale restored commit cannot overwrite newer epoch')
    ck(r.call('r5_aspect_menu_get')==newer,'newer choice retained')
    ck(len([x for x in r.calls if x[0]=='native_commit'])==commits,'stale restore commit is not invoked')
    results.append(dict(kind='cross_epoch',initial=initial,newer=newer,bias=hex(bias),token=token))
 receipt=dict(passed=True,checks=checks,cases=results)
except Exception as e:
 receipt=dict(passed=False,error=repr(e),traceback=traceback.format_exc(),checks=checks,cases=results,recent=r.recent,trace=r.trace)
out=HERE/(sys.argv[1] if len(sys.argv)>1 else 'lifecycle-e.json');assert not out.exists();out.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k not in ('checks','cases','recent','trace')}))
if not receipt['passed']:raise SystemExit(1)
