"""原生ARM64 MPR写头回放；只模型化普通libc/分配/诊断与等价DMA复制。"""
import io,re,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn import arm64_const as A
class NativeMpr:
 def __init__(self,raw):
  E=ELFFile(io.BytesIO(raw));blob=bytes(4096)
  u=self.u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);self.calls={};self.bad=[];self.logs=[];self.points=[];self.classify=[];self.trace=[];self.heap=0x51000000;self.extern={}
  for s in E.iter_segments():
   if s['p_type']=='PT_LOAD':
    lo=s['p_vaddr']&~4095;hi=(s['p_vaddr']+s['p_memsz']+4095)&~4095
    u.mem_map(lo,hi-lo);u.mem_write(s['p_vaddr'],s.data())
  sy=E.get_section_by_name('.dynsym')
  for sec in E.iter_sections():
   if sec['sh_type']!='SHT_RELA':continue
   for r in sec.iter_relocations():
    typ,a=r['r_info_type'],r['r_addend'];off=r['r_offset']
    if typ==1027:v=a
    elif typ in (257,1025,1026):
     s=sy.get_symbol(r['r_info_sym'])
     if s['st_value']:v=s['st_value']+a
     else:v=self.extern.setdefault(s.name,0x80010000+len(self.extern)*16)
    else:raise Exception(typ)
    u.mem_write(off,struct.pack('<Q',v))
  self.extrev={v:k for k,v in self.extern.items()}
  for a,n in [(0x50000000,0x4000000),(0x60000000,0x1000000),(0x70000000,0x200000),(0x80000000,0x20000)]:u.mem_map(a,n)
  u.mem_write(0x60000000,blob)
  self.blob=blob;self.obj=0x50000000;self.param=0x50010000;self.info=0x50020000
  u.hook_add(UC_HOOK_CODE,self.hook)
 def reg(self,i):return self.u.reg_read(getattr(A,'UC_ARM64_REG_X'+str(i)))
 def ret(self,n=0):self.u.reg_write(A.UC_ARM64_REG_X0,n&0xffffffffffffffff);self.u.reg_write(A.UC_ARM64_REG_PC,self.reg(30))
 def cstr(self,a):
  b=bytearray()
  while self.u.mem_read(a+len(b),1)!=b'\0':
   b.extend(self.u.mem_read(a+len(b),1));assert len(b)<100000
  return bytes(b)
 def hook(self,u,pc,size,_):
  self.trace.append(pc);self.trace=self.trace[-16:]
  if pc in (0x25f034,0x261e8c,0x261ea4,0x268928,0x261f48):return self.ret() # diagnostic transport only
  if pc==0x2b5028: # DMA memcpy: exact byte copy, no image/metadata substitute.
   x,y,n=self.reg(0),self.reg(1),self.reg(2);assert n<0x1000000;u.mem_write(x,bytes(u.mem_read(y,n)));return self.ret(x)
  name=self.extrev.get(pc)
  if not name:return
  self.calls[name]=self.calls.get(name,0)+1
  x,y,n=self.reg(0),self.reg(1),self.reg(2)
  if name=='osal_valloc_msg_wait':
   self.heap=(self.heap+15)&~15;v=self.heap;self.heap+=n+16;u.mem_write(y,struct.pack('<Q',v));return self.ret()
  if name=='snprintf':
   dst,n,fmtptr=x,y,n;fmt=self.cstr(fmtptr).decode();specs=re.findall(r'%[+0-9]*([dius])',fmt);count=len(specs)
   values=[self.reg(i) for i in range(3,8)]
   values += [struct.unpack('<Q',u.mem_read(u.reg_read(A.UC_ARM64_REG_SP)+i*8,8))[0] for i in range(max(0,count-5))]
   values=[self.cstr(v).decode() if t=='s' else v for t,v in zip(specs,values)]
   result=(fmt%tuple(values[:count])).encode()
   if n:u.mem_write(dst,result[:n-1]+b'\0')
   return self.ret(len(result))
  if name in ('osal_set_msg_content','osal_snd_msg','osal_get_time','osal_get_sys_time'):return self.ret()
  if name.startswith('_ZStls') or name.startswith('_ZNSo') or name.startswith('_ZSt4endl'):return self.ret(x) # stderr diagnostic
  if name in ('_Znwm','_Znam','malloc','calloc','realloc'):
   if name=='calloc':sz=x*y
   elif name=='realloc':sz=y
   else:sz=x
   assert sz<0x1000000,(name,sz)
   self.heap=(self.heap+15)&~15;v=self.heap;self.heap+=sz+16
   if name=='realloc' and x:u.mem_write(v,bytes(u.mem_read(x,min(y,0x1000))))
   return self.ret(v)
  if name in ('free','_ZdlPvm','_ZdaPvm','_ZdlPv','_ZdaPv'):return self.ret()
  if name in ('memcpy','memmove','__memcpy_chk','__memmove_chk'):
   assert n<0x1000000,(name,n);u.mem_write(x,bytes(u.mem_read(y,n)));return self.ret(x)
  if name in ('memset','__memset_chk'):
   assert n<0x1000000,(name,n);u.mem_write(x,bytes([y&255])*n);return self.ret(x)
  if name in ('memcmp','bcmp'):
   a,b=bytes(u.mem_read(x,n)),bytes(u.mem_read(y,n));return self.ret((a>b)-(a<b))
  if name=='strlen':return self.ret(len(self.cstr(x)))
  if name in ('strcmp','strncmp'):
   a,b=self.cstr(x),self.cstr(y)
   if name=='strncmp':a,b=a[:n],b[:n]
   return self.ret((a>b)-(a<b))
  if name in ('strcpy','strncpy'):
   a=self.cstr(y)+b'\0'
   if name=='strncpy':a=a[:n].ljust(n,b'\0')
   u.mem_write(x,a);return self.ret(x)
  if name in ('pthread_mutex_init','pthread_mutex_lock','pthread_mutex_unlock','pthread_mutex_destroy'):return self.ret()
  if name in ('__cxa_guard_acquire',):return self.ret(1)
  if name in ('__cxa_guard_release','__cxa_atexit'):return self.ret()
  raise Exception(('external',name,[hex(self.reg(i)) for i in range(5)], [hex(t) for t in self.trace]))
 def call(self,a,args):
  for k,v in enumerate(args):self.u.reg_write(getattr(A,'UC_ARM64_REG_X'+str(k)),v)
  self.u.reg_write(A.UC_ARM64_REG_SP,0x701f0000);self.u.reg_write(A.UC_ARM64_REG_LR,0x80000000)
  try:self.u.emu_start(a,0x80000000,count=10000000)
  except Exception:print('TRACE',list(map(hex,self.trace)));raise
  pc=self.u.reg_read(A.UC_ARM64_REG_PC);assert pc==0x80000000,hex(pc)
  return self.reg(0)
