"""Validate public M4/C2 downloadable files and their page descriptions."""
from pathlib import Path
import base64,hashlib,json,struct
M4_GAMMA_CAP=130944
ROOT=Path(__file__).resolve().parents[1]
FIELDS='defaults draft engine_abi format id mode model name parameters required_capabilities revision version'.split()
for model,ext in [('c2','.a7look'),('m4','.json')]:
 root=ROOT/(model+'-filters');names=set();count=0
 for meta in sorted(root.glob('*/*.meta.json')):
  item=json.loads(meta.read_text(encoding='utf8'));name=meta.name[:-10];file=meta.with_name(name+ext);blob=file.read_bytes();doc=json.loads(blob)
  assert item['schema']=='sony-single-filter-download/1' and item['model']==model and item['short_name']==name
  assert name not in names and hashlib.sha256(blob).hexdigest()==item['sha256'];names.add(name)
  assert doc['name']==item['name'] and item['camera_tested'] is False
  source=json.loads((ROOT/'filters'/meta.parent.name/(name+'.json')).read_text())
  assert item['metric_source_model']=='r5' and item['training_error']==source['training_error']
  assert doc['conversion' if model=='c2' else 'provenance']['source_bin_sha256']==source['sha256']
  if model=='c2':
   assert doc['schema']=='a7c2-creative-look/2' and doc['target']=={'model':'ILCE-7CM2','firmware':'2.01'}
   grid=base64.b64decode(doc['table_base64'],validate=True);assert len(grid)==1215 and all(v<64 or v>=192 for v in grid)
   edit=doc['edit_native'];assert edit['schema']=='a7c2-edit-native-fit/1' and len(edit['gamma_7805_x'])==128
   for stage in ['baseline','fitted']:
    assert len(bytes.fromhex(edit[stage]['matrix_780f_hex']))==276 and len(edit[stage]['gamma_7806_y'])==128 and len(edit[stage]['cc1_direct_raw'])==8
   icon=base64.b64decode(doc['menu_icon']['png_base64'],validate=True)
   assert icon[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>IIBBBBB',icon[16:29])==(26,19,8,0,0,0,0)
  else:
   assert doc['format']=='camera-look' and doc['version']==2 and doc['model']=='ILCE-7M4' and len(blob)<=131072
   payload=json.dumps({k:doc[k] for k in FIELDS},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
   assert hashlib.sha256(b'CAMLOOK2\0'+payload).hexdigest()==doc['payload_sha256']
   p=doc['parameters'];records=p['photo']['gamma']['records']+p['live']['gamma']['records']
   assert len(p['photo']['gamma']['records'])==7 and len(p['live']['gamma']['records'])==1
   assert all(len(r)==572 and r==records[0] for r in records)
   for record in records:
    gamma=list(struct.unpack('<129I',bytes(record[:516])))
    assert all(0 <= value <= M4_GAMMA_CAP for value in gamma)
    assert struct.unpack_from('<I',bytes(record),544)[0] == gamma[-1]
   assert p['photo']['coefficients']==p['live']['coefficients'] and p['photo']['matrices']==p['live']['matrices'] and p['grid']['photo']==p['grid']['live']
  count+=1
 payloads={p for p in root.glob('*/*'+ext) if not p.name.endswith('.meta.json')}
 assert payloads=={p.with_name(p.name[:-10]+ext) for p in root.glob('*/*.meta.json')}
 print(model.upper(),count,'single-filter files verified')
