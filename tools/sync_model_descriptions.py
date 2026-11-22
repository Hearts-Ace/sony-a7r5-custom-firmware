"""Refresh model download descriptions from matching public R5 sources."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
for model in ['c2','m4']:
 for meta in (ROOT/(model+'-filters')).glob('*/*.meta.json'):
  item=json.loads(meta.read_text());source=ROOT/'filters'/meta.parent.name/(item['short_name']+'.json');r5=json.loads(source.read_text())
  payload=meta.with_name(item['short_name']+('.a7look' if model=='c2' else '.json'));doc=json.loads(payload.read_text());origin=(item if model=='c2' else doc['provenance'])['source_bin_sha256']
  assert origin==r5['sha256'] and item['sha256']==hashlib.sha256(payload.read_bytes()).hexdigest()
  item.update(training_error=r5['training_error'],metric_source_model='r5',description=r5.get('description',''))
  meta.write_text(json.dumps(item,ensure_ascii=False,indent=2)+'\n')
 print(model,'source metrics synchronized')
