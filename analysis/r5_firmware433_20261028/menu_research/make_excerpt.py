"""Source-bound ELF excerpt for bounded REA; never an installable component."""
from read_menu import *
def elf64_excerpt(code,va):
 names=b'\0.text\0.shstrtab\0';at=0x100;name_at=at+len(code);s_at=(name_at+len(names)+7)&~7;b=bytearray(s_at+3*64)
 b[:64]=struct.pack('<16sHHIQQQIHHHHHH',b'\x7fELF\x02\x01\x01'+bytes(9),2,183,1,va,64,s_at,0,64,56,1,64,3,2)
 b[64:120]=struct.pack('<II6Q',1,5,at,va,va,len(code),len(code),1);b[at:at+len(code)]=code;b[name_at:name_at+len(names)]=names
 b[s_at+64:s_at+128]=struct.pack('<II4QII2Q',1,1,6,va,at,len(code),0,0,4,0);b[s_at+128:s_at+192]=struct.pack('<II4QII2Q',7,3,0,0,name_at,len(names),0,0,1,0);return bytes(b)
im=Image(ROOT/'build_r5_m4strict_4.04_20261015/patched/appFw.so');a=0x1c91a44;n=0x504;raw=im.read(a,n)
p=OUT/'menu_registration_excerpt.elf';p.write_bytes(elf64_excerpt(raw,a))
(OUT/'excerpt_identity.json').write_text(json.dumps(dict(source=str(im.path.relative_to(ROOT)),source_sha256=hashlib.sha256(im.data).hexdigest(),va=hex(a),bytes=n,file_offset=hex(im.offset(a)),raw_sha256=hashlib.sha256(raw).hexdigest(),excerpt_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),installable=False,camera_io=False),indent=2)+'\n')
