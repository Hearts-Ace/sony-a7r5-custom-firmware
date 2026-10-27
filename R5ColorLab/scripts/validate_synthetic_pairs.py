"""Reject mixed sensor/capture provenance and photograph training data."""
from pathlib import Path
import hashlib,json
import numpy as np

def validate_profile(profile,manifest):
 if profile.get('source_raw_sha256')!=manifest['source_sha256']:raise ValueError('Profile and RAW metadata source differ')
 if profile.get('black_levels')!=[512]*4 or profile.get('white_level')!=16383:raise ValueError('Unsupported sensor normalization')
 if profile.get('exposure_ev')!=0:raise ValueError('This calibrated workflow requires explicit zero EV')

def validate(arrays,chart,capture,context):
 chart,capture=Path(chart),Path(capture)
 manifest=json.load(open(chart/'manifest.json'));verified=json.load(open(chart/'libraw_verification.json'))
 if manifest.get('source_sensor_pixels_used') is not False or verified.get('mismatched')!=0 or verified.get('decoded_pixels')!=9728*6656:raise ValueError('Synthetic pixels not independently verified')
 if hashlib.sha256((chart/'synthetic.ARW').read_bytes()).hexdigest()!=manifest['output_sha256']:raise ValueError('Synthetic RAW identity mismatch')
 r=json.load(open(capture/'report.json'))
 if not r.get('complete') or r.get('truncated') or r['manifest'].get('synthetic_sensor') is not True or r['manifest']['raw_sha256']!=manifest['output_sha256']:raise ValueError('Capture is not the complete verified synthetic scene')
 if any(x['message'].get('type')=='error' or x['message'].get('payload',{}).get('kind')=='capture_error' for x in r['messages']):raise ValueError('Capture contains errors')
 groups={};expected={}
 for row in r['messages']:
  q=row['message'].get('payload',{});l=q.get('label','')
  if not l.startswith('synthetic-input-'+str(context)+'-'):continue
  b=(capture/row['data']['file']).read_bytes()
  if hashlib.sha256(b).hexdigest()!=row['data']['sha256']:raise ValueError('Capture buffer changed')
  g=groups.setdefault(l.rsplit('-ch',1)[0],dict(points=q['points'],planes={}))
  g['planes'][q['ch']]=np.frombuffer(b,dtype='<u2').reshape(-1,9)
 for g in groups.values():
  v=np.stack([g['planes'][i] for i in range(3)],axis=-1)
  for q,p in zip(g['points'],v):
   key=(q['gx'],q['gy'])
   if key in expected:raise ValueError('Repeated synthetic coordinate')
   expected[key]=(q['sx'],q['sy'],p)
 coords=arrays['coords'];rgb=np.load(chart/'chart.npz')['rgb_codes'];codes=[];native=[];split=[]
 if manifest['tile']!=128 or rgb.shape!=(52,76,3):raise ValueError('Unsupported chart geometry')
 if len(coords)!=len(expected) or len(np.unique(coords,axis=0))!=len(coords):raise ValueError('Missing or duplicate training colors')
 for coord in coords:
  if tuple(coord) not in expected:raise ValueError('Unknown sensor coordinate')
  sx,sy,x=expected[tuple(coord)];codes.append(rgb[sy,sx]);native.append(x)
  split.append('test' if (sy*76+sx)%5==0 else 'valid' if (sy*76+sx)%5==1 else 'train')
 if not np.array_equal(arrays['sensor_codes'],codes):raise ValueError('Sensor code provenance mismatch')
 if not np.array_equal(arrays['input'],native):raise ValueError('Native frontend provenance mismatch')
 if not np.array_equal(arrays['split'],split):raise ValueError('Train/valid/test split changed')
 if not np.array_equal(arrays['sensor'],(np.asarray(codes,dtype=float)-512)/15871):raise ValueError('Sensor normalization changed')
 return dict(passed=True,samples=len(coords),sensor_bytes_independently_verified=True,native_frontend_bound_to_capture=True,fixed_split_verified=True,photograph_training=False)
