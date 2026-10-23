"""Persistent offline413 CP task bridge; no device/transport access.

Stack depth is sampled at basic-block/service boundaries; not a full device stack budget.
Native shared-heap create/allocate instructions execute on a synthetic named
area. Only the original mutex's scheduler boundary is modeled. This fixture
does not prove hardware page backing, scheduling, available device heap or WBI.
"""
from pathlib import Path
import hashlib,json,struct,sys,zlib
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'vendor/audit-python')]
from verify_r5_m4strict_cp_cpu import new_cpu,SCRATCH,SP,STOP
from unicorn import UC_HOOK_CODE,UC_HOOK_BLOCK
from unicorn.arm_const import *
CPQ=0x90030001;APQ=0x80020002;STATE=0x1a39448;BANK_BYTES=28768
_build_file=OUT.parent/'cp/build.json'
_build=json.loads(_build_file.read_text()) if _build_file.exists() else {}
ALLOCATION_BYTES=_build.get('heap_bytes',52348)
HEAP_BASE=0x3600000;HEAP_BYTES=0x800000;HANDLE=0x195e254

def packet(token=1,config_hash=0,mask=0,op=1,build=0,bank_bytes=0):
 p=struct.pack('<4B7I',0xe8,1,op,32,0x32503552,token,config_hash,mask,bank_bytes,build,0)
 return p[:28]+struct.pack('<I',zlib.crc32(p[:28]))

