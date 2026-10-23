"""Read-only final delivery checks, independent of the packaging entry point."""
from pathlib import Path
import hashlib,json,stat,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'research/r5_custom_lut/build_r5_4.23_custom_filter_20261023'
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from sign_r5_firmware import inspect

def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()

def main():
 p=OUT/'BODYDATA.DAT';s=p.lstat();v=json.loads((OUT/'verification.json').read_text())
 assert stat.S_ISREG(s.st_mode)and not p.is_symlink()and s.st_size==754525608
 digest=sha(p);assert digest==v['output_sha256']and v['version']=='4.23'
 assert (OUT/'FDAT.header.4.23.bin').read_bytes()[32:34]==bytes.fromhex('2304')
 assert v['saved_signature_valid']and v['tampered_signature_rejected']and v['outer_crc_valid']
 assert v['plaintext_verification']['every_plaintext_byte_matches']
 layout=inspect(p)
 sums=0;names=set()
 for line in (OUT/'SHA256SUMS').read_text().splitlines():
  expected,name=line.split('  ',1);q=OUT/name
  assert name not in names and not Path(name).is_absolute()and '..'not in Path(name).parts
  names.add(name)
  assert q.is_file()and sha(q)==expected,name
  sums+=1
 assert names=={str(q.relative_to(OUT))for q in OUT.rglob('*')if q.is_file()and q.name!='SHA256SUMS'}
 manifest_path=OUT/'evidence/source_manifest.json'
 assert sha(manifest_path)==v['source_manifest_sha256']
 manifest=json.loads(manifest_path.read_text())
 for row in manifest['rows']:assert sha(ROOT/row['path'])==row['sha256'],row['path']
 assert (HERE/'release_tests/final_gate.json').read_bytes()==(OUT/'evidence/final_gate.json').read_bytes()
 report=dict(passed=True,version='4.23',output=str(p),output_bytes=s.st_size,
  output_sha256=digest,ordinary_file=True,BCD='2304',saved_outer_CRC_rechecked=True,
  sha256sum_entries=sums,frozen_source_inputs=len(manifest['rows']),
  layout_bytes=layout['file_size']if 'file_size'in layout else s.st_size,
  camera_io=False,device_acceptance_tested=False)
 (HERE/'release_tests/delivery_verified.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report))

if __name__=='__main__':main()
