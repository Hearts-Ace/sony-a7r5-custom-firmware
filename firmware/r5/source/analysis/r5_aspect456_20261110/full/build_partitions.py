#!/usr/bin/env python3
"""Build local 4.58 partitions from reproduced 4.55 and SHA-bound crop components.
Never opens a device or modifies a source partition. Output must be new.
"""
from pathlib import Path
import argparse, hashlib, json, os, shutil, struct, subprocess, sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path[:0]=[str(HERE/'vendor'),str(ROOT/'projects/firmware/development/shutter-sound-recovery455/src/lib')]
from a7r5dat.fat import FatImage
from partition_support import patch_partition, verify_lut_layout

EXPECTED={
 'AP':'e403e98212fc20056e0f876f7b8312cf48f9bfe5122b9954cb4e3e45e0d61937',
 'CP':'c44989e5990f375b4658f18e082f5e2773a6011e693f976b1ac09d452141975a',
 'AVCAM':'c83007a07a4058e63e9e984210642f18c74fbd555dcf8379001b0493b899af6b',
 'MPR':'81a97ba5ac2456077485fefa5eeaea441ae595f46e5edf8d3d8b7b7559ec1478'}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def identity(p):return dict(bytes=p.stat().st_size,sha256=sha(p))

def fat_replace(source,target,name,content):
 raw=source.read_bytes();fs=FatImage(raw);data=bytearray(raw)
 entry=fs.entries[name.casefold()];allocated=sum(n for _,n in entry['extents'])
 assert not entry['is_directory'] and entry['size']<=len(content)<=allocated
 used=[];position=0
 for at,size in entry['extents']:
  take=min(size,len(content)-position)
  if take<=0:break
  data[at:at+take]=content[position:position+take];used.append((at,take));position+=take
 assert position==len(content)
 size_at=entry['directory_entry_offset']+28;struct.pack_into('<I',data,size_at,len(content))
 final=FatImage(data);assert final.read(name)==content
 assert final.entries[name.casefold()]['extents']==entry['extents']
 reverse=bytearray(data)
 for at,size in used:reverse[at:at+size]=raw[at:at+size]
 reverse[size_at:size_at+4]=raw[size_at:size_at+4]
 assert reverse==raw
 assert final.entries.keys()==fs.entries.keys()
 for key in fs.entries:
  if key!=name.casefold():
   assert final.entries[key]==fs.entries[key]
   if not fs.entries[key]['is_directory']:assert final.read(key)==fs.read(key)
 target.write_bytes(data)
 return dict(passed=True,allocation_chain_unchanged=True,reverse_unchanged_outside_target=True,
  old_file_bytes=entry['size'],new_file_bytes=len(content),allocated_bytes=allocated,path=name,
  source_sha256=sha(source),**identity(target))

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
 p.add_argument('--e2fsck',type=Path,default=Path('/opt/homebrew/opt/e2fsprogs/sbin/e2fsck'))
 for n in ('ap','cp','avcam','mpr','resources'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--inputs',type=Path,default=ROOT/'projects/firmware/inputs.local.json')
 a=p.parse_args();assert __debug__ and not a.output.exists()
 base_expected=json.loads((ROOT/'projects/firmware/development/shutter-sound-recovery455/expected_outputs.json').read_text())
 baseline=a.base/'patched'
 for key,name in [('AP','appFw.so'),('CP','cpapp-b.bin'),('nflasha5','nflasha5'),('nflasha8','nflasha8'),('nflasha15','nflasha15')]:
  assert sha(baseline/name)==base_expected[key],('Wrong reproduced455',name)
 paths={key:getattr(a,key.lower())for key in EXPECTED}
 for key,path in paths.items():assert sha(path)==EXPECTED[key],('Wrong final component',key)
 resources=json.loads((a.resources/'manifest.json').read_text());assert resources['passed'] and resources['file_count']==70
 assert resources['text_runtime_ids']==[hex(v)for v in range(0x0200ab4c,0x0200ab50)]
 a.output.mkdir(parents=True);parts=a.output/'partitions';parts.mkdir();evidence=a.output/'evidence';evidence.mkdir()
 config={k:Path(v)for k,v in json.loads(a.inputs.read_text()).items()}
 from a7r5dat.ext2_patch import reader
 before=(baseline/'nflasha15').read_bytes();fs=reader(before)
 replacements={name:(fs.read_inode(fs.walk(name)),paths[key].read_bytes())for name,key in
  [('/lib/appFw.so','AP'),('/lib/libmpr.so','MPR')]}
 for row in resources['files']:
  q=a.resources/row['name'];assert sha(q)==row['output_sha256']
  name='/share/app/'+row['name'];raw=fs.read_inode(fs.walk(name))
  assert hashlib.sha256(raw).hexdigest()==row['input_sha256']
  replacements[name]=(raw,q.read_bytes())
 after,n15=patch_partition(before,replacements);(parts/'nflasha15').write_bytes(after)
 n15.update(layout=verify_lut_layout(after,True),against='Exact reproduced 4.55 nflasha15')
 save(evidence/'nflasha15.json',n15)
 check=subprocess.run([str(a.e2fsck),'-fn',str(parts/'nflasha15')],capture_output=True,text=True)
 (evidence/'nflasha15.e2fsck.log').write_text(check.stdout+check.stderr);assert check.returncode==0
 n15['e2fsck_readonly_passed']=True;save(evidence/'nflasha15.json',n15)
 archive_parts=config['stock_nflasha8'].parent
 save(evidence/'nflasha3.json',fat_replace(archive_parts/'nflasha3',parts/'nflasha3','/av-cam.bin',paths['AVCAM'].read_bytes()))
 save(evidence/'nflasha8.json',fat_replace(baseline/'nflasha8',parts/'nflasha8','/cpapp-b.bin',paths['CP'].read_bytes()))
 shutil.copyfile(baseline/'nflasha5',parts/'nflasha5');assert sha(parts/'nflasha5')==base_expected['nflasha5']
 report=dict(passed=True,state='PARTITIONS_BUILT_DEVICE_UNTESTED',version='4.58',camera_io=False,
  baseline_version='4.55',baseline_outputs=base_expected,components={key:identity(path)for key,path in paths.items()},
  resource_manifest_sha256=sha(a.resources/'manifest.json'),resources=70,
  partitions={q.name:identity(q)for q in parts.iterdir()},
  RAW='Full Bayer, DefaultCrop and SonyCrop preserved; shared embedded JPEG previews crop with JPEG/HEIF and their private size declarations are synchronized.',
  ratios=['809/500','239/100','5/4','37/20'],menu_order=[0,4,1,6,2,7,5,3],
  limitation='Offline partition integration; actual camera encoding, rendering and startup untested.')
 save(a.output/'build.json',report);print(json.dumps(dict(passed=True,partitions=report['partitions'])))
if __name__=='__main__':main()
