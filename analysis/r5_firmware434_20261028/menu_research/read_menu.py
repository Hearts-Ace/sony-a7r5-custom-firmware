"""Bounded original/4.04 AP menu data evidence; read-only inputs, no camera IO."""
from pathlib import Path
import hashlib, json, struct
from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
class Image:
 def __init__(self,path):
  self.path=path;self.data=path.read_bytes();b=self.data
  assert b[:6]==b'\x7fELF\x02\x01'
  phoff,shoff=struct.unpack_from('<QQ',b,32)
  phent,phnum,shent,shnum,shstr=struct.unpack_from('<HHHHH',b,54)
  self.loads=[]
  for n in range(phnum):
   p=struct.unpack_from('<IIQQQQQQ',b,phoff+n*phent)
   if p[0]==1:self.loads.append(p)
  sh=[struct.unpack_from('<IIQQQQIIQQ',b,shoff+n*shent) for n in range(shnum)]
  names=b[sh[shstr][4]:sh[shstr][4]+sh[shstr][5]];self.sections={}
  for s in sh:
   name=names[s[0]:].split(b'\0')[0].decode();self.sections[name]=s
  self.relocs={}
  for name,s in self.sections.items():
   if s[1]==4:
    for a,info,addend in struct.iter_unpack('<QQq',b[s[4]:s[4]+s[5]]):self.relocs[a]=(info,addend)
  self.md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
 def offset(self,va):
  for p in self.loads:
   if p[3]<=va<p[3]+p[5]:return p[2]+va-p[3]
  raise ValueError(hex(va))
 def read(self,va,size):return self.data[self.offset(va):self.offset(va)+size]
 def pointer(self,va):return self.relocs[va][1] if va in self.relocs else struct.unpack('<Q',self.read(va,8))[0]
 def string(self,va):return self.read(va,256).split(b'\0')[0].decode('utf8','replace')
 def dis(self,va,size):return '\n'.join(f'{i.address:08x}: {i.bytes.hex():8s} {i.mnemonic:7s} {i.op_str}'for i in self.md.disasm(self.read(va,size),va))
 def refs(self,target):return [a for a,v in self.relocs.items()if v[1]==target]
def main():
 im=Image(ROOT/'build_r5_m4strict_4.04_20261015/patched/appFw.so')
 strings=[]
 for p in sorted((ROOT/'unpacked/r5/usr_complete/share/app').glob('string_english*.uxc')):
  b=p.read_bytes()
  for term in [b'Creative Look',b'Picture Profile',b'Creative Style']:
   pos=0
   while True:
    pos=b.find(term,pos)
    if pos<0:break
    strings.append(dict(file=str(p.relative_to(ROOT)),offset=hex(pos),resource=hex((struct.unpack_from('<I',b,pos-4)[0]&0xffffff)|0x02000000),text=b[pos:].split(b'\0')[0].decode()));pos+=1
 root=im.pointer(0x594a7b0);groups=[]
 for category in range(7):
  for group in range(16):
   va=root+0x18+category*0x2e10+group*0x2e0
   gid,title,count=struct.unpack('<III',im.read(va,12))
   if not count or count>30:continue
   items=[]
   for n in range(count):
    item=va+0x10+n*24;mid=struct.unpack('<Q',im.read(item,8))[0];d1=im.pointer(item+8);d2=im.pointer(item+16)
    items.append(dict(index=n,va=hex(item),id=hex(mid),d1=hex(d1),d2=hex(d2),d1hex=im.read(d1,0xc0).hex()if d1 else None,d2hex=im.read(d2,0x90).hex()if d2 else None))
   groups.append(dict(category=category,group=group,va=hex(va),id=gid,title=hex(title),count=count,items=items))
 result=dict(source=str(im.path.relative_to(ROOT)),sha256=hashlib.sha256(im.data).hexdigest(),root=hex(root),creative_string_resources=strings,groups=groups,creative_descriptor_refs=[hex(x)for x in im.refs(0x5858b08)],creative_rows_refs=[hex(x)for x in im.refs(0x3f4a280)])
 (OUT/'menu_inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items()if k!='groups'},ensure_ascii=False,indent=2))
 for g in groups:
  for i in g['items']:
   if i['d1']=='0x5858b08' or i['d2']=='0x5858b08':print(json.dumps(g,indent=2))
if __name__=='__main__':main()
