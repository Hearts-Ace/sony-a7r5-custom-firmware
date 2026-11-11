#!/usr/bin/env python3
"""Independent candidate-d Fn cancel replay. All outputs stay in cancel/."""
from pathlib import Path
import sys,struct,json,hashlib,traceback
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent/'integration'),str(HERE.parent/'ap')]
from replay_final_ap import FinalAP
from replay_ap import FIX,STACK,STOP,p32,p64
from unicorn.arm64_const import *
AP=HERE.parent/'integration/ap-candidate-d/appFw-NONINSTALLABLE.so'
BUILD=HERE.parent/'integration/compile-guide-d'
if len(sys.argv)>2:
 AP=HERE/sys.argv[2]/'ap/appFw-NONINSTALLABLE.so';BUILD=HERE/sys.argv[2]/'module'
P=0x20020000;HEAD=0x7ef9290;VEC=0x5992160;CACHE=0x8410778
class Cancel(FinalAP):
 def __init__(self,bias):
  super().__init__(AP,BUILD,bias);self.u.mem_map(0x20000000,0x200000)
  self.trace=[];self.nextalloc=0x20080000;self.aliases=[];self.recent=[]
  b=bias;self.desc=b+0x586b990
  self.call('r5_aspect_menu_init')
  # Native generic accessor's descriptor map membership is an explicit fixture.
  self.u.mem_write(FIX+0x9000,p64(self.desc))
  self.callbacks[b+0x1bd906c]=lambda:self.ret(1)
  self.callbacks[b+0x1bd90c4]=lambda:self.ret(FIX+0x9000)
  for a in (0x2542a30,0x2542a40,0x252d80c,0x252c870,0x1b2bb88,0x2170ca8,0x3694f64,0x16d9870):self.callbacks[b+a]=lambda:self.ret()
  for a in (0x1bcf268,0x1c5febc,0x24f092c):self.callbacks[b+a]=lambda:self.ret(0)
  self.callbacks[b+0x1bd9f98]=lambda:self.ret(0x20040000)
  self.callbacks[b+0x1bcfffc]=lambda:self.ret(1)
  # Original vtable policy callback and parent/key map services.
  vt=self.u64(b+0x591f9a8)+16
  self.callbacks[self.u64(vt+520)]=lambda:self.ret(1)
  self.callbacks[b+0x16dc130]=self.allocate
  self.callbacks[b+0x16d9770]=self.memcpy
  self.callbacks[b+0x16d95f0]=self.memset
  self.callbacks[b+0x16db260]=self.link
  self.callbacks[b+0x16dabf0]=self.unlink
  mapping=self.u64(b+0x593fbd8);header=mapping+8;node=0x20030000
  self.u.mem_write(header+8,p64(node));self.u.mem_write(node+8,p64(header))
  self.u.mem_write(node+32,p32(33)+p32(33))
  self.u.mem_write(b+HEAD,p64(b+HEAD)*2+p64(0))
  self.u.mem_write(b+0x74e95c0,p64(0x20060000)+p64(1))
  self.u.mem_write(self.call(b+0x2170928),p32(33));self.u.mem_write(P+772,p32(33))
 def call(self,name,*args):
  super().call(name,*args);return self.x(0)
 def setter(self):
  super().setter();self.u.mem_write(self.bias+0x7f1cc28,p32(self.native))
 def commit(self):
  alias=self.x(0);assert 126<=alias<=129
  self.native=alias-126;self.u.mem_write(self.bias+0x7f1cc20,p32(self.native));self.u.mem_write(self.bias+0x7f1cc28,p32(self.native))
  super().commit()
 def allocate(self):
  p=self.nextalloc;self.nextalloc+=(self.x(0)+127)&~127;self.ret(p)
 def memcpy(self):
  if self.x(2):self.u.mem_write(self.x(0),bytes(self.u.mem_read(self.x(1),self.x(2))))
  self.ret(self.x(0))
 def memset(self):
  if self.x(2):self.u.mem_write(self.x(0),bytes([self.x(1)&255])*self.x(2))
  self.ret(self.x(0))
 def link(self):
  n,h=self.x(0),self.x(1);prev=self.u64(h+8)
  self.u.mem_write(n,p64(h)+p64(prev));self.u.mem_write(prev,p64(n));self.u.mem_write(h+8,p64(n));self.ret()
 def unlink(self):
  n=self.x(0);nxt,prev=self.u64(n),self.u64(n+8)
  self.u.mem_write(prev,p64(nxt));self.u.mem_write(nxt+8,p64(prev));self.ret()
 def hook(self,u,address,size,data):
  at=address-self.bias
  self.recent.append(hex(at));self.recent=self.recent[-30:]
  if at in (0x21714b0,0x1bd6528,0x1bd645c,0x1bcb1ac,0x252e208,0x2adfd3c,0x2adfd5c,0x1bc50ec,0x1bc5038,0x1bc8578,0x1bc49c8,0x1bcb550,0x1bd5478,0x24f0964,0x1bd9318,0x1bd924c,0x2175e7c,0x2173028,0x2172ed0,0x1bd733c,0x1bcabe0,0x1a5e4b8):self.trace.append({'at':hex(at),'x0':self.x(0),'x1':self.x(1)})
  if at==0x1bd64cc:self.aliases.append(self.x(0)&0xffffffff)
  super().hook(u,address,size,data)
 def capture(self):
  self.u.reg_write(UC_ARM64_REG_X20,P);self.u.reg_write(UC_ARM64_REG_SP,STACK+0x1f000);self.u.reg_write(UC_ARM64_REG_X29,STACK+0x1f000)
  self.u.emu_start(self.bias+0x2176c10,self.bias+0x2176bb4,count=500000)
  assert self.u.reg_read(UC_ARM64_REG_PC)==self.bias+0x2176bb4
 def event(self):return self.call(self.bias+0x1a5e4b8,P,0x20050000,0x0201000f)
