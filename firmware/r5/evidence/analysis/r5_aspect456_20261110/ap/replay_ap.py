#!/usr/bin/env python3
"""Run the compiled AArch64 module and selected original R5 paths in Unicorn.

POSIX endpoints and UI broker objects are explicit fixtures, never hardware.
"""
from pathlib import Path
import argparse,hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(HERE.parent/'integration')]
from inspect_ap import Image
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm64_const import *
X=[UC_ARM64_REG_X0+i for i in range(29)]+[UC_ARM64_REG_X29,UC_ARM64_REG_X30]
Q=[UC_ARM64_REG_Q0+i for i in range(32)]
STACK=0x12000000;STOP=0x13000000;FIX=0x10000000;SERV=0x11000000
def p32(x):return struct.pack('<I',x&0xffffffff)
def p64(x):return struct.pack('<Q',x)
class Replay:
 def __init__(self,build):
  self.im=Image(ROOT/'projects/firmware/releases/4.55-sound-recovery-20261105/appFw.so')
  self.report=json.loads((build/'module.json').read_text());self.sy=self.report['symbols']
  self.u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);self.callbacks={};self.calls=[];self.native=0
  for s in self.im.loads:
   lo=s['p_vaddr']&~4095;hi=(s['p_vaddr']+s['p_memsz']+4095)&~4095
   if hi>lo:self.u.mem_map(lo,hi-lo)
   self.u.mem_write(s['p_vaddr'],self.im.raw[s['p_offset']:s['p_offset']+s['p_filesz']])
  for k,name in [('rx','rx.bin'),('rw','rw.bin')]:
   addr=self.report[k];raw=(build/name).read_bytes()
   memory=max(len(raw),self.report.get('rw_memory_bytes',0) if k=='rw' else 0,1)
   lo=addr&~4095;hi=(addr+memory+4095)&~4095
   self.u.mem_map(lo,hi-lo)
   if raw:self.u.mem_write(addr,raw)
  self.u.mem_map(FIX,0x10000);self.u.mem_map(SERV,0x10000)
  self.u.mem_map(STACK,0x20000);self.u.mem_map(STOP,0x1000)
  self.callbacks[STOP]=lambda:self.u.emu_stop()
  self.callbacks[0x2e7d208]=lambda:self.ret(0)
  self.callbacks[0x2e7cee4]=lambda:self.ret(0)
  self.callbacks[0x1c61d14]=self.setter
  self.callbacks[0x1c93d88]=self.commit
  self.callbacks[0x16dac90]=self.dlsym
  self.callbacks[0x355882c]=self.send
  self.callbacks[0x3565f7c]=lambda:self.u.emu_stop()
  self.u.hook_add(UC_HOOK_CODE,self.hook)
  self.files={};self.fds={};self.nextfd=8;self.fail=None;self.chunk=17
  self.u.reg_write(UC_ARM64_REG_CPACR_EL1,3<<20)
 def hook(self,u,addr,size,_):
  if addr in self.callbacks:self.callbacks[addr]()
 def x(self,n):return self.u.reg_read(X[n])
 def putx(self,n,x):self.u.reg_write(X[n],x&0xffffffffffffffff)
 def ret(self,value=0):self.putx(0,value);self.u.reg_write(UC_ARM64_REG_PC,self.x(30))
 def cstr(self,p):
  b=bytearray()
  for i in range(1024):
   c=bytes(self.u.mem_read(p+i,1))
   if c==b'\0':return b.decode()
   b+=c
  raise AssertionError('string limit')
 def setter(self):
  self.native=self.x(0);self.calls.append(('native_set',self.native));self.u.mem_write(0x7f1cc20,p32(self.native));self.ret()
 def commit(self):self.calls.append(('native_commit',self.x(0)));self.ret()
 def send(self):self.calls.append(('send',bytes(self.u.mem_read(self.x(1),self.x(2))).hex()));self.ret(0x55)
 def dlsym(self):
  name=self.cstr(self.x(1));names=['open','openat','read','write','close','fsync','renameat','unlinkat']
  if name not in names or self.fail=='resolve':return self.ret(0)
  address=SERV+names.index(name)*16
  self.callbacks[address]=lambda name=name:self.posix(name)
  self.ret(address)
 def posix(self,name):
  self.calls.append(('posix',name))
  if self.fail==name:return self.ret(-1)
  if name=='open':
   assert self.cstr(self.x(0))=='/setting';return self.ret(7)
  if name=='openat':
   assert self.x(0)==7;n=self.cstr(self.x(1));flags=self.x(2)
   if flags&0x40:self.files[n]=bytearray()
   if n not in self.files:return self.ret(-1)
   fd=self.nextfd;self.nextfd+=1;self.fds[fd]=[n,0];return self.ret(fd)
  if name=='read':
   n,at=self.fds[self.x(0)];raw=bytes(self.files[n][at:at+min(self.x(2),self.chunk)])
   self.u.mem_write(self.x(1),raw);self.fds[self.x(0)][1]+=len(raw);return self.ret(len(raw))
  if name=='write':
   n,at=self.fds[self.x(0)];raw=bytes(self.u.mem_read(self.x(1),min(self.x(2),self.chunk)))
   self.files[n][at:at+len(raw)]=raw;self.fds[self.x(0)][1]+=len(raw);return self.ret(len(raw))
  if name=='renameat':
   a=self.cstr(self.x(1));b=self.cstr(self.x(3));self.files[b]=self.files.pop(a);return self.ret()
  if name=='unlinkat':self.files.pop(self.cstr(self.x(1)),None);return self.ret()
  if name in ('close','fsync'):return self.ret()
  raise AssertionError(name)
 def call(self,name,*args):
  for i,arg in enumerate(args):self.putx(i,arg)
  self.u.reg_write(UC_ARM64_REG_SP,STACK+0x1f000);self.putx(29,0);self.putx(30,STOP)
  self.u.emu_start(self.sy[name] if isinstance(name,str) else name,STOP,count=200000)
  assert self.u.reg_read(UC_ARM64_REG_PC)==STOP,(name,hex(self.u.reg_read(UC_ARM64_REG_PC)))
  return self.x(0)&0xffffffff
 def reset(self):self.call('r5_aspect_reset_for_test')
 def token(self):return struct.unpack('<I',self.u.mem_read(self.sy['r5_aspect_selection'],4))[0]
