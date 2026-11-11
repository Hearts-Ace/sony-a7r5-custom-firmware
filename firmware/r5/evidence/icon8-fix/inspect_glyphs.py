from pathlib import Path
import sys,struct,json,zlib
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'projects/firmware/development/aspect457-fn-style/source/analysis/r5_aspect456_20261110/resources'))
import build_resources as b,reference_style as r
import numpy as np
H=Path(__file__).resolve().parent

def png(path,items,columns=6,zoom=4):
 w=columns*80*zoom;h=((len(items)+columns-1)//columns)*65*zoom
 canvas=bytearray([50]*(w*h*3))
 for n,raw in enumerate(items):
  a=np.frombuffer(raw,dtype='<u2').reshape(-1,80)
  for y in range(a.shape[0]):
   for x in range(70):
    q=int(a[y,x]);al=q&15;rgb=bytes((((q>>sh)&15)*17*al+50*(15-al)+7)//15 for sh in (12,8,4))
    for dy in range(zoom):
     at=3*(((n//columns)*65*zoom+y*zoom+dy)*w+(n%columns)*80*zoom+x*zoom);canvas[at:at+3*zoom]=rgb*zoom
 def chunk(k,d):return struct.pack('>I',len(d))+k+d+struct.pack('>I',zlib.crc32(k+d))
 path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(b'\0'+canvas[y*w*3:(y+1)*w*3]for y in range(h)),9))+chunk(b'IEND',b''))

def main():
 for v in ('23','32'):
  rows=b.image_records((ROOT/('unpacked/r5/usr_complete/share/app/image_00_'+v+'_IPSX.uxc')).read_bytes())[3]
  g=np.array([[r.FN_PALETTE[c]for c in line]for line in r.FN_STYLES[v]['glyphs']['6'][False]],dtype=np.uint16)
  found=[];raws=[]
  for rid,row in rows.items():
   if row['descriptor_size']!=20 or struct.unpack_from('<HH',row['descriptor'],8)!=(70,60):continue
   raw,_=b.inflate(row['payload'],9600);a=np.frombuffer(raw,dtype='<u2').reshape(60,80)
   win=np.lib.stride_tricks.sliding_window_view(a,g.shape)
   at=np.argwhere(np.all(win==g,axis=(-1,-2)))
   if len(at):found.append(dict(id=hex(rid),positions=at.tolist()));raws.append(raw)
  (H/('matching6-'+v+'.json')).write_text(json.dumps(found));print(v,found)
  png(H/('matching6-'+v+'.png'),raws)
if __name__=='__main__':main()
