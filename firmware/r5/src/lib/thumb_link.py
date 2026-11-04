import struct
from elftools.elf.elffile import ELFFile
from thumb_ops import branch

RX=0x1195270
def link(objects,base=RX,externals=None,drop_sections=(),read_only=False,audit=None):
 data=bytearray();symbols=dict(externals or {});locals=[];pending=[]
 dropped=set();references=set();dropped_rows=[]
 for obj in objects:
  with obj.open('rb') as f:
   e=ELFFile(f);sections={};sy=e.get_section_by_name('.symtab');local={}
   for ix,s in enumerate(e.iter_sections()):
    if s.name in drop_sections:
     dropped.add(s.name)
     # This option removes only entirely unreferenced private helpers, not
     # native code or a live filter path. An incoming relocation fails below.
     removed_symbols=[]
     for symbol in sy.iter_symbols():
      if symbol['st_shndx']==ix and symbol.name:
       references.add(symbol.name);removed_symbols.append(symbol.name)
     dropped_rows.append(dict(object=obj.name,section=s.name,bytes=s['sh_size'],symbols=removed_symbols,incoming_relocations=[]))
     continue
    if s['sh_size'] and (s['sh_flags']&4 or
       (read_only and s['sh_type']=='SHT_PROGBITS' and s['sh_flags']&2 and not s['sh_flags']&1)):
     while len(data)%4:data.append(0)
     sections[ix]=len(data);data+=s.data()
   for ix,s in enumerate(sy.iter_symbols()):
    if s['st_shndx'] in sections:
     value=base+sections[s['st_shndx']]+s['st_value'];local[ix]=value
     if s['st_info']['bind']=='STB_GLOBAL':
      assert s.name not in symbols;symname=s.name;symbols[symname]=value
   for section in e.iter_sections():
    if section['sh_type']!='SHT_REL' or section['sh_info'] not in sections:continue
    for r in section.iter_relocations():
     s=sy.get_symbol(r['r_info_sym']);pending.append((len(locals),r['r_info_sym'],s.name,r['r_info_type'],sections[section['sh_info']]+r['r_offset']))
   locals.append(local)
 assert dropped==set(drop_sections),(dropped,drop_sections)
 assert not references.intersection(name for _,_,name,_,_ in pending),('Referenced section cannot be dropped',references)
 for oi,si,name,kind,off in pending:
  target=locals[oi].get(si,symbols.get(name));assert target is not None and kind in(2,10,30),(name,kind)
  if kind==2:
   addend=struct.unpack_from('<I',data,off)[0];value=target+addend
   assert 0<=value<=0xffffffff
   struct.pack_into('<I',data,off,value);continue
  assert data[off:off+4] in (bytes.fromhex('fff7feff'),bytes.fromhex('fff7febf'))
  data[off:off+4]=branch(base+off,target&~1,kind==10)
 if audit is not None:audit.update(dict(dropped_sections=dropped_rows,dropped_bytes=sum(x['bytes']for x in dropped_rows),incoming_relocations_to_removed_sections=0,all_retained_relocations_resolved=True,retained_bytes=len(data)))
 return bytes(data),symbols