def alias(i):return 126+i if i<4 else 0x1660+i-4
def main():
 out=HERE/(sys.argv[1] if len(sys.argv)>1 else 'cancel-receipt.json');assert not out.exists()
 results=[];r=None
 try:
  for bias in (0x4000000000,0x6000000000):
   r=Cancel(bias)
   for initial,browse in [(i,j) for i in range(8) for j in range(8)]:
    r.call('r5_aspect_menu_commit',alias(initial));r.u.mem_write(r.call(bias+0x2170958),p32(alias(initial)))
    assert r.call('r5_aspect_menu_get')==initial
    r.trace.clear();r.aliases.clear();r.capture()
    cache=r.u32(bias+CACHE);keys=[r.u32(bias+VEC+i*4) for i in range(r.u64(bias+VEC+800))]
    assert keys==[0x52b] and cache==(initial if initial<4 else 0)
    for _ in range((browse-initial)%8):r.call(bias+0x2175e7c,P)
    before=r.call('r5_aspect_menu_get');assert before==browse
    r.event();after=r.call('r5_aspect_menu_get')
    saved=struct.unpack('<4I',r.files['custom_aspect_v2.dat'])[2]
    results.append(dict(bias=hex(bias),initial=initial,browsed=browse,before=before,after=after,saved=saved,native_cache=cache,keys=keys,restored_aliases=list(r.aliases),trace=list(r.trace),restored_correctly=after==initial and saved==(initial if initial>=4 else 0)))
  receipt=dict(executed=True,private_cancel_closed=all(x['restored_correctly'] for x in results),case_count=len(results),failed_restores=sum(not x['restored_correctly'] for x in results),cases=results,AP_sha256=hashlib.sha256(AP.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),module_sha256=hashlib.sha256((BUILD/'rx.bin').read_bytes()).hexdigest(),native_entries=['Fn capture window 0x2176c10','Fn wheel 0x2175e7c','MENU event dispatcher 0x1a5e4b8 with 0x0201000f'],no_direct_publish_during_cancel=True,no_supplied_old_alias_at_cancel=True,no_runtime_patch_overlay=True,fixtures=['FinalAP ELF relocation and in-memory POSIX model','native setter and commit endpoint write original model/meta with native values only','mutex/condition/list allocator/memcpy/memset/delete services','descriptor-map membership and pointer lookup; descriptor callbacks and row scans execute actual instructions','minimal presenter/current leaf=33 and initial accepted highlight alias','availability policy/UI notification/row icon endpoints'],limits=['No full GUI tree or OS input transport','No hardware, native scheduler/SMP, camera filesystem, IPC, encoder, JPG/HEIF or RAW execution'])
 except Exception as e:
  receipt=dict(executed=False,error=repr(e),traceback=traceback.format_exc(),recent=r.recent if r else [],trace=r.trace if r else [],cases=results)
 out.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k not in ('cases','trace','recent')}))
 if not receipt['executed']:raise SystemExit(1)
if __name__=='__main__':main()
