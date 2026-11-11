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

def link(objects,rx,rw,rx_prefix,externals=None,*,gc_objects=None,gc_report=None,
         extra_rx_objects=None,extra_rx_base=0,extra_rx_size=0,extra_rx_output=None,merge_strings=False,drop_unused_functions=()):
 sections={};globals_=dict(externals or {});streams=[];rxdata=bytearray(rx_prefix);rwdata=bytearray();bss_end=0;extra_data=bytearray()
 # All R/X inputs receive RX mapping, writable initialized inputs RW, NOBITS
 # after file-backed RW. No dynamic/GOT/TLS or writable code is supported.
 records=[];elfs={}
 for obj in objects:
  f=obj.open('rb');streams.append(f);e=ELFFile(f)
  if e['e_machine']!='EM_AARCH64' or e['e_type']!='ET_REL':raise ValueError('Expected AArch64 REL')
  elfs[str(obj)]=e
  for ix,s in enumerate(e.iter_sections()):
   if not(s['sh_flags']&2):continue
   if s['sh_flags']&0x400 or s['sh_flags']&1 and s['sh_flags']&4:raise ValueError('TLS/WX input')
   records.append((str(obj),ix,s))
 # Retain the full baseline. Only explicitly selected new objects may lose
 # unreferenced sections; relocation edges retain callbacks/constants/BSS.
 selected={str(Path(p))for p in(gc_objects or ())}
 extra_objects={str(Path(p))for p in(extra_rx_objects or ())}
 if not(selected|extra_objects)<=elfs.keys():raise ValueError('Unknown optional objects')
 if extra_objects:
  if extra_rx_output is None or not extra_rx_base or extra_rx_size<=0:raise ValueError('Extra RX output/range required')
  if not(extra_rx_base+extra_rx_size<=rx or rx+65536<=extra_rx_base):raise ValueError('Extra RX overlaps main RX')
 all_sections={(obj,ix):s for obj,ix,s in records}
 live={key for key in all_sections if key[0]not in selected}
 if selected:
  definitions={};edges={}
  for obj,e in elfs.items():
   syms=e.get_section_by_name('.symtab')
   if syms is None:raise ValueError('Missing symbol table')
   for s in syms.iter_symbols():
    if s['st_info']['bind']in['STB_GLOBAL','STB_WEAK']and s['st_shndx']!='SHN_UNDEF':definitions.setdefault(s.name,[]).append((obj,s))
   for rsec in e.iter_sections():
    if rsec['sh_type']in['SHT_RELA','SHT_REL']:edges.setdefault((obj,rsec['sh_info']),[]).append(rsec)
  pending=list(live)
  def retain(obj,s):
   ix=s['st_shndx']
   if ix=='SHN_ABS':return
   if ix=='SHN_UNDEF':
    if s.name in(externals or {}):return
    candidates=definitions.get(s.name,[])
    if not candidates:raise ValueError(('Undefined symbol',obj,s.name))
    for other,symbol in candidates:retain(other,symbol)
    return
   key=(obj,ix)
   if key not in all_sections:raise ValueError(('Symbol outside allocated section',obj,s.name,ix))
   if key not in live:live.add(key);pending.append(key)
  while pending:
   key=pending.pop();obj=key[0];syms=elfs[obj].get_section_by_name('.symtab')
   for rsec in edges.get(key,[]):
    if rsec['sh_type']!='SHT_RELA':raise ValueError('REL unsupported')
    for r in rsec.iter_relocations():retain(obj,syms.get_symbol(r['r_info_sym']))
 # Only named legacy private helpers with zero relocation consumers can be
 # retired. Native detour/RELA roots must be excluded explicitly by caller.
 for name in drop_unused_functions:
  matches=[]
  for obj,e in elfs.items():
   syms=e.get_section_by_name('.symtab')
   for sym in syms.iter_symbols():
    if sym.name==name and sym['st_shndx']!='SHN_UNDEF':
     if sym['st_info']['type']!='STT_FUNC' or sym['st_value']!=0:raise ValueError('Non-whole-function drop')
     matches.append((obj,sym['st_shndx']))
   for rsec in e.iter_sections():
    if rsec['sh_type']=='SHT_RELA':
     for r in rsec.iter_relocations():
      symbol=syms.get_symbol(r['r_info_sym'])
      if symbol.name==name:raise ValueError(('Dropped private helper has consumer',name,obj))
  if len(matches)!=1:raise ValueError(('Missing unique retired private helper',name,matches))
  owner,section_index=matches[0]
  syms=elfs[owner].get_section_by_name('.symtab')
  for rsec in elfs[owner].iter_sections():
   if rsec['sh_type']=='SHT_RELA':
    for r in rsec.iter_relocations():
     if syms.get_symbol(r['r_info_sym'])['st_shndx']==section_index:raise ValueError(('Dropped helper section alias consumer',name))
  live.discard(matches[0])
 dropped=[(obj,ix,s)for obj,ix,s in records if(obj,ix)not in live]
 dropped_keys={(obj,ix)for obj,ix,s in dropped}
 if gc_report is not None:
  gc_report.update(eligible_objects=sorted(selected),dropped_sections=[dict(object=obj,index=ix,name=s.name,size=s['sh_size'],flags=s['sh_flags'])for obj,ix,s in dropped],dropped_allocated_bytes=sum(s['sh_size']for obj,ix,s in dropped),baseline_sections_preserved=all((obj,ix)in live for obj,ix,s in records if obj not in selected))
 records=[(obj,ix,s)for obj,ix,s in records if(obj,ix)in live]
 # Standard ELF SHF_MERGE|SHF_STRINGS semantics, restricted to immutable
 # single-byte NUL strings with no relocations of their own. Map every input
 # byte independently, including symbol+addend interior references. Code,
 # numeric constants, initialized data and all BSS remain outside this merge.
 merged={};pool=bytearray();pool_items={}
 if merge_strings:
  for obj,ix,s in records:
   if s['sh_type']!='SHT_PROGBITS' or s['sh_flags']!=0x32:continue
   if s['sh_addralign']!=1 or s['sh_entsize']!=1:raise ValueError('Unexpected merge-string layout')
   data=s.data()
   if data and data[-1]:raise ValueError('Unterminated merge-string section')
   if any(r['sh_type'] in ['SHT_RELA','SHT_REL'] and r['sh_info']==ix and r['sh_size'] for r in elfs[obj].iter_sections()):raise ValueError('Relocations in merge strings')
   merged[(obj,ix)]=(s,data)
  for s,data in merged.values():
   for item in data.split(b'\0')[:-1]:
    item+=b'\0'
    if item not in pool_items:
     suffix=next((at+len(previous)-len(item)for previous,at in pool_items.items()if previous.endswith(item)),None)
     if suffix is None:pool_items[item]=len(pool);pool.extend(item)
     else:pool_items[item]=suffix
  poolbase=rx+len(rxdata);rxdata.extend(pool)
  for key,(s,data) in merged.items():
   mapping={};fragments=[];off=0
   for item in data.split(b'\0')[:-1]:
    item+=b'\0';at=poolbase+pool_items[item]
    for j in range(len(item)):mapping[off+j]=at+j
    fragments.append(dict(va=at,size=len(item),input_offset=off));off+=len(item)
   sections[key]={'va':poolbase,'data':bytearray(),'size':len(data),'space':'merged_strings','name':s.name,'address_map':mapping,'fragments':fragments}
  records=[row for row in records if(row[0],row[1])not in merged]
  if gc_report is not None:gc_report['merged_strings']={'input_bytes':sum(len(data)for _,data in merged.values()),'output_bytes':len(pool),'identical_or_exact_suffix':True,'sections':len(merged),'input_byte_mapping_complete':True}
 for isbss in [False,True]:
  # Place only the new read-only/executable sections largest-first. This
  # fills a bounded spare span without changing any baseline allocation order
  # or writable/BSS order. Every address remains resolved by its relocation.
  optional=lambda row:row[0]in extra_objects and not(row[2]['sh_flags']&1)and row[2]['sh_type']=='SHT_PROGBITS'
  allocation=records if isbss else [r for r in records if not optional(r)]+sorted((r for r in records if optional(r)),key=lambda r:(-r[2]['sh_addralign'],-r[2]['sh_size'],r[0],r[1]))
  for obj,ix,s in allocation:
   if (s['sh_type']=='SHT_NOBITS')!=isbss:continue
   if s['sh_type'] not in ['SHT_PROGBITS','SHT_NOBITS']:raise ValueError(('Unsupported allocated section',s.name,s['sh_type']))
   if isbss:
    if not(s['sh_flags']&1):raise ValueError('Read-only NOBITS unsupported')
    bss_end=align(max(bss_end,len(rwdata)),max(1,s['sh_addralign']));at=rw+bss_end;bss_end+=s['sh_size'];data=bytearray(s['sh_size']);space='bss'
   else:
    # The extra span is already executable in the original PT_LOAD. The image
    # builder must prove it is vacated data and no native reader still uses it.
    extra=obj in extra_objects and not(s['sh_flags']&1)
    if extra:
     extra_offset=align(extra_rx_base+len(extra_data),max(1,s['sh_addralign']))-extra_rx_base
     extra=extra_offset+s['sh_size']<=extra_rx_size
    dest=extra_data if extra else rwdata if s['sh_flags']&1 else rxdata;base=extra_rx_base if extra else rw if s['sh_flags']&1 else rx
    offset=extra_offset if extra else align(len(dest),max(1,s['sh_addralign']));dest.extend(bytes(offset-len(dest)));at=base+offset;data=bytearray(s.data());dest.extend(data);space='extra_rx'if extra else'rw'if s['sh_flags']&1 else'rx'
   sections[(obj,ix)]={'va':at,'data':data,'size':s['sh_size'],'space':space,'name':s.name}
 def value(obj,s,addend=0):
  ix=s['st_shndx']
  if ix=='SHN_ABS':return s['st_value']+addend
  if ix=='SHN_UNDEF':
   if s.name not in globals_:raise ValueError(('Undefined symbol',obj,s.name))
   return globals_[s.name]+addend
  key=(obj,ix)
  if key not in sections:raise ValueError(('Symbol outside allocated section',obj,s.name,ix))
  if not 0<=s['st_value']<=sections[key]['size']:raise ValueError('Symbol bounds')
  if 'address_map'in sections[key]:
   if s['st_value']+addend not in sections[key]['address_map']:raise ValueError(('Merged string reference outside input',obj,s.name,addend))
   return sections[key]['address_map'][s['st_value']+addend]
  return sections[key]['va']+s['st_value']+addend
 for f in streams:
  e=ELFFile(f);obj=str(Path(f.name));syms=e.get_section_by_name('.symtab')
  for s in syms.iter_symbols():
   if s['st_info']['bind'] not in ['STB_GLOBAL','STB_WEAK']or s['st_shndx']=='SHN_UNDEF':continue
   if(obj,s['st_shndx'])in dropped_keys:continue
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
    off=r['r_offset'];kind=r['r_info_type'];sym=syms.get_symbol(r['r_info_sym']);target=value(obj,sym,r['r_addend']);at=rec['va']+off
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
  if rec['space']=='merged_strings':continue
  if rec['space']=='bss':
   if any(rec['data']):raise ValueError('Relocated BSS is not zero')
   continue
  dest=extra_data if rec['space']=='extra_rx'else rwdata if rec['space']=='rw'else rxdata;base=extra_rx_base if rec['space']=='extra_rx'else rw if rec['space']=='rw'else rx
  off=rec['va']-base;dest[off:off+rec['size']]=rec['data']
 for f in streams:f.close()
 if extra_rx_output is not None:extra_rx_output.update(base=extra_rx_base,capacity=extra_rx_size,data=bytes(extra_data))
 elif extra_data:raise ValueError('Missing extra RX output')
 layout=[]
 for k,v in sections.items():
  if v['space']=='merged_strings':
   layout.extend(dict(object=k[0],index=k[1],name=v['name']+'['+str(f['input_offset'])+']',va=hex(f['va']),size=f['size'],space='rx')for f in v['fragments'])
  else:layout.append(dict(object=k[0],index=k[1],name=v['name'],va=hex(v['va']),size=v['size'],space=v['space']))
 return bytes(rxdata),bytes(rwdata),max(bss_end,len(rwdata)),globals_,relocations,layout
