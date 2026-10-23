"""Offline R5 4.23 packaging. Requires source-bound final menu/AP/CP receipts.
No camera, SD card or block-device access. Protected source evidence is read-only.
"""
from pathlib import Path
import argparse,hashlib,io,json,os,shutil,struct,sys,tarfile,types
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'vendor/fwtool.py-a7iv'),str(ROOT/'tools')]
from build_corrected_fl2_fl3 import geometry,digest_file,digest_stream
from rebuild_tar import update_sum
OUT=ROOT/'research/r5_custom_lut/build_r5_4.23_custom_filter_20261023'
BASE=ROOT/'build_r5_m4strict_4.04_20261015'
AP_SOURCE=HERE
sha=lambda b:hashlib.sha256(b).hexdigest()
def save(p,q):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(q,indent=2,ensure_ascii=False)+'\n')
def original_header_identity():
 """Bind inherited FDAT header bytes to independently decrypted original DAT."""
 from Cryptodome.Cipher import AES
 from fwtool.sony import constants
 from sign_r5_firmware import inspect
 source=ROOT/'BODYDATA.DAT'
 expected='51e1176a255a9a4b4782dfbcfa6c5f332b71173bdfe9ed2bcf4fca6bcbc6c2e2'
 assert digest_file(source)==expected
 layout=inspect(source)
 with source.open('rb')as f:
  f.seek(layout['signature_offset']-16);iv=f.read(16)
  f.seek(layout['signed_offset']);block=f.read(1024)
 decoded=AES.new(constants.key_aes,AES.MODE_ECB).decrypt(block[:512])+AES.new(constants.key_cxd90057_k8,AES.MODE_CBC,iv).decrypt(block[512:])
 native=decoded[4:516]
 with (ROOT/'unpacked/r5/firmware.fdat').open('rb')as f:assert f.read(512)==native
 return dict(passed=True,original_DAT_sha256=expected,original_header_sha256=sha(native),
  original_header_bytes=512,independently_decrypted_original_header_exact=True)
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
 assert not(OUT/'BODYDATA.DAT').exists(),'Refuse changing an already packaged release'
 source=BASE/'patched/nflasha8';old,offsets,unit,meta=geometry(source,'cpapp-b.bin');new=(HERE/'cp/cp423.NONINSTALLABLE.bin').read_bytes();assert len(old)==len(new)
 assert sha(old)=='8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32'
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
 replacements={'0700_part_image/dev/nflasha8':OUT/'patched/nflasha8','0700_part_image/dev/nflasha15':AP_SOURCE/'ap/nflasha15'}
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
 save(OUT/'evidence/archive_verification_423.json',q);return overlay

def gates():
 """Frozen final acceptance manifest is produced only after menu integration."""
 path=HERE/'release_tests/final_gate.json';gate=json.loads(path.read_text())
 assert gate['passed'] and gate['version']=='4.23'
 assert gate['menu_native_registration_render_selection_back_replayed'] is True
 assert gate['mandatory_grid_and_native_gamma_tail_preserved'] is True
 assert gate['AP_sha256']==digest_file(HERE/'ap/appFw.so')
 assert gate['CP_sha256']==digest_file(HERE/'cp/cp423.NONINSTALLABLE.bin')
 for row in gate['inputs']:
  p=ROOT/row['path'];assert digest_file(p)==row['sha256'],row['path']
 for row in gate['receipts']:
  p=ROOT/row['path'];assert digest_file(p)==row['sha256'],row['path']
  assert json.loads(p.read_text())['passed'],row['path']
 build=json.loads((HERE/'ap/ap_build.json').read_text())
 assert build['AP_sha256']==gate['AP_sha256'] and build['native_readonly_e2fsck_passed']
 assert build['partition_sha256']==digest_file(HERE/'ap/nflasha15')
 cp_image=json.loads((OUT/'evidence/cp_partition.json').read_text())
 assert cp_image['passed'] and cp_image['CP_sha256']==gate['CP_sha256']
 assert cp_image['partition_sha256']==digest_file(OUT/'patched/nflasha8')
 assert cp_image['original_partition_sha256']==digest_file(BASE/'patched/nflasha8')
 assert cp_image['full_component_readback'] and cp_image['all_other_bytes_unchanged']
 header=original_header_identity()
 v=json.loads((BASE/'verification.json').read_text())
 assert v['version']=='4.04' and v['source_commit']=='086df3b1e33dfa0206553ac2bb003535c58ddb80'
 assert digest_file(BASE/'patched/firmware.tar')==v['archive_sha256']
 components={n:dict(row,path=str((BASE/'patched'/n).relative_to(ROOT)))for n,row in v['components'].items()}
 for n,p in [('appFw.so',HERE/'ap/appFw.so'),('cpapp-b.bin',HERE/'cp/cp423.NONINSTALLABLE.bin')]:
  components[n]=dict(path=str(p.relative_to(ROOT)),sha256=digest_file(p))
 for row in components.values():assert digest_file(ROOT/row['path'])==row['sha256']
 return dict(upstream_commit=v['source_commit'],components=components,
  passed=True,camera_io=False,AP_sha256=gate['AP_sha256'],CP_sha256=gate['CP_sha256'],original_header=header)

