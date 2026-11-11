#!/usr/bin/env python3
"""Final AP D9 menu display and original dispatch replay, without a device."""
from pathlib import Path
import argparse,json,sys,struct,hashlib
H=Path(__file__).resolve().parent;R=H.parents[1]
sys.path[:0]=[str(R/'vendor/audit-python'),str(R/'analysis/r5_aspect456_20261110/ui')]
from replay_ui_support import UIReplay,VIEW,ARENA,require,sha
from unicorn.arm64_const import UC_ARM64_REG_PC

class StyleReplay(UIReplay):
 def __init__(self,ap,build,bias=0):
  super().__init__(ap,R/'analysis/r5_aspect456_20261110/ui/build-d',bias)
  self.style=json.loads((build/'build.json').read_text())
  self.sy.update({k:v+bias for k,v in self.style['symbols'].items()})
  for row in self.style['layout']:
   if row['space']=='rx' and row['name'].startswith('.text.'):
    self.sy['LOCAL:'+row['name'][6:]]=int(row['va'],16)+bias
   if row['name']=='.bss.g':self.g=int(row['va'],16)+bias
  self.selected=0;self.command=2;self.sequence=1;self.pending=0;self.mask=0xfff
  self.logs=[];self.list_owners=[];self.requests=[];self.sleeps=0;self.native_events=[];self.closed=[]
  self.u.mem_map(0x20400000,0x400000)
  self.write(0x502d20b8,0x20408000,'<Q')
  self.midptr=0x20400100;self.write(self.midptr,0x635)
  self.callbacks[bias+0x28a8720]=lambda:self.ret(self.midptr)
  self.callbacks[self.sy['r5_filter_selected']]=lambda:self.ret(self.selected)
  self.callbacks[self.sy['r5_filter_available_mask']]=lambda:self.ret(self.mask)
  self.callbacks[self.sy['r5_filter_pending']]=lambda:self.ret(self.pending)
  self.callbacks[self.sy['r5_filter_command_state']]=lambda:self.ret(self.command)
  self.callbacks[self.sy['r5_filter_command_sequence']]=lambda:self.ret(self.sequence)
  self.callbacks[self.sy['r5_filter_request']]=self.request
  self.callbacks[bias+0x1a6d8cc]=lambda:self.original_event()
  self.callbacks[bias+0x1bd55fc]=lambda:self.ret(0x2ff4400+self.selected)
  self.callbacks[bias+0x28cc860]=lambda:self.ret(self.midptr+4)
  self.callbacks[self.sy['usleep']]=lambda:self.sleep()
 def hook(self,u,address,size,data):
  name=getattr(self,'externals',{}).get(address)
  if hasattr(self,'sy') and address==self.sy.get('r5_filter_list_update'):
   self.list_owners.append(self.x(0))
  if address-self.bias==0x1884d20:
   vt=self.read(self.x(19),'<Q');target=self.read(vt+0x150,'<Q');self.callbacks[target]=lambda:self.ret(0)
  if address-self.bias==0x35b8564:self.logs.append(('assert caller',hex(self.x(30))))
  if address-self.bias in (0x17fbad8,0x3692384):
   fmt=self.cstr(self.x(0));detail= self.cstr(self.x(1)) if fmt.startswith(('assert','function')) else ''
   self.logs.append((fmt,detail,self.x(2),hex(self.x(30))))
  if name=='__assert_fail':raise AssertionError(('Native assertion',self.cstr(self.x(0)),self.cstr(self.x(1)),self.x(2),self.cstr(self.x(3))))
  if name in ('printf','fprintf','puts','fflush'):
   self.logs.append(self.cstr(self.x(0)) if name!='fflush' else 'flush');return self.ret(0)
  if name=='strlen':return self.ret(len(self.cstr(self.x(0)).encode()))
  if name in ('osal_valloc_msg_wait','osal_malloc'):
   self.external_calls.append('MODELED:'+name);ptr=self.heap;self.heap+=(self.x(2)+15)&-16;self.write(self.x(1),ptr,'<Q');return self.ret(0)
  if name in ('osal_send_msg','osal_free','osal_free_msg','osal_vfree_msg','osal_set_msg_src','osal_snd_msg'):
   self.external_calls.append('MODELED:'+name);return self.ret(0)
  if name=='vsnprintf':
   self.logs.append(self.cstr(self.x(2)));self.external_calls.append('MODELED:diagnostic-vsnprintf');self.write(self.x(0),0,'<B');return self.ret(0)
  return super().hook(u,address,size,data)
 def request(self):
  self.requests.append(self.x(0));self.sequence+=1;self.selected=self.x(0);self.command=2;self.ret(0)
 def sleep(self):self.sleeps+=1;self.ret()
 def original_event(self):self.native_events.append(self.x(2));self.ret(0x555)
 def begin(self,capacity=0x400000,layout=0):
  self.manager=0x20401000;vt=0x20402000;cb=0x20403000
  self.write(self.manager,vt,'<Q');self.write(vt+0x20,cb,'<Q');self.write(vt+8,cb+32,'<Q');self.callbacks[cb+32]=lambda:self.ret(0)
  self.callbacks[cb]=lambda:(self.closed.append(self.x(1)),self.ret())[-1]
  self.context=0x20404000;self.write(self.context,vt,'<Q');self.write(vt+0x38,cb+16,'<Q');self.callbacks[cb+16]=lambda:self.ret(0)
  self.controller=self.invoke('r5_filter_controller425',0,self.manager,self.context,0,0,layout)
  self.invoke(0x182ad30,VIEW,0,0,ARENA,capacity,self.manager,self.manager,self.manager)
  vvt=self.read(VIEW,'<Q');self.view_updates=[]
  for off in (0x20,0x50):
   target=self.read(vvt+off,'<Q');self.callbacks[target]=lambda off=off:(self.view_updates.append(off),self.ret(0))[-1]
  self.presenter=self.invoke('r5_filter_presenter425',0,VIEW,0,0,0xd9,layout)
  return self.presenter

