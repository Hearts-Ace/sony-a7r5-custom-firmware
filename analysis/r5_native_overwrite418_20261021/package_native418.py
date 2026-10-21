"""Offline new418 packaging with a read-only TAR overlay to conserve disk.
Never opens a camera or modifies original/reference files. Packaging is gated
on final source-bound component replays. Every byte is re-decrypted afterward.
"""
from pathlib import Path
import argparse,hashlib,io,json,os,shutil,struct,sys,tarfile,types
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from build_corrected_fl2_fl3 import geometry,digest_file,digest_stream
from rebuild_tar import update_sum
OUT=ROOT/'research/r5_custom_lut/build_r5_4.18_native12_20261021'
BASE=ROOT/'build_r5_m4strict_4.04_20261015'
sha=lambda b:hashlib.sha256(b).hexdigest()
def save(p,q):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(q,indent=2,ensure_ascii=False)+'\n')
class OverlayStream(io.RawIOBase):
 def __init__(self,source,rows):self.f=source.open('rb');self.rows=rows;self.position=0;self.length=source.stat().st_size
 def readable(self):return True
 def seekable(self):return True
 def tell(self):return self.position
 def seek(self,n,whence=0):
  self.position=n if whence==0 else self.position+n if whence==1 else self.length+n
  if self.position<0:raise ValueError('Negative offset')
  return self.position
 def read(self,n=-1):
  n=max(0,self.length-self.position)if n<0 else min(n,max(0,self.length-self.position));start=self.position;self.f.seek(start);result=bytearray(self.f.read(n));end=start+len(result)
  for lo,hi,path in self.rows:
   if lo<end and hi>start:
    a,b=max(start,lo),min(end,hi)
    with path.open('rb')as f:f.seek(a-lo);replacement=f.read(b-a)
    assert len(replacement)==b-a;result[a-start:b-start]=replacement
  self.position=end;return bytes(result)
 def close(self):self.f.close();super().close()
class Overlay:
 def __init__(self,source,rows):self.source,self.rows=source,rows
 def open(self,mode):assert mode=='rb';return OverlayStream(self.source,self.rows)
 def stat(self):return self.source.stat()
def cp_partition():
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'patched').mkdir(exist_ok=True);(OUT/'evidence').mkdir(exist_ok=True)
 source=BASE/'patched/nflasha8';old,offsets,unit,meta=geometry(source,'cpapp-b.bin');new=(HERE/'cp/cp418-native12.NONINSTALLABLE.bin').read_bytes();assert len(old)==len(new)
 dest=OUT/'patched/nflasha8';shutil.copyfile(source,dest)
 with dest.open('r+b')as f:
  for i,at in enumerate(offsets):chunk=new[i*unit:(i+1)*unit];f.seek(at);f.write(chunk)
  f.flush();os.fsync(f.fileno())
 actual,o,u,m=geometry(dest,'cpapp-b.bin');assert actual==new and(o,u,m)==(offsets,unit,meta)
 spans=sorted((at,at+min(unit,len(new)-i*unit))for i,at in enumerate(offsets))
 with source.open('rb')as x,dest.open('rb')as y:
  pos=0
  for a,b in spans:assert x.read(a-pos)==y.read(a-pos);x.seek(b);y.seek(b);pos=b
  assert x.read()==y.read()
 save(OUT/'evidence/cp_partition.json',dict(passed=True,CP_sha256=sha(new),partition_sha256=digest_file(dest),original_partition_sha256=digest_file(source),all_other_bytes_unchanged=True,full_component_readback=True))