def source_manifest():
 paths=[p for p in HERE.rglob('*')if p.is_file() and p.suffix in ('.py','.c','.h','.S') and '__pycache__'not in p.parts]
 paths += [ROOT/p for p in ['research/r5_custom_lut/build_r5_4.16_bcd_fixed_20261021/source/pack_bcd.py',
  'tools/build_corrected_fl2_fl3.py','tools/rebuild_tar.py','tools/sign_r5_firmware.py','tools/fdat_encrypt.py',
  'vendor/fwtool.py-a7iv/fwtool/sony/constants.py','vendor/fwtool.py-a7iv/fwtool/sony/fdat.py','vendor/fwtool.py-a7iv/fwtool/sony/dat.py',
  'research/r5_custom_lut/scripts/custom_filter_config423.py']]
 gate=json.loads((HERE/'release_tests/final_gate.json').read_text())
 paths += [ROOT/row['path']for row in gate['inputs']+gate['receipts']]
 paths.append(HERE/'release_tests/final_gate.json')
 rows=[dict(path=str(p.relative_to(ROOT)),sha256=digest_file(p))for p in sorted(set(paths))]
 q=dict(schema='r5-423-source-manifest/1',rows=rows,camera_io=False)
 save(OUT/'evidence/source_manifest.json',q);return q

def package():
 gates();manifest=source_manifest();overlay=archive()
 source=ROOT/'research/r5_custom_lut/build_r5_4.16_bcd_fixed_20261021/source/pack_bcd.py'
 pack=types.ModuleType('r5_custom423_package');pack.__file__=str(ROOT/'tools/build_r5_m4strict403.py')
 exec(compile(source.read_text(),str(source),'exec'),pack.__dict__)
 original_digest=pack.digest_file
 pack.digest_file=lambda p:digest_stream(overlay.open('rb'))if p is overlay else original_digest(p)
 pack.OUT=OUT;pack.TAR=overlay;pack.TAG='423';pack.VERSION='4.23';pack.components=gates
 pack.build_package()
 assert (OUT/'FDAT.header.4.23.bin').read_bytes()[32:34]==bytes.fromhex('2304')
 assert (OUT/'BODYDATA.DAT').stat().st_size==754525608 and not (OUT/'BODYDATA.DAT').is_symlink()
 for row in manifest['rows']:assert digest_file(ROOT/row['path'])==row['sha256'],row['path']
 gates()
 q=json.loads((OUT/'verification.json').read_text());q.pop('exact_four_member_scope_verified',None)
 q.update(firmware_release='4.23',config_version=4,config_schema='r5-custom-filter-config/4',
  base_firmware='strict4.04 native baseline',custom_filter_menu='自定义滤镜',
  creative_look_and_custom_selection_independent=True,grid_mandatory=True,
  grid_switch_present=False,legacy_BIN_accepted=False,selection_saved_immediately=True,
  native_Gamma_tail_preserved_for_actual_Creative_Look=True,
  SD_import_policy='full replacement; missing selected configuration disables custom filter',
  SD_file='R5NATIVE.BIN',selection_file='/usr/data/lut/R5FILTER.BIN',
  camera_io_performed=False,device_acceptance_tested=False,experimental_candidate=True,
  source_manifest_sha256=digest_file(OUT/'evidence/source_manifest.json'),
  limitations=['Offline native instruction/UI controller replays and complete package verification do not demonstrate camera boot, LCD appearance or final JPG pixels.',
  'Original Creative Look private processing and native Gamma tails are retained. Selected base can still affect image processing outside the custom fields.',
  'CP immutable allocations retain up to16 banks; real camera heap/cache/stack capacity is unverified.',
  'AP names retain up to16 immutable snapshots, including name-only updates. On exhaustion new UI names are unavailable; Off remains usable and existing CP data is not rolled back.',
  'One immutable selection view is used within each stage; whole-frame atomic switching across all separate native stages has not been demonstrated.',
  'Runtime native grid restoration snapshots preserve original builders; source-producer stability and physical cache coherency need device acceptance.',
  'No camera, SD card or block device was accessed.'])
 save(OUT/'verification.json',q)
 shutil.copyfile(HERE/'release_tests/final_gate.json',OUT/'evidence/final_gate.json')
 sums=[]
 for p in sorted(OUT.rglob('*')):
  if p.is_file()and p.name!='SHA256SUMS':sums.append(digest_file(p)+'  '+str(p.relative_to(OUT)))
 (OUT/'SHA256SUMS').write_text('\n'.join(sums)+'\n')

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['images','package'],required=True)
 args=parser.parse_args();cp_partition()if args.stage=='images'else package()
