#!/usr/bin/env python3
"""Offline single BIN -> M4 camera-look v2. All photo/live parameters copied identically."""
import argparse,copy,hashlib,importlib.util,json,struct,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CODEC=Path(__file__).with_name('custom_filter_v4.py')
spec=importlib.util.spec_from_file_location('r5codec',CODEC);codec=importlib.util.module_from_spec(spec);spec.loader.exec_module(codec)
FIELDS='defaults draft engine_abi format id mode model name parameters required_capabilities revision version'.split()
M4_GAMMA_CAP=130944

def digest(d):
 data=json.dumps({k:d[k] for k in FIELDS},sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf8')
 return hashlib.sha256(b'CAMLOOK2\0'+data).hexdigest()

def validate(d):
 if (d['format'],d['version'],d['model'],d['engine_abi'],d['mode'])!=('camera-look',2,'ILCE-7M4',131072,'photo'):raise ValueError('Unsupported M4 contract')
 if d['payload_sha256']!=digest(d):raise ValueError('M4 payload hash mismatch')
 if not 1<=len(d['name'].encode('utf8'))<=63:raise ValueError('Invalid name')
 if uuid.UUID(d['id']).int==0:raise ValueError('Invalid UUID')
 p=d['parameters'];g=p['grid']
 flat=lambda x:[v for a in x for b in a for c in b for v in c]
 for key in ['photo','live']:
  if len(flat(g[key]))!=1215 or any(type(v)is not int or not -64<=v<=63 for v in flat(g[key])):raise ValueError('Invalid grid')
  v=p[key]
  if len(v['coefficients']['values'])!=3 or any(len(a)!=8 or any(type(x)is not int or not -32768<=x<=32767 for x in a) for a in v['coefficients']['values']):raise ValueError('Invalid coefficients')
  if len(v['matrices']['values'])!=3 or any(len(a)!=16 or any(len(b)!=6 or any(type(x)is not int or not -8192<=x<=8191 for x in b) for b in a) for a in v['matrices']['values']):raise ValueError('Invalid matrices')
  records=v['gamma']['records']
  if len(records)!=(7 if key=='photo' else 1):raise ValueError('Invalid Gamma record count')
  for r in records:
   if len(r)!=572:raise ValueError('Invalid Gamma size')
   b=bytes(r);points=struct.unpack('<129I',b[:516])
   if points[0]!=0 or any(a>b for a,b in zip(points,points[1:])) or max(points)>M4_GAMMA_CAP:raise ValueError('Invalid M4 Gamma ordinates (must be <= 130944)')
   if struct.unpack_from('<I',b,544)[0]!=points[-1]:raise ValueError('Invalid duplicated Gamma endpoint at byte 544')
 if p['photo']['coefficients']!=p['live']['coefficients'] or p['photo']['matrices']!=p['live']['matrices'] or g['photo']!=g['live']:raise ValueError('Photo/live copy mismatch')
 if any(r!=p['photo']['gamma']['records'][0] for r in p['photo']['gamma']['records']+p['live']['gamma']['records']):raise ValueError('Eight Gamma records must be identical')
 return d

def convert(source,template):
 blob=source.read_bytes();cfg=codec.unpack(blob)
 if len(cfg['entries'])!=1:raise ValueError('Requires a single-filter BIN')
 e=cfg['entries'][0];d=copy.deepcopy(template)
 d.update(name=e['full_name'],author='Native parameter transfer',description='Identical photo/live parameter transfer; camera validation pending.',id=str(uuid.uuid5(uuid.NAMESPACE_URL,'sony-filter-transfer/ILCE-7M4/'+e['short_name'])),revision=1,draft=False)
 p=d['parameters'];record=bytearray(p['photo']['gamma']['records'][0])
 gamma=[min(value,M4_GAMMA_CAP) for value in e['gamma_native_129']]
 struct.pack_into('<129I',record,0,*gamma)
 struct.pack_into('<I',record,544,gamma[128])
 for branch,count in [('photo',7),('live',1)]:
  p[branch]['coefficients']['values']=copy.deepcopy(e['cc1_delta'])
  p[branch]['matrices']['values']=copy.deepcopy(e['block13'])
  p[branch]['gamma']['records']=[list(record) for _ in range(count)]
  p['grid'][branch]=copy.deepcopy(e['grid_5x9x9']['coefficients'])
 d['provenance']={'method':'native-integer-transfer-photo-live-identical','source_bin_sha256':hashlib.sha256(blob).hexdigest(),'short_name':e['short_name'],'camera_verified':False,'refitted':False,'gamma_policy':'129 source points clamped to <= 130944; byte offset 544 repeats final point; normalized complete 572-byte record copied to all seven photo and one live records'}
 d['payload_sha256']=digest(d);validate(d)
 return e,d

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('--template',type=Path,default=Path(__file__).with_name('m4-template.json'));p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 template=json.loads(a.template.read_text(encoding='utf-8-sig'))
 paths=sorted(a.input.rglob('*.bin')) if a.input.is_dir() else [a.input]
 a.output.mkdir(parents=True,exist_ok=False);manifest=[]
 for source in paths:
  e,d=convert(source,template);label=e['short_name']
  if '/' in label or '\\' in label or label in ['.','..']:raise ValueError('Unsafe name')
  dest=a.output/(source.relative_to(a.input).parent if a.input.is_dir() else Path())/(label+'.json');dest.parent.mkdir(parents=True,exist_ok=True)
  text=json.dumps(d,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n'
  if len(text.encode('utf8'))>131072:raise ValueError('M4 JSON exceeds 128KiB reader limit')
  with dest.open('x',encoding='utf8') as f:f.write(text)
  manifest.append({'file':str(dest.relative_to(a.output)),'short_name':label,'source_sha256':d['provenance']['source_bin_sha256'],'payload_sha256':d['payload_sha256'],'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
 (a.output/'manifest.json').write_text(json.dumps({'schema':'r5-m4-transfer/1','camera_verified':False,'filters':manifest},ensure_ascii=False,indent=2)+'\n')
 print('Converted',len(manifest),'filters to',a.output)
if __name__=='__main__':main()