def main():
 p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 r=Replay(a.build);checks=0;cases=[]
 def check(ok,label):
  nonlocal checks
  assert ok,label;checks+=1
 for native in range(4):
  for choice in range(8):
   r.reset();token=r.call('r5_aspect_publish',choice)
   check(r.call('r5_aspect_effective',native,token)==(choice if native==0 and choice>=4 else native),'effective')
   check(r.call('r5_aspect_freeze',native)==(choice if native==0 and choice>=4 else 0),'freeze')
   r.u.mem_write(FIX,bytes(range(24)));r.call('r5_aspect_packet',FIX,choice)
   expected=bytearray(range(24))
   if choice>=4:expected[8]=choice+1
   check(bytes(r.u.mem_read(FIX,24))==expected,'packet only aspect byte')
 cases.append('all four native values and all eight menu choices')
 for choice in [0,4,5,6,7]:
  for malformed in range(7):
   r.reset();r.call('r5_aspect_make_record',choice,FIX);record=bytearray(r.u.mem_read(FIX,16));n=16
   if malformed==1:record[0]^=1
   if malformed==2:record[4]=3
   if malformed==3:record[8]=8
   if malformed==4:record[12]^=1
   if malformed==5:n=15
   if malformed==6:n=17;record+=b'X'
   r.u.mem_write(FIX,bytes(record))
   got=r.call('r5_aspect_restore_record',FIX,n,0)
   check(got==(malformed==0),'record validation')
   check((r.token()&15)==((choice|8) if choice and malformed==0 else 0),'record state')
 cases.append('record magic/schema/range/complement/exact-length validation')
 r.reset();r.call('r5_aspect_make_record',4,FIX);r.call('r5_aspect_publish',7)
 check(r.call('r5_aspect_restore_record',FIX,16,0)==0,'late restore refused')
 check(r.token()&15==15,'new explicit choice retained')
 # Actual native getter, with only mutex endpoints modeled.
 for native in range(4):
  r.u.mem_write(0x7f1cc20,p32(native));check(r.call(0x1c448dc)==native,'original getter actual load')
 cases.append('original R5 getter reads original native model word')
 # Actual original generic apply makes the independent broker consumer visible.
 broker=FIX+0x1000;vt=FIX+0x2000;self_=FIX+0x3000;selfvt=FIX+0x4000
 r.u.mem_write(0x74dc990,p64(broker));r.u.mem_write(broker,p64(vt));r.u.mem_write(self_,p64(selfvt))
 row_get=FIX+0x8000;broker_call=FIX+0x8010
 r.u.mem_write(selfvt+0x790,p64(row_get));r.u.mem_write(vt+8,p64(broker_call))
 captured=[]
 def row_lookup():
  alias=r.x(1);order=[0,4,1,6,2,7,5,3]
  addr=0x3f46600+(alias-126)*128 if 126<=alias<=129 else r.sy['r5_aspect_menu_rows']+order.index(alias-0x1660+4)*128
  r.ret(addr)
 def broker_capture():
  captured.append((struct.unpack('<I',r.u.mem_read(r.x(1),4))[0],struct.unpack('<I',r.u.mem_read(r.x(2),4))[0]));r.ret()
 r.callbacks[row_get]=row_lookup;r.callbacks[broker_call]=broker_capture
 r.call('r5_aspect_menu_init')
 original=bytes(r.u.mem_read(0x3f46600,512));order=[0,4,1,6,2,7,5,3]
 for native in range(4):check(bytes(r.u.mem_read(r.sy['r5_aspect_menu_rows']+order.index(native)*128,128))==original[native*128:(native+1)*128],'original row exact in display order')
 for alias in range(0x1660,0x1664):
  r.call(0x1bc7720,self_,alias);check(captured[-1]==(0x52b,alias-0x1660+4),'native unpatched leaks private enum')
  r.call('r5_aspect_apply_hook',self_,alias);check(captured[-1]==(0x52b,0),'wrapper broker native zero')
  check(r.token()&7==alias-0x1660+4,'wrapper private choice retained')
 for alias in range(126,130):
  r.call('r5_aspect_apply_hook',self_,alias);check(captured[-1]==(0x52b,alias-126),'native broker values retained')
  check(r.token()&15==0,'native alias clears private')
 cases.append('original generic apply reproduces invalid private enum and wrapper fixes broker value')
 for alias in range(126,130):
  check(r.call('r5_aspect_size_alias_hook',alias)==r.call(0x1bcfd18,alias),'native size alias unchanged')
 for alias in range(0x1660,0x1664):
  check(r.call('r5_aspect_size_alias_hook',alias)==r.call(0x1bcfd18,126),'custom size uses native 3:2')
 cases.append('actual R5 native size alias jump table')
 # Run the original list loop and typed-model accessor. Only its row-query
 # services are fixtures, so count, selected index and output stores are native.
 table=FIX+0x5000;model=FIX+0x6000;request=FIX+0x7e00;modeword=FIX+0x7f00
 aliases=[126+n if n<4 else 0x1660+n-4 for n in order]
 r.u.mem_write(table,p64(28)+p64(model));r.u.mem_write(modeword,p32(0x1234))
 def enumerate_rows():
  assert r.x(1)==33 and r.x(3)==256
  r.u.mem_write(r.x(2),b''.join(p32(alias)+p32(0x335) for alias in aliases))
  r.ret(8)
 r.callbacks[0x1bcad24]=enumerate_rows
 r.callbacks[0x1bd5840]=lambda:r.ret(0x02001081)
 r.callbacks[0x1bd5870]=lambda:r.ret(0x02001421)
 r.callbacks[0x1bd5d50]=lambda:r.ret(0)
 r.callbacks[0x1bd5e40]=lambda:r.ret(6)
 r.callbacks[0x28cc860]=lambda:r.ret(modeword)
 r.u.mem_write(request,struct.pack('<4I',0,0,33,0x1662))
 r.call(0x1bc36f8,0,table,request)
 check(struct.unpack('<I',r.u.mem_read(model+0xd30,4))[0]==8,'original list produces eight rows')
 check(struct.unpack('<I',r.u.mem_read(model+0xd38,4))[0]==6,'original list selected index retained')
 check(bytes(r.u.mem_read(model+0x30,32))==p32(0x02001081)*8,'original list fixture image output observed')
 r.call('r5_aspect_list_hook',0,table,request)
 check(bytes(r.u.mem_read(model+0x30,32))==p32(-1)*8,'list ordinary images cleared')
 check(bytes(r.u.mem_read(model+0x430,32))==p32(-1)*8,'list selected images cleared')
 textids=[struct.unpack('<I',original[n*128+8:n*128+12])[0] if n<4 else 0x0200ab4c+n-4 for n in order]
 check(bytes(r.u.mem_read(model+0x830,32))==b''.join(p32(t) for t in textids),'all eight actual list text slots')
 check(struct.unpack('<I',r.u.mem_read(model+0xd38,4))[0]==6,'list wrapper preserves selected index')
 check(struct.unpack('<I',r.u.mem_read(model+0xd44,4))[0]==0x1234,'list wrapper preserves native mode field')
 cases.append('original native list loop and typed model produce eight rows; wrapper supplies eight text labels')
 # Menu setters and commit route only original native values/aliases.
 for choice in range(8):
  r.call('r5_aspect_menu_set',choice);check(r.calls[-1]==('native_set',0 if choice>=4 else choice),'setter native normalization')
 for alias in range(0x1660,0x1664):
  r.call('r5_aspect_menu_commit',alias)
  check([c for c in r.calls if c[0]=='native_commit'][-1]==('native_commit',126),'commit native alias')
  check(bytes(r.files['custom_aspect_v2.dat'])==struct.pack('<4I',0x32505243,2,alias-0x1660+4,~(alias-0x1660+4)&0xffffffff),'persist selected choice')
 cases.append('menu setter/commit native normalization and atomic record publication')
 # Actual descriptor setter/commit dispatch traverses all eight row aliases.
 # Tree membership, parent lookup and blocked status are explicit fixtures.
 descriptor=0x586b990;holder=FIX+0x9000;blocked_cb=FIX+0x8020;parent_cb=FIX+0x8030
 r.u.mem_write(holder,p64(descriptor))
 r.u.mem_write(selfvt+0x250,p64(blocked_cb));r.u.mem_write(selfvt+0x328,p64(parent_cb))
 r.callbacks[blocked_cb]=lambda:r.ret(0);r.callbacks[parent_cb]=lambda:r.ret(33)
 r.callbacks[0x1bd851c]=lambda:r.ret(33)
 r.callbacks[0x1bd906c]=lambda:r.ret(1)
 r.callbacks[0x1bd90c4]=lambda:r.ret(holder)
 r.u.mem_write(descriptor+0x54,p32(8));r.u.mem_write(descriptor+0x58,p64(r.sy['r5_aspect_menu_rows']))
 r.u.mem_write(descriptor+0x80,p64(r.sy['r5_aspect_menu_set']))
 r.u.mem_write(descriptor+0x88,p64(r.sy['r5_aspect_menu_commit']))
 for oldalias in aliases:
  oldchoice=oldalias-126 if oldalias<130 else oldalias-0x1660+4
  r.call(0x1bd924c,self_,oldalias)
  check(r.native==(oldchoice if oldchoice<4 else 0),'descriptor setter native old alias')
  r.call(0x1bd924c,self_,0x1663)
  check(r.token()&15==15,'descriptor setter browse private alias')
  r.call(0x1bd924c,self_,oldalias)
  check(r.token()&15==(oldchoice|8 if oldchoice>=4 else 0),'descriptor setter restores old alias')
  check(r.native==(oldchoice if oldchoice<4 else 0),'descriptor restore native enum')
  r.call(0x1bd9348,self_,oldalias)
  check([c for c in r.calls if c[0]=='native_commit'][-1]==('native_commit',126 if oldchoice>=4 else oldalias),'descriptor commit native alias')
 cases.append('actual descriptor alias-to-choice setter/commit and supplied old-alias restoration; event source remains unproven')
 # The restore CAS must prefer a newer explicit choice even if read() returns
 # the old on-disk selection. Faults never mutate the original native model.
 goodrecord=struct.pack('<4I',0x32505243,2,5,~5&0xffffffff)
 for variant in ['valid','missing','truncated','oversized','malformed','read','close','resolve','explicit']:
  rp=Replay(a.build);data=goodrecord
  if variant=='truncated':data=data[:15]
  if variant=='oversized':data+=b'x'
  if variant=='malformed':data=b'BAD!'+data[4:]
  if variant!='missing':rp.files['custom_aspect_v2.dat']=bytearray(data)
  if variant in ['read','close','resolve']:rp.fail=variant
  if variant=='explicit':rp.call('r5_aspect_publish',7)
  rp.call('r5_aspect_restore_once')
  check(rp.token()&15==(13 if variant=='valid' else 15 if variant=='explicit' else 0),'restore fault '+variant)
  if variant=='explicit':check(not rp.calls,'new explicit choice suppresses disk IO')
  before=rp.token();rp.call('r5_aspect_restore_once');check(rp.token()==before,'restore is once '+variant)
 cases.append('restore missing/truncated/oversized/malformed/IO failures and newer explicit choice')
 for failure in ['write','fsync','close','renameat']:
  rp=Replay(a.build);rp.files['custom_aspect_v2.dat']=bytearray(goodrecord);rp.chunk=3;rp.fail=failure
  check(rp.call('r5_aspect_save',7)==0xffffffff,'save reports failure '+failure)
  check(bytes(rp.files['custom_aspect_v2.dat'])==goodrecord,'failed save preserves old record '+failure)
  rp.fail=None
  check(rp.call('r5_aspect_save',7)==0,'save claim released after '+failure)
  check(bytes(rp.files['custom_aspect_v2.dat'])==struct.pack('<4I',0x32505243,2,7,~7&0xffffffff),'retry saves full record '+failure)
 cases.append('save short writes, pre-publication faults, old record preservation and retry')
 # Freeze ABI, including a restore with libc fixtures, then a later global change.
 for native in range(4):
  r2=Replay(a.build);record=struct.pack('<4I',0x32505243,2,5,~5&0xffffffff)
  r2.files['custom_aspect_v2.dat']=bytearray(record);r2.chunk=3
  frame=STACK+0x18000;input_=FIX+0x5000;r2.u.mem_write(input_+8,p32(native))
  original_regs=[(i+1)*0x11223344 for i in range(31)]
  for i,v in enumerate(original_regs):r2.putx(i,v)
  r2.putx(20,input_);r2.putx(29,frame);r2.putx(30,0x12345678)
  original_regs[20]=input_;original_regs[29]=frame;original_regs[30]=0x12345678
  for i,q in enumerate(Q):r2.u.reg_write(q,((i+1)<<96)|0x8877665544332211)
  simd=[r2.u.reg_read(q) for q in Q]
  r2.u.reg_write(UC_ARM64_REG_SP,STACK+0x17000);r2.u.reg_write(UC_ARM64_REG_NZCV,0xa0000000)
  r2.u.reg_write(UC_ARM64_REG_FPCR,0x400000);r2.u.reg_write(UC_ARM64_REG_FPSR,0x10)
  r2.u.emu_start(r2.sy['r5_aspect_freeze_hook'],STOP,count=200000)
  check(r2.u.reg_read(UC_ARM64_REG_PC)==0x3565f7c,'freeze real continuation')
  for i in range(31):check(r2.x(i)==(native if i==1 else original_regs[i]),'freeze register '+str(i))
  check([r2.u.reg_read(q) for q in Q]==simd,'freeze all Q registers')
  check(r2.u.reg_read(UC_ARM64_REG_NZCV)==0xa0000000,'freeze NZCV')
  check(r2.u.reg_read(UC_ARM64_REG_FPCR)==0x400000,'freeze FPCR')
  check(r2.u.reg_read(UC_ARM64_REG_FPSR)==0x10,'freeze FPSR')
  check(struct.unpack('<I',r2.u.mem_read(frame+0x74,4))[0]==(5 if native==0 else 0),'frozen native eligibility')
  # Keep the previous frame; publish an explicit new choice before send.
  r2.call('r5_aspect_publish',7);packet=FIX+0x6000;r2.u.mem_write(packet,bytes(range(24)))
  r2.putx(0,0x90030001);r2.putx(1,packet);r2.putx(2,24);r2.putx(29,frame);r2.putx(30,STOP)
  r2.u.reg_write(UC_ARM64_REG_SP,STACK+0x17000)
  r2.u.emu_start(r2.sy['r5_aspect_send_hook'],STOP,count=200000)
  expected=bytearray(range(24))
  if native==0:expected[8]=6
  check(bytes(r2.u.mem_read(packet,24))==expected,'send uses frozen choice after global changed')
 cases.append('freeze restore, complete register/flags ABI, and send with later selection change')
 output=dict(passed=True,checks=checks,cases=cases,
   module_sha256=hashlib.sha256((a.build/'rx.bin').read_bytes()).hexdigest(),
   AP_sha256=hashlib.sha256(r.im.raw).hexdigest(),
   fixtures=['POSIX dynamic resolver and in-memory files','model mutex endpoints',
             'native setter/commit endpoints','row lookup and broker object/callback',
             'send endpoint'],
   limitations=['No LCD, camera filesystem or full native event loop',
                'No full capture or JPEG encoder execution',
                'No complete appended AP loader verification'])
 a.output.write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output))
if __name__=='__main__':main()
