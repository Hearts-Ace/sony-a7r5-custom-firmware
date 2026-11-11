from pathlib import Path
import hashlib,json
H=Path(__file__).resolve().parent;R=H.parents[1];U=R/'analysis/r5_icons_unified458_20261111/resources';B=H/'build-adjusted/runtime/analysis/r5_aspect456_20261110/resources/output-build'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
names=[r['name']for r in json.loads((U/'manifest.json').read_text())['files']]
assert len(names)==70 and all(sha(U/n)==sha(B/n)for n in names)
print('All 70 resources exactly match approved unified preview')