def main():
 p=argparse.ArgumentParser();p.add_argument('--ap',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 m=StyleReplay(a.ap,a.build)
 print('constructed replay',flush=True)
 try: print('begin result',hex(m.begin()),flush=True)
 except Exception:
  print('PC',hex(m.u.reg_read(UC_ARM64_REG_PC)),'LR',hex(m.x(30)),'ext',m.external_calls[-8:],'logs',m.logs[-15:],'regs',[hex(m.x(i)) for i in range(5)],flush=True);raise
 print('controller',hex(m.controller),'g',hex(m.g),flush=True)
 for off in (0x20,0x50):
  target=m.read(m.read(VIEW,'<Q')+off,'<Q');print('view',hex(off),hex(target))
 owner=m.read(VIEW+0x3ec8+9*8,'<Q');param=m.read(m.presenter+0x48,'<Q');print('owner',hex(owner),'map',hex(param),'param9',hex(m.read(param+9*16+8,'<Q')))
 print('types',[(i,m.read(param+i*16),hex(m.read(VIEW+0x3ec8+i*8,'<Q'))) for i in range(34)],flush=True)
 print('applylist',hex(m.read(m.read(owner,'<Q')+0x148,'<Q')),flush=True)
 m.invoke(m.read(m.read(owner,'<Q')+0x148,'<Q'),owner)
 print('updatelist',flush=True)
 print('state',m.read(owner+0x204,'<B'),m.read(owner+0xf08),m.read(owner+0x17c1,'<B'),flush=True)
 print('native update',hex(m.read(m.read(owner,'<Q')+0x150,'<Q')),flush=True)
 try: m.invoke(m.read(m.read(owner,'<Q')+0x150,'<Q'),owner)
 except Exception:
  print('updatePC',hex(m.u.reg_read(UC_ARM64_REG_PC)),'LR',hex(m.x(30)),'ext',m.external_calls[-8:],'logs',m.logs[-8:],'regs',[hex(m.x(i)) for i in range(6)],flush=True);raise
 print('updated list owners',[hex(x) for x in m.list_owners],flush=True)
 for own in m.list_owners:
  print('native inner',hex(own),'resource',hex(m.read(own+0x334)), 'rows',[(hex(m.read(own+0x289a8+i*8,'<Q')),hex(m.read(m.read(own+0x289a8+i*8,'<Q')+0x208))) for i in range(7)],flush=True)
 a.output.write_text(json.dumps({'passed':True,'AP_sha256':sha(a.ap.read_bytes())})+'\n')
if __name__=='__main__':main()
