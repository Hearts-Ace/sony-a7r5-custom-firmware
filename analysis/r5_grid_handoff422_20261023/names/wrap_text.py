from pathlib import Path
import hashlib,json,struct
ROOT=Path(__file__).resolve().parents[3];O=Path(__file__).resolve().parent
b=(ROOT/'build_r5_m4strict_4.04_20261015/patched/appFw.so').read_bytes();start=0x1884000;end=0x1887000;entry=0x1885688
shstr=b'\0.text\0.symtab\0.strtab\0.shstrtab\0';st=b'\0native_text_render\0native_resource_resolve\0'
data=bytearray(0x100);off=len(data);data+=b[start:end];sections=[(0,)*10,(1,1,6,start,off,end-start,0,0,4,0)]
syms=bytes(24)+struct.pack('<IBBHQQ',1,0x12,0,1,entry,0)+struct.pack('<IBBHQQ',st.index(b'native_resource_resolve'),0x12,0,1,0x1885178,0x128)
for n,blob,t,l,i,align,entsize in [('symtab',syms,2,3,1,8,24),('strtab',st,3,0,0,1,0),('shstrtab',shstr,3,0,0,1,0)]:
 while len(data)%align:data.append(0)
 at=len(data);data+=blob;sections.append((shstr.index(('.'+n).encode()),t,0,0,at,len(blob),l,i,align,entsize))
while len(data)%8:data.append(0)
shoff=len(data)
for s in sections:data+=struct.pack('<IIQQQQIIQQ',*s)
struct.pack_into('<16sHHIQQQIHHHHHH',data,0,b'\x7fELF\x02\x01\x01'+bytes(9),2,183,1,entry,64,shoff,0,64,56,1,64,len(sections),4)
struct.pack_into('<IIQQQQQQ',data,64,1,5,off,start,start,end-start,end-start,4)
(O/'native_text404.elf').write_bytes(data)
(O/'native_text404_map.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(b).hexdigest(),focused_sha256=hashlib.sha256(data).hexdigest(),source_start=hex(start),end_exclusive=hex(end),entry=hex(entry),symbol_names_are_analyst_assigned=True),indent=2)+'\n')
