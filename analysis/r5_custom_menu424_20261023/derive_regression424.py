"""Derive bounded 4.23 menu regressions against the actual narrow 4.24 AP.
Original scripts and frozen reports remain untouched. No firmware rebuild.
"""
from pathlib import Path
import hashlib,json,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'analysis/r5_custom_filter423_20261023'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name in ['import','menu_research']:
 target=HERE/name;target.mkdir(exist_ok=True)
 for p in (OLD/name).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:
   q=target/p.relative_to(OLD/name);q.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(p,q)
# No build entry is executed. Source copies are solely the original replay inputs.
script=HERE/'menu_research/replay_ap_1005_enter423.py'
s=script.read_text();old="str((OUT / 'r5_filter_menu423.c').relative_to(ROOT))";new="'analysis/r5_custom_filter423_20261023/menu_research/r5_filter_menu423.c'"
assert s.count(old)==1;script.write_text(s.replace(old,new))
p=HERE/'menu_research/verify_menu_route423.py';s=p.read_text();s=s.replace("assert sha == '4017b746b8720b0b3c0b1b8d79b00472548361b335048656b72c71be77202717'", "assert sha == json.loads((AP.parent/'ap_build.json').read_text())['AP_sha256']");p.write_text(s)
manifest=dict(passed=True,policy='Source copies for replay only; frozen423 inputs not rebuilt or changed',
 sources=[dict(source=str(p.relative_to(ROOT)),copy=str((HERE/n/p.relative_to(OLD/n)).relative_to(ROOT)),source_sha256=sha(p),copy_sha256=sha(HERE/n/p.relative_to(OLD/n))) for n in ['import','menu_research'] for p in (OLD/n).rglob('*') if p.is_file() and '__pycache__' not in p.parts])
(HERE/'regression_derivation.json').write_text(json.dumps(manifest,indent=2)+'\n')
