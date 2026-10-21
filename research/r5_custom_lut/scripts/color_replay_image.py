"""Bind a replay to the exact consumer recipe and optional integrated CP."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[3]
def image(build,cp_image=None):
    meta=json.loads((build/'build.json').read_text())
    source=Path(cp_image)if cp_image else build/'cp-callsite-replay.NONINSTALLABLE.bin'
    code=source.read_bytes()
    if not cp_image:assert hashlib.sha256(code).hexdigest()==meta['candidate_sha256']
    for p in meta['patches']:
        at=int(p['site'],16)-0x108000;raw=bytes.fromhex(p['replacement'])
        assert code[at:at+len(raw)]==raw,('recipe patch missing from replay image',p['site'])
    page=(build/'color_page.bin').read_bytes();assert hashlib.sha256(page).hexdigest()==meta['page_sha256']
    if cp_image:
        # The integrated loader copies precisely this stored file page to RX.
        assert code[0x1198000-0x108000:0x1199000-0x108000]==page,'stored RX page differs'
    return meta,code,page,dict(path=str(source),sha256=hashlib.sha256(code).hexdigest(),integrated=bool(cp_image),patches_verified=len(meta['patches']))
def output(build,stem,record,explicit=None,cp_image=None):
    path=Path(explicit)if explicit else build/(stem+('.integrated'if cp_image else '')+'.json')
    assert not path.exists(),('refuse to overwrite existing replay evidence',str(path))
    path.write_text(json.dumps(record,indent=2)+'\n');return path