def archive():
 source=BASE/'patched/firmware.tar'
 replacements={'0700_part_image/dev/nflasha8':OUT/'patched/nflasha8','0700_part_image/dev/nflasha15':HERE/'ap/nflasha15'}
 with tarfile.open(source,'r:')as t:
  members=t.getmembers();by={m.name:m for m in members};assert len(by)==len(members)
  name='0701_part_image_sum/part_image.sum';mapping={n.removeprefix('0700_part_image/'):p for n,p in replacements.items()}
  text,changes=update_sum(t.extractfile(name).read().decode('ascii'),mapping,{n:p.stat().st_size for n,p in mapping.items()})
  assert len(changes)==2;p=OUT/'patched/part_image.sum';p.write_text(text);replacements[name]=p
 rows=[]
 for n,p in sorted(replacements.items(),key=lambda kv:by[kv[0]].offset_data):
  m=by[n];assert p.stat().st_size==m.size;rows.append((m.offset_data,m.offset_data+m.size,p))
 overlay=Overlay(source,rows);h=digest_stream(overlay.open('rb'));facts=[]
 with source.open('rb')as a,overlay.open('rb')as b:
  pos=0
  for lo,hi,path in rows:
   left=lo-pos
   while left:n=min(4<<20,left);assert a.read(n)==b.read(n);left-=n
   with path.open('rb')as p:
    left=hi-lo
    while left:n=min(4<<20,left);assert b.read(n)==p.read(n);left-=n
   a.seek(hi);pos=hi
  while True:
   x=a.read(4<<20);y=b.read(len(x));assert x==y
   if not x:break
 with tarfile.open(source,'r:')as a,overlay.open('rb')as f,tarfile.open(fileobj=f,mode='r:')as b:
  assert [m.get_info()for m in a.getmembers()]==[m.get_info()for m in b.getmembers()]
  for m in members:
   if not m.isfile():continue
   before,after=digest_stream(a.extractfile(m)),digest_stream(b.extractfile(m));assert after==(digest_file(replacements[m.name])if m.name in replacements else before)
   assert (before!=after)==(m.name in replacements);facts.append(dict(name=m.name,sha256=after,baseline_sha256=before,changed=before!=after))
 q=dict(passed=True,source_sha256=digest_file(source),output_sha256=h,bytes=source.stat().st_size,changed_members=list(replacements),members=facts,crc_updates=changes,virtual_archive=True,all_other_bytes_headers_padding_trailer_unchanged=True,overlay_source=str(source.relative_to(ROOT)),overlay_ranges=[dict(start=lo,end=hi,path=str(p.relative_to(ROOT)),sha256=digest_file(p))for lo,hi,p in rows])
 save(OUT/'evidence/archive_verification_418.json',q);return overlay

def gates():
 cp=json.loads((HERE/'cp/build.json').read_text());csha=cp['candidate_sha256'];asha=digest_file(HERE/'ap/appFw.so')
 for p,expected in [(HERE/'cp/loader_replay.json',csha),(HERE/'import/native_transfer_replay.json',csha),(HERE/'cp/native_color_replay.json',csha),(HERE/'cp/native53_replay.json',csha),(HERE/'import/native_probe_replay.json',csha),(HERE/'gamma/final_replay.json',csha)]:
  q=json.loads(p.read_text());assert q.get('passed',False),(p,'not passed');assert q.get('CP_sha256',q.get('candidate_sha256'))==expected,(p,'unbound')
 for p in [HERE/'import/native_worker_replay.json',HERE/'import/ap_loader_replay.json',HERE/'names/integrated_replay.json']:
  q=json.loads(p.read_text());assert q.get('passed',True);assert asha in p.read_text(),(p,'AP hash unbound')
 v=json.loads((BASE/'verification.json').read_text());components={n:dict(row,path=str((BASE/'patched'/n).relative_to(ROOT)))for n,row in v['components'].items()}
 components['appFw.so']=dict(path=str((HERE/'ap/appFw.so').relative_to(ROOT)),sha256=asha)
 components['cpapp-b.bin']=dict(path=str((HERE/'cp/cp418-native12.NONINSTALLABLE.bin').relative_to(ROOT)),sha256=csha)
 for row in components.values():assert digest_file(ROOT/row['path'])==row['sha256']
 return dict(upstream_commit='086df3b1e33dfa0206553ac2bb003535c58ddb80',components=components)
def package():
 gates();v=archive();source=ROOT/'research/r5_custom_lut/build_r5_4.16_bcd_fixed_20261021/source/pack_bcd.py';pack=types.ModuleType('native418_package');pack.__file__=str(ROOT/'tools/build_r5_m4strict403.py');exec(compile(source.read_text(),str(source),'exec'),pack.__dict__)
 original_digest=pack.digest_file;pack.digest_file=lambda p:digest_stream(v.open('rb'))if p is v else original_digest(p)
 pack.OUT=OUT;pack.TAR=v;pack.TAG='418';pack.VERSION='4.18';pack.components=gates;pack.build_package()
 q=json.loads((OUT/'verification.json').read_text());q.pop('exact_four_member_scope_verified',None)
 q.update(base_firmware='4.04 native baseline plus new12 ordinal SD parameter/name overwrite',version_encoding='BCD',encoded_version_hex='1804',virtual_archive=True,no_old_slot_selection_tokens=True,no_Q_identity_table=True,extra_compensation_matrix_included=False,compensation_grid_included=False,native12_order=['ST','PT','NT','VV','VV2','FL','FL2','FL3','IN','SH','BW','SE'],SD_file='R5NATIVE.BIN',device_acceptance_tested=False)
 save(OUT/'verification.json',q)
 assert(OUT/'FDAT.header.4.18.bin').read_bytes()[32:34]==bytes.fromhex('1804')
 print(json.dumps(dict(DAT=str(OUT/'BODYDATA.DAT'),SHA256=q['output_sha256'])))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--stage',choices=['images','package'],required=True);args=a.parse_args();cp_partition()if args.stage=='images'else package()
