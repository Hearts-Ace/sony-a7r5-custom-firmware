from pathlib import Path
import struct,sys,json,hashlib
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'analysis/r5_custom_filter423_20261023/menu_research')]
from read_menu import Image
AP=ROOT/'analysis/r5_firmware434_20261028/ap/appFw.so'
def xrefs(im,targets):
 text=im.sections['.text']; va=text[3]; data=im.data[text[4]:text[4]+text[5]]; pages={t&~4095 for t in targets}; out={t:[] for t in targets}
 for off in range(0,len(data),4):
  ins=struct.unpack_from('<I',data,off)[0]
  if ins&0x9f000000!=0x90000000:continue
  imm=((ins>>29)&3)|(((ins>>5)&0x7ffff)<<2)
  if imm&(1<<20):imm-=1<<21
  pc=va+off; page=(pc&~4095)+(imm<<12)
  if page not in pages:continue
  reg=ins&31
  for step in range(1,8):
   i=struct.unpack_from('<I',data,off+4*step)[0]
   if i&0xffc003e0==0x91000000|(reg<<5):
    dest=page+((i>>10)&4095)
    if dest in targets:out[dest].append([pc,pc+4*step])
   if i&0xffc003e0==0xf9400000|(reg<<5):
    dest=page+(((i>>10)&4095)<<3)
    if dest in targets:out[dest].append([pc,pc+4*step])
 return out
if __name__=='__main__':
 im=Image(AP)
 targets=[int(x,0) for x in sys.argv[1:]]
 if not targets:targets=[0x37485D0,0x374B518,0x3E114D0,0x3E19EA8,0x3E1A538,0x4265490,0x4268CD8,0x4269D08,0x4287F20,0x4289370,0x42C9DC8,0x42CA428,0x4F8F0EF,0x4F8662E,0x4ED638E]
 result=xrefs(im,targets)
 for t,hits in result.items():
  print(hex(t),im.string(t),[[hex(n) for n in h] for h in hits])
  for p,q in hits:print(im.dis(p-24,q-p+60))
