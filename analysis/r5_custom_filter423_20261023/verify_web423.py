"""Local HTTP export contract and Python/C interop fixtures; no camera IO."""
from pathlib import Path
import sys,hashlib,json,io,zipfile,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'research/r5_custom_lut/web'))
import core
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 folder=HERE/'web_tests';folder.mkdir(exist_ok=True)
 boot=json.load(urllib.request.urlopen('http://127.0.0.1:4183/api/bootstrap'))
 entries=boot['presets']
 entries[0]['short_name']='F01';entries[0]['full_name']='独立配置一'
 entries[1]['short_name']='F02';entries[1]['full_name']='独立配置二'
 entries[0]['grid_5x9x9']['coefficients'][0][0][0][0]=-64
 entries[1]['grid_5x9x9']['coefficients'][2][4][8][8]=63
 cfg=core.config(entries[:2]);binary=core.compiler.pack(cfg)
 (folder/'interop_v4.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
 (folder/'interop_v4.bin').write_bytes(binary)
 def request(path,body):
  return urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:4183'+path,
      data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-R5-Token':boot['token']}))
 validation=json.load(request('/api/validate',cfg));assert validation['valid'] and validation['bytes']==len(binary)
 with zipfile.ZipFile(io.BytesIO(request('/api/export',cfg).read()))as archive:
  assert set(archive.namelist())=={'R5NATIVE.BIN','native_config.json','export_audit.json'}
  assert archive.read('R5NATIVE.BIN')==binary
  assert json.loads(archive.read('native_config.json'))==cfg
  audit=json.loads(archive.read('export_audit.json'))
  assert audit['format_version']==4 and audit['firmware']=='4.23' and audit['grid_required']
  assert audit['config_numbers_are_independent']
 assert core.compiler.unpack(binary)==cfg
 clear=core.config([])
 with zipfile.ZipFile(io.BytesIO(request('/api/export',clear).read()))as archive:
  assert len(archive.read('R5NATIVE.BIN'))==128
 rejected=0
 for wrong in [dict(cfg,schema='r5-native-overwrite-config/3'),dict(cfg,compensation_grid_enabled=False)]:
  try:request('/api/validate',wrong)
  except urllib.error.HTTPError as e:assert e.code==400;rejected+=1
  else:raise AssertionError('Legacy config accepted')
 report=dict(passed=True,HTTP_exports=2,legacy_rejections=rejected,
  binary_bytes=len(binary),binary_sha256=sha(binary),grid_required=True,
  separate_short_and_full_names=True,only_v4=True,empty_set_clear=True,
  camera_IO=False,sources={str(p.relative_to(ROOT)):sha(p.read_bytes())for p in [Path(__file__),core.COMPILER_PATH,core.HERE/'core.py',core.HERE/'server.py',core.HERE/'grid_distillation.py',core.HERE/'static/app.js',core.HERE/'static/index.html']})
 (folder/'http_export.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
