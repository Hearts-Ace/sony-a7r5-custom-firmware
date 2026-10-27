"""Compiled425 D9 page + native parent value filling, offline A64 fixtures."""
from pathlib import Path
import sys,json,hashlib,struct
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent;CAND=HERE.parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(CAND)]
from replay_main_menu425 import VM,R,X,RAM
from unicorn import UC_HOOK_CODE
results=[]
class PageVM(VM):
 def __init__(self,bias):
  self.custom={};self.busy=0;self.sequence=1;self.selected=0;self.mask=4095;self.allocations=[];self.calls=[];self.frees=[];self.mode='success';self.command=0;self.cpu=None;self.oom=0;self.parent_bad=False;self.target=0
  super().__init__(CAND/'ap/appFw.so',bias)
  self.fixture.update({})
  self.u.hook_add(UC_HOOK_CODE,self.pagehook)
  self.parent=RAM+0x100000;self.parentview=RAM+0x110000;self.parentmap=RAM+0x120000;self.pmap=RAM+0x150000
  self.view=RAM+0x140000;self.vvt=RAM+0x141000;self.manager=RAM+0x142000;self.mvt=RAM+0x143000
  self.menu_pid=0x7eff000+0xa98+0x18000+0xf40+bias;self.row_pid=0x7eff000+0xa98+0x18000+0xfb8+bias
  self.w32(self.row_pid,0x1607);self.w32(self.menu_pid,0x635);self.w32(RAM+0x800,0x635);self.w64(self.parent,0x58c1508+bias);self.w32(self.parent+0x38,0x2d7);self.w64(self.parent+0x28,self.parentview);self.w64(self.parent+0x30,self.parentmap)
  for n,typ in [(4,13),(5,0x18),(6,0x55),(7,2),(9,0),(10,0),(11,0x5b)]:
   addr=RAM+0x180000+n*0x10000;self.w32(self.parentmap+n*16,typ);self.w64(self.parentmap+n*16+8,addr)
  self.parentlist=self.q(self.parentmap+11*16+8)
  for i in range(7):
   rec=RAM+0x260000+i*0x200;self.w64(self.parentlist+0x3c+i*16,0x10);self.w64(self.parentlist+0x3c+i*16+8,rec)
  self.w32(self.view+0x3ea0,0x600000);self.w64(self.view,self.vvt);self.w64(self.parentview,self.vvt);self.w64(self.manager,self.mvt)
  self.callbacks={}
  for off in [0x10,0x18,0x20,0x30,0x50,0x60]:self.w64(self.vvt+off,RAM+0x100+off);self.callbacks[RAM+0x100+off]=off
  self.w64(self.mvt+0x20,RAM+0x1f0)
  self.map_at_got(0x5915b80,[(0x1600+n,self.sy['r5_filter_menu_rows']+n*0x80) for n in range(13)],'ptr')
  self.custom_mid=0x635
  helper=self.parent+0x2aa8;self.w32(helper+0x650,1);self.w32(helper+8,0x5b);self.w32(helper+12,11)
 def pagehook(self,u,pc,size,arg):
  a=[u.reg_read(r)for r in X[:8]];at=pc-self.bias
  if pc in self.custom:self.custom[pc](a);return
  sy=self.sy
  if pc==sy['r5_filter_selected']:self.ret(self.selected);return
  if pc==sy['r5_filter_available_mask']:self.ret(self.mask);return
  if pc==sy['r5_filter_command_sequence']:self.ret(self.sequence);return
  if pc==sy['r5_filter_pending']:self.ret(int(self.busy!=0));return
  if pc==sy['r5_filter_command_state']:
   if self.busy and self.mode!='timeout':self.busy-=1
   if self.command and not self.busy:
    self.command=3 if self.mode=='failure' else 2
    if self.command==2:self.selected=self.target
   self.ret(1 if self.busy else self.command);return
  if pc in [sy['r5_filter_request'],sy['r5_filter_reload_request']]:
   self.calls.append(('request',a[0] if pc==sy['r5_filter_request'] else 'reload'));self.sequence+=1;self.busy=3;self.command=1
   self.target=a[0] if pc==sy['r5_filter_request'] else self.selected
   self.ret(0);return
  if pc==sy['usleep']:self.calls.append(('yield',));self.ret(0);return
  if pc==sy['r5_osal_alloc']:
   if self.oom:self.ret(-1);return
   addr=RAM+0x280000+len(self.allocations)*0x10000;self.allocations.append((addr,a[2]));self.w64(a[1],addr);self.ret(0);return
  if pc==sy['r5_osal_free']:self.frees.append(a[1]);self.ret(0);return
  if at in [0x1d2e488,0x1e1e1a4]:self.calls.append(('stock_factory',at));self.ret(0x123456);return
  if at==0x1d90c7c:self.ret(self.parent);return
  if at==0x1d2e2f0:self.w32(a[0]+0x178,0xd9);self.w64(a[0]+0x180,a[1]);self.ret(a[0]);return
  if at in [0x1b2ae4c,0x1bc3304]:self.ret(0);return
  if pc in self.callbacks:
   off=self.callbacks[pc]
   if off==0x30:self.ret(self.pmap);return
   if off==0x10:
    styles=a[2];self.styles=styles;self.masks=bytes(u.mem_read(a[5],34));self.created=[]
    for i in range(34):
     typ=self.d(styles+i*52);self.w32(self.pmap+i*16,typ);self.w64(self.pmap+i*16+8,RAM+0x150000+0x1000+i*0x1000)
     if not self.masks[i]:self.created.append((i,typ))
   if off==0x20 and a[0]==self.parentview and self.parent_bad:self.w32(self.parentlist+0x80,0xdeadbeef)
   self.calls.append(('view',off));self.ret(0);return
  if pc==RAM+0x1f0:self.calls.append(('committed_before_pop',self.selected));self.calls.append(('pop',self.d(a[1])));self.ret(0);return
  if at in [0x1cbfb80,0x22083ec]:self.calls.append(('base_destroy',at));self.ret(0);return
  if at==0x1bd55fc and self.parent_bad:self.ret(0xdeadbeef);return
  # Native1004 parent presenter update executes its body and real value fill.
  if at in [0x1b2b600,0x1d90d78,0x1d90cb0,0x2e7d208,0x2e7cee4]:self.ret(0);return
  if at==0x1b2b140:self.ret(12);return
  if at==0x1bd6c5c:self.ret(1);return
  if at==0x1bd54a8:self.ret(0x200a2fd);return
  if at in [0x1bd54d8]:self.ret(0x200a2fd);return
  if at==0x28a8608:self.ret(RAM+0x800);return
  if at==0x16d95f0:u.mem_write(a[0],bytes([a[1]&255])*a[2]);self.ret(a[0]);return
  if at==0x1bd6620:self.w32(a[1],0x635);self.ret(1);return
  if at in [0x1bd5d20,0x1bd845c,0x1bd84ec]:self.ret(0);return
  if at==0x28cc860:self.ret(RAM+0x808);return
  if at==0x28ec604:self.ret(RAM+0x804);return
  if at==0x1afe958:self.ret(self.q(self.q(a[0])+8));return
  if at==0x211d378:self.ret(self.q(self.q(a[0])+8));return
  if at==0x1834410:self.ret(a[0]+a[1]*0x94);return
  if at in [0x1bd6868,0x1bd5e70,0x1bd86a8,0x1bd621c]:self.ret(0);return
 def hook(self,u,pc,size,arg):
  # Base VM's invariants and registry/tree fixtures remain active, but its
  # model accessor must not swallow our independent parameter object.
  if pc-self.bias in [0x1bd55fc,0x1afe958]:return
  super().hook(u,pc,size,arg)
 def open(self):
  self.call(self.sy['r5_filter_parent_presenter425'],0,self.parentview,0,0,0x2d7,0)
  c=self.call(self.sy['r5_filter_controller425'],0,self.manager,0,0,0,0)
  p=self.call(self.sy['r5_filter_presenter425'],0,self.view,0,0,0xd9,0)
  self.controller=c;self.presenter=p;return c,p
 def event(self,event):return self.call(self.q(self.q(self.controller)+0x10),self.controller,RAM+0x820,event)
 def touch(self,index):
  self.w32(RAM+0x820,1);self.w32(RAM+0x82c,index);self.w32(RAM+0x838,0xd9);return self.event(0x3010002)
 def cleanup(self):
  p,c=self.presenter,self.controller;self.call(self.q(self.q(p)),p);self.call(self.q(self.q(c)),c)
def main():
 from replay_interaction431 import main as interaction
 interaction()
if __name__=='__main__':main()
