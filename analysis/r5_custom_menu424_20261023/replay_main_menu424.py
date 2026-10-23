"""Offline exact-A64 main visible-list/title/cache-gate replay.

No device or code from the supplied ZIP is executed. Container trees, category
selection, model node storage, and profile/display services are explicit fixtures.
The full original secondary alias table is retained without the private key.
"""
from pathlib import Path
import argparse, hashlib, io, json, struct, sys
from collections import deque
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'analysis/r5_custom_filter423_20261023/menu_research')]
from read_menu import Image
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as R

BASE=ROOT/'analysis/r5_custom_filter423_20261023/ap/appFw.so'
AUDIT=json.loads((BASE.parent.parent/'import/module_audit.json').read_text())
RAM=0x20000000
STOP=RAM+0x3ff000
SP=RAM+0x3f0000
X=[getattr(R,'UC_ARM64_REG_X'+str(i)) for i in range(29)]+[R.UC_ARM64_REG_FP,R.UC_ARM64_REG_LR]

class VM:
 def __init__(self,path,bias):
  self.im=Image(path);self.path=path;self.bias=bias
  self.u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);self.events=[];self.trace=set();self.recent=deque(maxlen=180);self.alloc=RAM+0x30000
  self.fixture={};self.collected=[];self.profile=0;self.facade=0x582ca68
  elf=ELFFile(io.BytesIO(self.im.data))
  for s in elf.iter_segments():
   if s['p_type']!='PT_LOAD':continue
   lo=(s['p_vaddr']+bias)&-4096;hi=(s['p_vaddr']+s['p_memsz']+bias+4095)&-4096
   self.u.mem_map(lo,hi-lo)
   if s['p_filesz']:self.u.mem_write(s['p_vaddr']+bias,s.data())
  self.u.mem_map(RAM,0x400000)
  # Apply only actual ELF R_AARCH64_RELATIVE relocations, including moved PLT.
  for at,(info,value) in self.im.relocs.items():
   if info==1027:self.w64(at+bias,value+bias)
  self.sy={n:v+bias for n,v in AUDIT['symbols'].items()}
  self.u.hook_add(UC_HOOK_CODE,self.hook)
  self.call(self.sy['r5_filter_menu_register'],RAM+0x100,RAM+0x100,RAM+0x100)
  self.desc=self.sy['r5_filter_menu_descriptor']
  assert self.u.mem_read(self.desc+0x28,3)==b'\1\1\1'
  self.secondary=list(struct.iter_unpack('<II',self.im.read(0x3e41c38,0x31a8)))
  assert len(self.secondary)==1589 and [k for k,v in self.secondary]==list(range(1589))
  assert 0x635 not in dict(self.secondary)
  self.map_at_got(0x5959e80,self.secondary,'u32')
  primary=list(struct.iter_unpack('<II',self.im.read(0x3e44de0,0x31a8)))
  self.map_at_got(0x593fbd8,primary,'u32')
  kind=list(struct.iter_unpack('<II',self.im.read(0x3e27668,0x31a8)))
  self.map_at_got(0x591abf8,kind,'u32')
  pairs=[]
  for a in range(0x502a980,0x5030590,16):pairs.append((struct.unpack('<Q',self.im.read(a,8))[0],self.im.pointer(a+8)+bias))
  assert not any(k==0x635 for k,v in pairs)
  pairs.append((0x635,self.desc));self.map_at_got(0x59611f8,pairs,'ptr')
  # Original concrete-state map is absent for private menu. An empty container
  # deliberately exercises real native "no cached concrete record" fallback.
  self.map_at_got(0x5947870,[],'ptr')
  self.membership=set()
  self.cachebase=self.q(0x5928070+bias)
  self.w64(0x591f9a8+bias,self.facade+bias-0x10)
  self.category=RAM+0x1000
  self.w32(self.category+8,1)
  # Category isolation retains the actual inserted final group record byte-for-byte.
  self.u.mem_write(self.category+0x10,bytes(self.u.mem_read(0x5053628+bias,0x2e0)))
  self.group=self.category+0x10
  # Select only the private slot; group/category filtering itself is outside scope.
  slot=bytes(self.u.mem_read(self.group+0x10+2*24,24))
  assert struct.unpack_from('<Q',slot)[0]==0x635
  self.w32(self.group+8,1);self.u.mem_write(self.group+0x10,slot)
  self.model=RAM+0x8000;self.slots=RAM+0x8100;self.indices=RAM+0x8200
  self.node0=RAM+0x8300;self.node1=RAM+0x8400
  self.w64(self.model+0x40,self.slots);self.w32(self.indices,0);self.w32(self.indices+4,1)
  self.w64(self.slots,self.node0);self.w64(self.slots+16,self.node1)

 def w32(self,a,v):self.u.mem_write(a,struct.pack('<I',v&0xffffffff))
 def w64(self,a,v):self.u.mem_write(a,struct.pack('<Q',v&0xffffffffffffffff))
 def q(self,a):return struct.unpack('<Q',self.u.mem_read(a,8))[0]
 def d(self,a):return struct.unpack('<I',self.u.mem_read(a,4))[0]
 def ret(self,value=0):
  self.u.reg_write(R.UC_ARM64_REG_X0,value&0xffffffffffffffff)
  self.u.reg_write(R.UC_ARM64_REG_PC,self.u.reg_read(R.UC_ARM64_REG_LR))
 def tree(self,items,kind):
  items=sorted(items);base=self.alloc;self.alloc+=0x40
  sentinel=base+8
  def build(lo,hi,parent):
   if lo>=hi:return 0
   mid=(lo+hi)//2;key,value=items[mid];node=self.alloc;self.alloc+=0x40
   left=build(lo,mid,node);right=build(mid+1,hi,node)
   self.w64(node+8,parent);self.w64(node+0x10,left);self.w64(node+0x18,right);self.w32(node+0x20,key)
   if kind=='u32':self.w32(node+0x24,value)
   else:self.w64(node+0x28,value)
   return node
  root=build(0,len(items),sentinel)
  self.w32(base+8,0);self.w64(base+0x10,root)
  self.w64(base+0x18,root);self.w64(base+0x20,sentinel);self.w64(base+0x28,len(items))
  return base
 def map_at_got(self,got,items,kind):
  at=self.tree(items,kind);self.w64(got+self.bias,at);return at
 def hook(self,u,pc,size,arg):
  if pc==STOP:u.emu_stop();return
  at=pc-self.bias;self.trace.add(at);self.recent.append(hex(at))
  a=[u.reg_read(r) for r in X[:5]]
  if at in (0x1bcfea4,0x1bd8580,0x1bd9f04,0x1bc84a0,0x1bc88e8,0x1bdaec4,0x1bdfc80):self.events.append((hex(at),[hex(x)for x in a[:2]]))
  if pc in (self.sy['r5_native_menu_insert'],self.sy['r5_native_row_insert']):
   self.collected.append(tuple(a[:3]));self.ret();return
  if at==0x16d9770:
   u.mem_write(a[0],bytes(u.mem_read(a[1],a[2])));self.ret(a[0]);return
  if at==0x1bc4910:self.ret(self.category if a[1]==3 else 0);return
  if at==0x1bd7314:self.ret(self.profile);return
  if at==0x1be0110:self.ret(1 if self.d(a[1]) in self.membership else 0);return
  if at==0x1be0324:self.membership.add(self.d(a[1]));self.ret();return
  if at in (0x1bcb6d8,0x1bc7998):self.ret(0);return
  if at==0x1bcfd88:
   # Product/profile visibility mapping service; 0=first model branch.
   self.ret(a[1]);return
  if at==0x1bd55fc:self.ret(0xffffffff);return
  if at in (0x1bd7018,0x1bde9d8,0x1bdeaf4):self.ret(0);return
  if at==0x1afe958:self.ret(self.q(self.q(a[0])));return
  if at==0x16dc130:
   atmem=self.alloc;self.alloc=(self.alloc+a[0]+15)&-16;self.ret(atmem);return
  if pc==self.sy['name_char']:
   self.events.append(('name_char',bytes(u.mem_read(a[1],96)).split(b'\0')[0].decode('utf-8')));self.ret();return
  if pc==self.sy['name_id']:
   self.events.append(('name_id',a[1]));self.ret();return
  if at in (0x35b858c,0x16db710):raise AssertionError(('native assert',hex(at),[hex(x)for x in a],hex(u.reg_read(R.UC_ARM64_REG_LR))))
 def call(self,pc,*args):
  for i in range(19,30):self.u.reg_write(X[i],0x111100000000+i)
  for i,a in enumerate(args):self.u.reg_write(X[i],a)
  self.u.reg_write(R.UC_ARM64_REG_SP,SP);self.u.reg_write(R.UC_ARM64_REG_LR,STOP)
  try:self.u.emu_start(pc,STOP,count=1000000)
  except Exception as exc:raise RuntimeError(('replay fault',hex(pc),hex(self.u.reg_read(R.UC_ARM64_REG_PC)),hex(self.u.reg_read(R.UC_ARM64_REG_LR)),self.events,list(self.recent))) from exc
  assert self.u.reg_read(R.UC_ARM64_REG_PC)==STOP,hex(self.u.reg_read(R.UC_ARM64_REG_PC))
  assert self.u.reg_read(R.UC_ARM64_REG_SP)==SP
  assert all(self.u.reg_read(X[i])==0x111100000000+i for i in range(19,30))
  return self.u.reg_read(R.UC_ARM64_REG_X0)
 def native(self,pc,*args):return self.call(pc+self.bias,*args)
 def facade_use(self,va):
  self.facade=va;self.w64(RAM+0x9000,va+self.bias)
  self.w64(0x591f9a8+self.bias,va+self.bias-0x10)
  return RAM+0x9000
 def visible(self,facade,mode):
  this=self.facade_use(facade);self.trace.clear()
  self.native(0x1bd9b9c,this,mode)
  countp=self.q((0x591f398 if mode else 0x59828c0)+self.bias)
  listp=self.q((0x595df20 if mode else 0x598b6c0)+self.bias)
  return list(struct.iter_unpack('<II',bytes(self.u.mem_read(listp,self.d(countp)*8))))
 def title(self,facade,mid,producer):
  self.facade_use(facade);self.w32(self.node0+0x30,0xdeadbeef)
  self.native(producer,self.model,mid,self.indices)
  resource=self.d(self.node0+0x30)
  self.events.clear();self.call(self.sy['r5_filter_menu_name_draw'],RAM+0x8500,resource)
  return resource,list(self.events)