class CPBridge:
 def __init__(self,image_path,heap_bytes=HEAP_BYTES):
  self.image=Path(image_path).read_bytes();self.cpu=u=new_cpu(self.image)
  self.heap_bytes=heap_bytes
  mapped=(heap_bytes+4095)&~4095
  u.mem_map(HEAP_BASE,mapped);u.mem_write(HEAP_BASE,b'\xa5'*mapped)
  u.reg_write(UC_ARM_REG_R0,HEAP_BASE);u.reg_write(UC_ARM_REG_R1,heap_bytes);u.reg_write(UC_ARM_REG_R2,1)
  u.emu_start(0x5ed108,STOP,count=200000)
  assert u.reg_read(UC_ARM_REG_PC)==STOP,'native heap create did not return'
  self.handle=u.reg_read(UC_ARM_REG_R0);assert self.handle==HEAP_BASE+8
  self.w(HANDLE,self.handle)
  self.MSG=SCRATCH+0x1000;self.OSAL_HEAP=SCRATCH+0x3000;self.OBJ=SCRATCH+0x5000
  self.OPS=SCRATCH+0x6000;self.SEND=SCRATCH+0x7f00
  self.w(0x193eb08,self.OPS);self.w(self.OPS,self.SEND|1);u.mem_write(self.OBJ,bytes(64))
  self.events=[];self.acks=[];self.dispatch=[];self.statuses=[]
  self.fail=None;self.loops=0;self.lock24=0;self.heap_lock=0;self.minsp=SP
  self.bank_attempts=0;self.bank_pointer=0;self.last_bank=None;self.native_oom=False
  boundaries=[0x5ef6ec,0x4612f2,0x5ef69c,0x5ed29c,0x5f3894,0x5ef6e8,
   0x5ea0dc,0x5ea0e4,0x5ede74,0x49604e,0x496056,0x49826c,0x345b98,
   0x495ffa,0x53c3c4,0x5d9b24,0x5b8d6c,0x5b8910,0xbaa416,0x53d394,
   0x53aac0,self.SEND,0x53c31c,0xb0de92,0x8989ac]
  for at in boundaries:u.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)
  u.hook_add(UC_HOOK_BLOCK,lambda cpu,at,size,arg: self.sample_stack(cpu))
 def sample_stack(self,cpu):
  self.minsp=min(self.minsp,cpu.reg_read(UC_ARM_REG_SP))
 def w(self,at,v):self.cpu.mem_write(at,struct.pack('<I',v))
 def r(self,at):return struct.unpack('<I',self.cpu.mem_read(at,4))[0]
 def ret(self,value=None):
  if value is not None:self.cpu.reg_write(UC_ARM_REG_R0,value&0xffffffff)
  self.cpu.reg_write(UC_ARM_REG_PC,self.cpu.reg_read(UC_ARM_REG_LR))
 def hook(self,cpu,at,size,_):
  self.minsp=min(self.minsp,cpu.reg_read(UC_ARM_REG_SP))
  if at in (0x5ef6ec,0x4612f2):raise AssertionError('unwanted Q/other allocation hook')
  args=[cpu.reg_read(r)for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if at==0x5ef69c:
   assert args[0]==ALLOCATION_BYTES and self.lock24==1
   self.bank_attempts+=1;self.events.append('bank_alloc6904')
   if self.fail=='bank_alloc':self.w(HANDLE,0)
   return
  if at==0x5ed29c:self.events.append('native_shared_heap_allocate');return
  if at==0x5f3894:self.native_oom=True;self.events.append('native_errno12');return
  if at==0x5ef6e8:
   self.bank_pointer=args[0];self.events.append('bank_return_'+hex(args[0]))
   if args[0]:
    assert HEAP_BASE<=args[0]<HEAP_BASE+self.heap_bytes-ALLOCATION_BYTES
    self.last_bank=(bytes(cpu.mem_read(args[0]-8,8)),bytes(cpu.mem_read(args[0]+ALLOCATION_BYTES,16)))
   return
  if at in (0x5ea0dc,0x5ea0e4):
   assert args[0]==0x1a38f00 and self.lock24==1
   if at==0x5ea0dc:assert self.heap_lock==0;self.heap_lock=1;self.events.append('heap_mutex_lock')
   else:assert self.heap_lock==1;self.heap_lock=0;self.events.append('heap_mutex_unlock')
   self.ret(0);return
  if at==0x5ede74:raise AssertionError('native allocator corruption diagnostic')
  if at in (0x49604e,0x496056):
   self.statuses.append(dict(at=hex(at),r0=args[0],r5=cpu.reg_read(UC_ARM_REG_R5),r6=cpu.reg_read(UC_ARM_REG_R6)))
  if at in (0x49826c,0x345b98):self.dispatch.append(at)
  if at not in (0x495ffa,0x53c3c4,0x5d9b24,0x5b8d6c,0x5b8910,0xbaa416,0x53d394,
                 0x53aac0,self.SEND,0x53c31c,0xb0de92,0x8989ac,0x49826c,0x345b98):return
  if at==0x495ffa:
   self.loops+=1
   if self.loops==2:cpu.emu_stop()
   return
  if at==0x53c3c4:
   assert args[0]==CPQ and args[2]==0xffffffff;self.w(args[1],self.MSG);self.ret(0)
  elif at==0x5b8d6c:
   assert args[0]==0x24 and self.lock24==0;self.lock24=1;self.events.append('lock24');self.ret(0)
  elif at==0x5b8910:
   assert args[0]==0x24 and self.lock24==1;self.lock24=0;self.events.append('unlock24');self.ret()
  elif at==0xbaa416:self.ret(self.OBJ)
  elif at==0x53d394:
   assert self.lock24==1 and args[1] in (128,256) and args[2]==0
   self.events.append('OSAL_alloc128_wait0');cpu.mem_write(self.OSAL_HEAP,bytes(512));self.w(args[3],0)
   self.ret(0 if self.fail=='alloc'else self.OSAL_HEAP)
  elif at==0x53aac0:self.events.append('allocation_diagnostic');self.ret()
  elif at==self.SEND:
   assert args[0]==APQ and self.lock24==1
   assert self.r(args[1]-8) in (32,44,128) and self.r(args[1]-12)==CPQ
   self.acks.append(bytes(cpu.mem_read(args[1],self.r(args[1]-8))));self.events.append('ACK_send')
   self.ret(0xffffffff if self.fail=='send'else 0)
  elif at==0x53c31c:
   if args[:2]==[CPQ,self.MSG]:self.events.append('release_request')
   else:assert args[:2]==[APQ,self.OSAL_HEAP+0x40];self.events.append('free_failed_ACK')
   self.ret()
  elif at in (0x49826c,0x345b98):
   assert args[:2]==[self.MSG,self.r(self.MSG-12)]
   self.events.append('native_class_dispatch');self.ret(0)
  elif at==0x8989ac:self.ret(0x157aa10)
  else:self.ret()
 def run(self,p,src=APQ,fail=None):
  self.fail=fail;self.loops=0;self.events.clear();self.acks.clear();self.dispatch.clear();self.statuses.clear();self.minsp=SP
  self.cpu.mem_write(self.MSG-24,bytes(24));self.w(self.MSG-12,src);self.w(self.MSG-8,len(p))
  self.cpu.mem_write(self.MSG,p+bytes(max(0,128-len(p))))
  before=bytes(self.cpu.mem_read(0x1197000,0x8a2448));self.native_oom=False
  self.cpu.reg_write(UC_ARM_REG_SP,SP);self.cpu.reg_write(UC_ARM_REG_LR,STOP|1)
  self.cpu.emu_start(0x495fd9,STOP,count=8000000)
  assert self.loops==2 and self.lock24==self.heap_lock==0
  assert self.events[-1]=='release_request' and self.events.count('lock24')==self.events.count('unlock24')==1
  assert self.events.count('release_request')==1 and bytes(self.cpu.mem_read(self.MSG,len(p)))==p
  if fail=='bank_alloc':self.w(HANDLE,self.handle)
  expected=bytearray(before)
  if self.native_oom:
   assert self.r(0x1a38f10)==12
   struct.pack_into('<I',expected,0x1a38f10-0x1197000,12)
  assert bytes(self.cpu.mem_read(0x1197000,0x8a2448))==bytes(expected),'original BSS changed beyond native OOM errno'
  if self.bank_pointer:
   assert self.r(STATE+4)==BANK_BYTES
   assert self.last_bank==(bytes(self.cpu.mem_read(self.bank_pointer-8,8)),bytes(self.cpu.mem_read(self.bank_pointer+ALLOCATION_BYTES,16)))
  return list(self.acks),list(self.events),SP-self.minsp,list(self.dispatch),list(self.statuses)

def create_cp_bridge(image_path):return CPBridge(image_path)
