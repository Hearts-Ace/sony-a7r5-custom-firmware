from elftools.elf.elffile import ELFFile
from thumb_ops import branch

RX=0x1195270
def link(objects,base=RX):
 data=bytearray();symbols={};locals=[];pending=[]
 for obj in objects:
  with obj.open('rb') as f:
   e=ELFFile(f);sections={};sy=e.get_section_by_name('.symtab');local={}
   for ix,s in enumerate(e.iter_sections()):
    if s['sh_flags']&4 and s['sh_size']:
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
 for oi,si,name,kind,off in pending:
  target=locals[oi].get(si,symbols.get(name));assert target and kind in(10,30),(name,kind)
  assert data[off:off+4] in (bytes.fromhex('fff7feff'),bytes.fromhex('fff7febf'))
  data[off:off+4]=branch(base+off,target&~1,kind==10)
 return bytes(data),symbols