def main():
 p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path);p.add_argument('--output',type=Path,default=HERE/'main_menu424_replay.json');args=p.parse_args()
 paths=[('source423',BASE)]+([('candidate424',args.candidate.resolve())]if args.candidate else [])
 results=[]
 for label,path in paths:
  for bias in (0,0x40000000,0x7000000000):
   vm=VM(path,bias)
   old=[]
   for key,value in vm.secondary:
    assert vm.native(0x1bd2020,0,key)==value;old.append(key)
   for key in (0x636,0x7fffffff,0x80000000,0xffffffff):assert vm.native(0x1bd2020,0,key)==0xca4
   wanted=0x635 if label=='candidate424'else 0xca4
   assert vm.native(0x1bd2020,0,0x635)==wanted
   views=[]
   for facade in (0x582ca68,0x582d618):
    for mode in (0,1):
     rows=vm.visible(facade,mode);assert rows==[(0,wanted)],rows
     titles=[]
     for producer in (0x2218cc8,0x221eee0):
      resource,draw=vm.title(facade,rows[0][1],producer)
      if label=='candidate424':assert resource==0x02ff4230 and draw==[('name_char','自定义滤镜')],(resource,draw)
      else:assert resource!=0x02ff4230
      titles.append(dict(producer=hex(producer),resource=hex(resource),text_dispatch=draw))
     this=vm.facade_use(facade)
     concrete=vm.native(0x1bd9f04,this,0x635);assert concrete==0
     present=vm.native(0x1bd027c,this,0x635);assert present==1
     available=vm.native(0x1bcfea4,this,0x635);assert available==1
     produced=rows[0][1]
     produced_present=vm.native(0x1bd027c,this,produced)
     # Direct existence is meaningful for the actual produced MID. The old
     # CA4 fallback may describe a default menu and is never the private entry.
     assert produced_present==(1 if label=='candidate424' else 0)
     cached_byte=None
     if facade==0x582d618:
      cached_byte=bytes(vm.u.mem_read(vm.cachebase+0x635*24,24)).hex()
      before=len(vm.membership);assert vm.native(0x1bcfea4,this,0x635)==1 and len(vm.membership)==before
     views.append(dict(facade=hex(facade),mode=mode,rows=rows,titles=titles,concrete_private_record=concrete,present=present,available=available,produced_mid_present=produced_present,private_cache_record=cached_byte))
   results.append(dict(label=label,path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bias=hex(bias),old_alias_keys_checked=len(old),secondary_source_sha256=hashlib.sha256(vm.im.read(0x3e41c38,0x31a8)).hexdigest(),private_key_absent_from_fixture=True,views=views))
 report=dict(passed=True,AP_sha256=hashlib.sha256(args.candidate.read_bytes()).hexdigest() if args.candidate else None,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),source423_sha256=hashlib.sha256(BASE.read_bytes()).hexdigest(),rows=results,limits=['Exact A64 visible-loop and title/cache-gate methods execute. Full original secondary alias table is represented as a balanced tree, not by executing allocation/constructors.','Only the actual inserted custom parent slot is exposed by an isolated category fixture. Profile index, model node storage, special-menu/category services and model visibility mapping remain fixtures.','Cached facade executes native 1BDFB0C cache producer and 1BE03AC consumer against the original GOT5928070 memory; hash membership lookup/insert functions 1BE0110/1BE0324 are explicit container fixtures. Cache capacity is a separate static acceptance check.','name_draw routes actual title ID to actual private UTF-8 string; no font rasterizer, physical LCD, UI event loop, boot or device execution.'])
 args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(passed=True,rows=len(results),output=str(args.output))))
if __name__=='__main__':main()
