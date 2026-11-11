#!/usr/bin/env python3
"""Build and fully verify a local 4.59 test DAT; no deployment or publishing."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, sys, tarfile

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
LIB=ROOT/'projects/firmware/development/shutter-sound-recovery455/src/lib'
sys.path[:0]=[str(LIB),str(ROOT/'vendor/audit-python')]
from image_io import digest_file,digest_stream,update_sum
from overlay import Overlay
import package

def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('base','build','output'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--inputs',type=Path,default=ROOT/'projects/firmware/inputs.local.json')
 a=p.parse_args();assert __debug__ and not a.output.exists()
 report=json.loads((a.build/'build.json').read_text());assert report['passed'] and report['version']=='4.59'
 for name,row in report['partitions'].items():assert digest_file(a.build/'partitions'/name)==row['sha256']
 config={k:Path(v).resolve()for k,v in json.loads(a.inputs.read_text()).items()}
 a.output.mkdir(parents=True);work=a.output/'work';inputs=work/'inputs';inputs.mkdir(parents=True)
 evidence=a.output/'evidence';evidence.mkdir()
 for key,name in {'original_dat':'original.DAT','original_fdat':'original.fdat','updater':'updater.img',
  'public_key':'public.pem','sony_public_key':'sony_public.pem','private_key':'private.pem'}.items():
  (inputs/name).symlink_to(config[key])
 baseline=json.loads((a.base/'evidence/archive_verification_455.json').read_text())
 replacements={}
 for name in baseline['changed_members']:
  if name.startswith('011'):
   q=a.base/'patched/templates'/name;assert q.is_file(),name;replacements[name]=q
 for name in report['partitions']:replacements['0700_part_image/dev/'+name]=a.build/'partitions'/name
 original=config['original_tar']
 with tarfile.open(original,'r:')as t:
  members=t.getmembers();by={m.name:m for m in members};assert len(by)==len(members)
  name='0701_part_image_sum/part_image.sum'
  mapping={'dev/'+name:a.build/'partitions'/name for name in report['partitions']}
  text,changes=update_sum(t.extractfile(name).read().decode('ascii'),mapping,{k:v.stat().st_size for k,v in mapping.items()})
  assert len(changes)==4
  sums=a.output/'part_image.sum';sums.write_text(text);replacements[name]=sums
 ranges=[]
 for name,path in sorted(replacements.items(),key=lambda item:by[item[0]].offset_data):
  m=by[name];assert path.stat().st_size==m.size;ranges.append((m.offset_data,m.offset_data+m.size,path))
 overlay=Overlay(original,ranges)
 with overlay.open('rb')as f:archive_sha=digest_stream(f)
 facts=[];baseline_by={row['member']:row['sha256']for row in baseline['members']}
 with tarfile.open(original,'r:')as stock,overlay.open('rb')as f,tarfile.open(fileobj=f,mode='r:')as result:
  assert [m.get_info()for m in stock.getmembers()]==[m.get_info()for m in result.getmembers()]
  for m in members:
   if not m.isfile():continue
   before,after=digest_stream(stock.extractfile(m)),digest_stream(result.extractfile(m))
   assert after==(digest_file(replacements[m.name])if m.name in replacements else before)
   differs=after!=baseline_by[m.name]
   if differs:assert m.name in ['0700_part_image/dev/'+n for n in ('nflasha3','nflasha8','nflasha15')]+['0701_part_image_sum/part_image.sum']
   facts.append(dict(member=m.name,sha256=after,changed_from_stock=before!=after,changed_from_455=differs))
 archive=dict(passed=True,output_sha256=archive_sha,changed_members=list(replacements),members=facts,
  original_headers_padding_trailer_preserved=True,only_four_archive_members_differ_from_455=True)
 save(evidence/'archive_verification_459.json',archive)
 package.ROOT=work;package.OUT=a.output;package.TAR=overlay;package.VERSION='4.59';package.TAG='459';package.NAME='NONINSTALLABLE.DAT'
 package.components=lambda:dict(upstream_commit='086df3b1e33dfa0206553ac2bb003535c58ddb80',components=report['components'])
 old_digest=package.digest_file;package.digest_file=lambda path:archive_sha if path is overlay else old_digest(path)
 package.build_package()
 receipt=json.loads((a.output/'verification.json').read_text())
 receipt.update(state='OFFLINE_VERIFIED_LOCAL_TEST_PACKAGE_CAMERA_UNTESTED',
  exact_four_member_scope_verified=False,scope_against_455=['nflasha3','nflasha8','nflasha15','part_image.sum'],
  factory_defaults_and_backup_sum_unchanged_from_455=True,only_four_archive_members_differ_from_455=True,
  ratios=report['ratios'],RAW=report['RAW'],scope='Crop menus, preview masks, shared JPEG/HEIF and RAW embedded previews, metadata/playback; filter presentation using the original aspect Fn style with left abbreviations and selected full name, filter/sound transactions retained; abandoned page/renderer, E9 observers and reload branch removed; explicit non-Off filter switching sets native Creative Look to PT before the existing E4 request.',
  limitations=[
   'Camera installation, startup, physical LCD, actual JPEG/HEIF encoding and real ARW files remain untested for4.59.',
   'Instruction replays explicitly model OS, memory/files, display, transport and hardware encoder endpoints; they do not establish real pixel output.',
   'Full Bayer and native DefaultCrop/SonyCrop are preserved by the patch scope; shared embedded preview size declarations and playback recognition are updated.',
   'The original conditional CP NOR updater is retained; no physical NOR readback or camera operation was performed in this task.',
   'Existing4.55 sound/session behavior and updater trust are inherited; no additional physical acceptance is implied.'
  ],
  device_acceptance_tested=False,source_freeze_and_rebuild_pending=True)
 save(a.output/'verification.json',receipt)
 print(json.dumps(dict(passed=True,DAT_sha256=receipt['output_sha256'],archive=archive_sha)))
if __name__=='__main__':main()
