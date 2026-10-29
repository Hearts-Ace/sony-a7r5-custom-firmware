"""Narrow static AArch64 linker. No unresolved symbols, unsupported relocation,
opcode mismatch, truncation, overlap or silent branch veneer is admitted.
No dynamic relocation/constructor is created. Not a general ELF linker.
"""
from pathlib import Path
import struct
from elftools.elf.elffile import ELFFile

def align(v,n):
 if n<1 or n&(n-1):raise ValueError('non-power-of-two alignment')
 return(v+n-1)&-n

def branch(at,target,link=False):
 d=target-at
 if d&3 or not -(1<<27)<=d<(1<<27):raise ValueError('B/BL range')
 return struct.pack('<I',(0x94000000 if link else 0x14000000)|((d>>2)&0x3ffffff))

def link(objects,rx,rw,rx_prefix,externals=None):
 sections={};globals_=dict(externals or {});streams=[];rxdata=bytearray(rx_prefix);rwdata=bytearray();bss_end=0
 # All R/X inputs receive RX mapping, writable initialized inputs RW, NOBITS
 # after file-backed RW. No dynamic/GOT/TLS or writable code is supported.
 records=[]
 for obj in objects:
  f=obj.open('rb');streams.append(f);e=ELFFile(f)
  if e['e_machine']!='EM_AARCH64' or e['e_type']!='ET_REL':raise ValueError('Expected AArch64 REL')
  for ix,s in enumerate(e.iter_sections()):
   if not(s['sh_flags']&2):continue
   if s['sh_flags']&0x400 or s['sh_flags']&1 and s['sh_flags']&4:raise ValueError('TLS/WX input')
   records.append((str(obj),ix,s))
 for isbss in [False,True]:
  for obj,ix,s in records:
   if (s['sh_type']=='SHT_NOBITS')!=isbss:continue
   if s['sh_type'] not in ['SHT_PROGBITS','SHT_NOBITS']:raise ValueError(('Unsupported allocated section',s.name,s['sh_type']))
   if isbss:
    if not(s['sh_flags']&1):raise ValueError('Read-only NOBITS unsupported')
    bss_end=align(max(bss_end,len(rwdata)),max(1,s['sh_addralign']));at=rw+bss_end;bss_end+=s['sh_size'];data=bytearray(s['sh_size']);space='bss'
   else:
    dest=rwdata if s['sh_flags']&1 else rxdata;base=rw if s['sh_flags']&1 else rx
    offset=align(len(dest),max(1,s['sh_addralign']));dest.extend(bytes(offset-len(dest)));at=base+offset;data=bytearray(s.data());dest.extend(data);space='rw'if s['sh_flags']&1 else'rx'
   sections[(obj,ix)]={'va':at,'data':data,'size':s['sh_size'],'space':space,'name':s.name}
 def value(obj,s):
  ix=s['st_shndx']
  if ix=='SHN_ABS':return s['st_value']
  if ix=='SHN_UNDEF':
   if s.name not in globals_:raise ValueError(('Undefined symbol',obj,s.name))
   return globals_[s.name]
  key=(obj,ix)
  if key not in sections:raise ValueError(('Symbol outside allocated section',obj,s.name,ix))
  if not 0<=s['st_value']<=sections[key]['size']:raise ValueError('Symbol bounds')
  return sections[key]['va']+s['st_value']
 for f in streams:
  e=ELFFile(f);obj=str(Path(f.name));syms=e.get_section_by_name('.symtab')
  for s in syms.iter_symbols():
   if s['st_info']['bind'] not in ['STB_GLOBAL','STB_WEAK']or s['st_shndx']=='SHN_UNDEF':continue
   if s.name in globals_:raise ValueError(('Duplicate global',s.name))
   globals_[s.name]=value(obj,s)
 relocations=[]
 for f in streams:
  e=ELFFile(f);obj=str(Path(f.name));syms=e.get_section_by_name('.symtab')
  for rsec in e.iter_sections():
   if rsec['sh_type'] not in ['SHT_RELA','SHT_REL']:continue
   key=(obj,rsec['sh_info'])
   if key not in sections:continue
   if rsec['sh_type']!='SHT_RELA':raise ValueError('REL unsupported')
   rec=sections[key];data=rec['data']
   for r in rsec.iter_relocations():
    off=r['r_offset'];kind=r['r_info_type'];sym=syms.get_symbol(r['r_info_sym']);target=value(obj,sym)+r['r_addend'];at=rec['va']+off
    if kind==257:
     # Extra segments belong to ET_DYN. Absolute pointers would need native
     # runtime relocation/bias handling that this narrow linker never adds.
     raise ValueError('ABS64 unsupported for dormant PIE payload')
    else:
     if off<0 or off+4>len(data)or off&3:raise ValueError('Instruction relocation bounds')
     w=struct.unpack_from('<I',data,off)[0]
     if kind in [282,283]:
      op=0x14000000 if kind==282 else 0x94000000
      if w&0xfc000000!=op:raise ValueError('B/BL opcode')
      w=struct.unpack('<I',branch(at,target,kind==283))[0]
     elif kind==275:
      if w&0x9f000000!=0x90000000:raise ValueError('ADRP opcode')
      d=(target>>12)-(at>>12)
      if not -(1<<20)<=d<(1<<20):raise ValueError('ADRP range')
      w=(w&~0x60ffffe0)|((d&3)<<29)|(((d>>2)&0x7ffff)<<5)
     elif kind==277:
      if w&0x7f400000!=0x11000000:raise ValueError('ADD immediate opcode')
      w=(w&~0x3ffc00)|((target&4095)<<10)
     elif kind in [278,284,285,286,299]:
      shift={278:0,284:1,285:2,286:3,299:4}[kind]
      if target&((1<<shift)-1):raise ValueError('LDST alignment')
      if w&0x3b000000!=0x39000000:raise ValueError('LDST unsigned offset opcode')
      # SIMD128 has size00 + opc11; general-regs compile avoids it here.
      if kind!=299 and w>>30!=shift:raise ValueError('LDST width mismatch')
      if kind==299 and w&0x3f000000!=0x3d000000:raise ValueError('LDST128 opcode')
      w=(w&~0x3ffc00)|(((target&4095)>>shift)<<10)
     else:raise ValueError(('Unsupported relocation',kind,sym.name))
     struct.pack_into('<I',data,off,w)
    relocations.append({'kind':kind,'site':hex(at),'target':hex(target),'symbol':sym.name,'source_object':obj})
 # Reassemble patched sections into disjoint segment buffers.
 for rec in sections.values():
  if rec['space']=='bss':
   if any(rec['data']):raise ValueError('Relocated BSS is not zero')
   continue
  dest=rwdata if rec['space']=='rw'else rxdata;base=rw if rec['space']=='rw'else rx
  off=rec['va']-base;dest[off:off+rec['size']]=rec['data']
 for f in streams:f.close()
 layout=[dict(object=k[0],index=k[1],name=v['name'],va=hex(v['va']),size=v['size'],space=v['space'])for k,v in sections.items()]
 return bytes(rxdata),bytes(rwdata),max(bss_end,len(rwdata)),globals_,relocations,layout
