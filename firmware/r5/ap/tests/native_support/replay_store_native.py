#!/usr/bin/env python3
"""Final ARM64 AP storage and boot machine code with explicit POSIX/Fsys fixtures.

No real file is written except the selected evidence JSON. Every buffer/fd and
read/write/rename effect below belongs to an in-memory fixture filesystem.
"""
from pathlib import Path
import argparse,json,struct,hashlib
from replay_final_ap import FinalAP,FIX,SERV,STACK,STOP
from unicorn.arm64_const import UC_ARM64_REG_PC,UC_ARM64_REG_SP
HEAP=0x20000000;INPUT=HEAP+0x20000;OUTPUT=HEAP+0x30000

def check(ok,label):
 if not ok:raise AssertionError(label)
class Store(FinalAP):
 def __init__(self,candidate,build,fixture):
  super().__init__(candidate,build,0x4000000000);self.u.mem_map(HEAP,0x200000)
  self.raw=fixture;self.files={'R5NATIVE.BIN':bytearray(fixture)};self.fds={};self.fd=7;self.alloc={};self.allocation_log=[];self.peak=0;self.errno=2;self.fail='';self.calls=[];self.chunk=512;self.tick=0;self.service_calls=0
  native=json.loads((Path(__file__).resolve().parents[2]/'contracts/native.json').read_text())
  for native_name,name in [('r5_ap_posix_open','open'),('r5_ap_posix_openat','openat'),('r5_ap_posix_read','read'),('r5_ap_posix_write','write'),('r5_ap_posix_close','close'),('r5_ap_posix_fsync','fsync'),('r5_ap_posix_unlinkat','unlinkat'),('r5_ap_posix_errno','errno')]:self.callbacks[self.bias+native[native_name]]=lambda name=name:self.posix(name)
  self.callbacks[self.bias+0x16dac90]=self.resolve
  self.u.mem_write(INPUT,fixture);self.call('r5_session_cold');check(self.call('r5_session_prepare')==1,'session prepare')
 def call(self,name,*args):
  for i,arg in enumerate(args):self.putx(i,arg)
  self.u.reg_write(UC_ARM64_REG_SP,STACK+0x1f000);self.putx(29,0);self.putx(30,STOP)
  self.u.emu_start(self.sy[name]if isinstance(name,str)else name,STOP,count=10000000)
  check(self.u.reg_read(UC_ARM64_REG_PC)==STOP,(name,hex(self.u.reg_read(UC_ARM64_REG_PC))))
  return self.x(0)&0xffffffff
 def resolve(self):
  name=self.cstr(self.x(1));names=['malloc','free','pread','renameat','dup','clock_gettime','nanosleep','sched_setscheduler']
  if name not in names:return self.ret(0)
  at=SERV+0x400+16*names.index(name);self.callbacks[at]=lambda name=name:self.posix(name);self.ret(at)
 def makefd(self,name):self.fd+=1;self.fds[self.fd]=[name,0];return self.fd
 def posix(self,name):
  if name=='malloc':
   size=self.x(0);ptr=HEAP+0x50000+sum((n+15)&~15 for n in self.alloc.values())
   check(ptr+size<HEAP+0x200000,'fixture heap bounded');self.alloc[ptr]=size;self.allocation_log.append(size);self.peak=max(self.peak,sum(self.alloc.values()));return self.ret(ptr)
  if name=='free':check(self.x(0)in self.alloc,'free exactly owned allocation');self.alloc.pop(self.x(0));return self.ret()
  if name=='clock_gettime':self.u.mem_write(self.x(1),struct.pack('<qq',self.tick//1000,self.tick%1000*1000000));return self.ret()
  if name=='nanosleep':sec,ns=struct.unpack('<qq',self.u.mem_read(self.x(0),16));self.tick+=sec*1000+ns//1000000;return self.ret()
  if name=='sched_setscheduler':return self.ret(1 if self.fail=='schedule'else 0)
  if name=='errno':self.u.mem_write(FIX+0x9000,struct.pack('<I',self.errno));return self.ret(FIX+0x9000)
  if name=='open':
   path=self.cstr(self.x(0));self.calls.append((name,path))
   if path=='/usr/data/lut':
    if self.fail=='mount_absent':return self.ret(-1)
    return self.ret(self.makefd('directory'))
   if path.startswith('/proc/self/fdinfo/'):
    self.files[path]=bytearray(b'pos:\t0\nflags:\t0100000\nmnt_id:\t42\n');return self.ret(self.makefd(path))
   if path=='/proc/self/mountinfo':
    self.files[path]=bytearray(b'42 2 179:30 / /usr/data/lut rw - vfat /dev/nflasha30 rw\n');return self.ret(self.makefd(path))
   raise AssertionError(path)
  if name=='dup':check(self.fds[self.x(0)][0]=='directory','dup directory');return self.ret(self.makefd('directory'))
  if name=='openat':
   check(self.fds[self.x(0)][0]=='directory','anchored openat');path=self.cstr(self.x(1));flags=self.x(2);self.calls.append((name,path,flags))
   if flags&0x40:
    check(path not in self.files,'exclusive create');self.files[path]=bytearray()
   if path not in self.files:return self.ret(-1)
   return self.ret(self.makefd(path))
  if name=='unlinkat':
   path=self.cstr(self.x(1));self.calls.append((name,path))
   if path not in self.files:return self.ret(-1)
   self.files.pop(path);return self.ret()
  if name=='renameat':
   old,new=self.cstr(self.x(1)),self.cstr(self.x(3));self.calls.append((name,old,new))
   if self.fail=='rename':return self.ret(-1)
   self.files[new]=self.files.pop(old);return self.ret()
  if name=='close':
   fd=self.x(0);path=self.fds.pop(fd)[0];self.calls.append((name,path))
   return self.ret(-1 if self.fail=='close_active'and path=='R5NATIVE.BIN'else 0)
  if name=='fsync':
   path=self.fds[self.x(0)][0];self.calls.append((name,path));return self.ret(-1 if self.fail=='directory_sync'and path=='directory'or self.fail=='stage_sync'and path=='R5NATIVE.NEW'else 0)
  if name in ('read','pread'):
   path,position=self.fds[self.x(0)];offset=self.x(3)if name=='pread'else position;count=min(self.x(2),self.chunk)
   if self.fail=='read_active'and path=='R5NATIVE.BIN':return self.ret(-1)
   if self.fail=='zero_record'and path=='R5NATIVE.BIN'and offset>=128:count=0
   data=bytes(self.files[path][offset:offset+count])
   if self.fail=='verify_mismatch'and path=='R5NATIVE.NEW'and data:data=bytes([data[0]^1])+data[1:]
   self.u.mem_write(self.x(1),data);self.calls.append((name,path,offset,len(data)))
   if name=='read':self.fds[self.x(0)][1]+=len(data)
   return self.ret(len(data))
  if name=='write':
   path,offset=self.fds[self.x(0)];count=min(self.x(2),self.chunk)
   if self.fail=='write_zero':count=0
   data=bytes(self.u.mem_read(self.x(1),count));self.files[path][offset:offset+count]=data;self.fds[self.x(0)][1]+=count;self.calls.append((name,path,offset,count));return self.ret(count)
  raise AssertionError(name)
 def clean(self):check(not self.alloc and not self.fds,'all temporary heap buffers and fds released')
 def index(self):check(self.call('r5_filter_store_index',OUTPUT)==0,'index complete package');self.clean()
 def boot(self,sd):
  self.sd=sd;self.sd_at=0;self.sd_open=False
  native=json.loads((Path(__file__).resolve().parents[2]/'contracts/native.json').read_text())
  def sdopen():
   check(self.cstr(self.x(0))=='A:/R5NATIVE.BIN','SD file path');self.sd_open=True;self.u.mem_write(self.x(2),struct.pack('<Q',123));self.ret()
  def sdread():
   check(self.sd_open,'SD handle owned');part=self.sd[self.sd_at:self.sd_at+self.x(2)];self.sd_at+=len(part);self.u.mem_write(self.x(1),part);self.u.mem_write(self.x(3),struct.pack('<Q',len(part)));self.ret()
  def sdclose():check(self.sd_open,'SD close once');self.sd_open=False;self.ret()
  def service():self.service_calls+=1;self.ret()
  self.callbacks.update({self.bias+native['r5_native_fsys_open']:sdopen,self.bias+native['r5_native_fsys_read']:sdread,self.bias+native['r5_native_fsys_close']:sdclose,self.sy['r5_filter_service']:service,self.sy['r5sound_initial']:lambda:self.ret(),self.sy['r5sound_completed']:lambda:self.ret(),self.sy['r5sound_media']:lambda:self.ret()})
  self.call('r5_stage411_initial',1,0);self.call('r5_stage411_completed',0);self.call('r5_stage411_media',0,0,ord('A'))
  result=self.call('r5_stage411_child',self.sy['r5_stage411_state']);self.clean();check(not self.sd_open,'SD closes before internal IO');return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--fixture',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();check(not a.output.exists(),'new receipt');data=a.fixture.read_bytes();rows=[]
 for fail in ['', 'read_active','close_active','zero_record']:
  m=Store(a.candidate,a.build,data);m.index();m.calls.clear();m.fail=fail;rc=m.call('r5_filter_store_read',OUTPUT,3,OUTPUT+0x2000);m.clean();check((rc==0)==(not fail),'single-record failure result')
  if not fail:
   record=data[128+2*2452:128+3*2452];expected=record[4:28]+bytes(8)+record[92:1232]+struct.pack('<I',1)+record[1232:2447]+b'\0';check(bytes(m.u.mem_read(OUTPUT+0x2000,2392))==expected,'exact selected compact')
   check(sum(x[3]for x in m.calls if x[0]=='pread'and x[1]=='R5NATIVE.BIN')==2581,'selected record only bytes')
  rows.append(dict(case='single_record_'+(fail or 'success'),rc=rc,heap_empty=True,fd_empty=True,peak_ap_heap=m.peak));del m
 for fail in ['', 'write_zero','stage_sync','verify_mismatch','rename','directory_sync']:
  m=Store(a.candidate,a.build,data);m.files['R5NATIVE.BIN']=bytearray(b'prior-invalid-package');m.fail=fail
  rc=m.call('r5_filter_store_publish',INPUT,len(data),OUTPUT);m.clean();check((rc==0)==(not fail),'publish failure result')
  check(bytes(m.files['R5NATIVE.BIN'])==(data if fail in ('','directory_sync')else b'prior-invalid-package'),'atomic publish/uncertain-after-rename state')
  rows.append(dict(case='publish_'+(fail or 'success'),rc=rc,active_replaced=fail in ('','directory_sync'),heap_empty=True,fd_empty=True,peak_ap_heap=m.peak));del m
 for case,sd in [('valid_whole_sd',data),('invalid_sd_falls_back',data[:-1]),('empty_sd_clears',b'')]:
  m=Store(a.candidate,a.build,data);rc=m.boot(sd);check(rc==1,'clock/sleep readiness preserves audio worker contract');mask=m.call('r5_filter_available_mask');check(mask==(0 if not sd else 4095),'catalog mask from durable package')
  check(m.service_calls>0,'worker reaches filter service only after ready catalog')
  rows.append(dict(case=case,rc=rc,available_mask=mask,heap_empty=True,fd_empty=True,peak_ap_heap=m.peak,boot_package_freed_before_service=True));del m
 m=Store(a.candidate,a.build,data);m.fail='schedule';check(m.boot(data)==0,'scheduler failure does not start audio service');check(m.call('r5_filter_available_mask')==0,'scheduler failure no catalog');rows.append(dict(case='scheduler_refusal',rc=0,no_catalog=True));del m
 result=dict(passed=True,AP_sha256=hashlib.sha256(a.candidate.read_bytes()).hexdigest(),fixture_sha256=hashlib.sha256(data).hexdigest(),cases=rows,limits=['POSIX/Fsys calls, file data, allocator backing and native timing are explicit in-memory endpoints.','Actual AP store/index/boot/read/write/validate/stage/rename branches and mountinfo/fdinfo parsers execute from the final ELF.','Directory fsync failure after rename leaves the newly visible file; failure is reported and boot rereads it rather than retries publish.','No physical storage timing, power-cut persistence, free RAM or camera operation is measured.'])
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(rows),max_peak_ap_heap=max(r.get('peak_ap_heap',0)for r in rows))))
if __name__=='__main__':main()
