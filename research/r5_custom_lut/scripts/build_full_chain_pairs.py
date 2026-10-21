# SPDX-License-Identifier: AGPL-3.0-or-later
# RAW target-chain research based on Raw Alchemy v0.6.2; see THIRD_PARTY_NOTICES.md.
"""Pair synthetic sensor codes, measured Edit frontend and full native JPEG.

Training uses only generated sensor colors, never photograph image pixels.
"""
from pathlib import Path
import argparse,hashlib,json,sys
import numpy as np
from PIL import Image
from raw_slog3_reference import RawSLog3Reference,Cube

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('capture',type=Path);ap.add_argument('chart',type=Path)
 ap.add_argument('--profile',type=Path,required=True);ap.add_argument('--sgamut3-lut',type=Path,required=True);ap.add_argument('--cine-lut',type=Path,required=True);ap.add_argument('--context',type=int,default=4);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(exist_ok=False)
 r=json.load(open(a.capture/'report.json'));chart=np.load(a.chart/'chart.npz')['rgb_codes'];groups={}
 for row in r['messages']:
  p=row['message'].get('payload',{});l=p.get('label','')
  if not l.startswith('synthetic-input-'+str(a.context)+'-'):continue
  data=(a.capture/row['data']['file']).read_bytes()
  if hashlib.sha256(data).hexdigest()!=row['data']['sha256']:raise ValueError('Capture modified')
  key=l.rsplit('-ch',1)[0];g=groups.setdefault(key,dict(points=p['points'],planes={}))
  g['planes'][p['ch']]=np.frombuffer(data,dtype='<u2').reshape(-1,9)
 samples={}
 for g in groups.values():
  rgb=np.stack([g['planes'][i] for i in range(3)],axis=-1)
  for pt,pixels in zip(g['points'],rgb):
   key=(pt['sy'],pt['sx'])
   if key in samples:raise ValueError('Duplicate sensor center')
   samples[key]=(pt,pixels)
 keys=sorted(samples);x=np.array([samples[k][1] for k in keys]);coords=np.array([[samples[k][0]['gx'],samples[k][0]['gy']] for k in keys])
 codes=np.array([chart[k] for k in keys]);itp=np.clip(np.trunc((codes.astype(float)-512)*np.array([2698,1056,1878])/2048),0,16383)
 delta=x[:,4].astype(float)-itp
 jpeg=np.asarray(Image.open(a.capture/'native-reference.jpg').convert('RGB'));j=jpeg[coords[:,1],coords[:,0]].astype(float)
 root=Path(__file__).resolve().parents[1];profile=a.profile;pr=json.load(open(profile))
 sensor=(codes.astype(float)-512)/15871
 # Spatial split, deterministic and independent from outputs.
 splits=np.array(['test' if (sy*76+sx)%5==0 else 'valid' if (sy*76+sx)%5==1 else 'train' for sy,sx in keys])
 arrays=dict(sensor_codes=codes,sensor=sensor,input=x,coords=coords,native_jpeg=j,split=splits)
 for i,(g,lut) in enumerate([('S-Gamut3',a.sgamut3_lut),('S-Gamut3.Cine',a.cine_lut)]):
  ref=RawSLog3Reference(pr,Cube(lut),g,mode='raw-alchemy-v0.6.2-fused')
  arrays[str(i)+'_target']=ref(sensor)*16383
 np.savez_compressed(a.output/'pairs.npz',**arrays)
 m=dict(schema='full-native-synthetic-RAW-pairs/1',samples=len(keys),context=a.context,source_sensor_pixels_used=False,
  sensor_code_domain='integer Sony Bayer black 512 white 16383; both chains use identical codes',
  source={str(p):sha(p) for p in [a.capture/'report.json',a.capture/'native-reference.jpg',a.chart/'synthetic.ARW',profile]},
  raw_to_jpeg_offset=[32,20],frontend_vs_uniform_itp=dict(mae=float(np.abs(delta).mean()),max=float(np.abs(delta).max())),
  splits={s:int(np.sum(splits==s)) for s in ['train','valid','test']},extra_compensation=False)
 (a.output/'pairs_manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(m,indent=2))
if __name__=='__main__':main()
