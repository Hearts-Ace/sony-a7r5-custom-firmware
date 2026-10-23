from read_menu import *
def adrp_refs(im,targets):
 pages={t&~4095 for t in targets};result={t:[] for t in targets}
 s=im.sections['.text'];start,size=s[3],s[5];raw=im.read(start,size);words=memoryview(raw).cast('I')
 for k,w in enumerate(words):
  if w&0x9f000000!=0x90000000:continue
  va=start+k*4;imm=((w>>5)&0x7ffff)<<2 | ((w>>29)&3)
  if imm&0x100000:imm-=0x200000
  page=(va&~4095)+(imm<<12)
  if page not in pages:continue
  rd=w&31
  for j in range(1,5):
   if k+j>=len(words):break
   a=words[k+j]
   if a&0xffc00000==0x91000000 and (a>>5)&31==rd:
    target=page+((a>>10)&4095)
    if target in result:result[target].append((va,va+j*4))
 return result
if __name__=='__main__':
 import sys
 im=Image(ROOT/'build_r5_m4strict_4.04_20261015/patched/appFw.so')
 for t,x in adrp_refs(im,[int(s,0) for s in sys.argv[1:]]).items():
  print(hex(t),[(hex(a),hex(b))for a,b in x])
