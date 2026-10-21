"""Read-only delivered native12 source/artifact/patch verification. No camera."""
from pathlib import Path
import hashlib,json,struct,zlib,sys
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;OUT=ROOT/'research/r5_custom_lut/build_r5_4.18_native12_20261021'
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from build_corrected_fl2_fl3 import geometry,digest_file

def main():
 rows=json.loads((OUT/'evidence/source_snapshot.json').read_text())['files']
 for r in rows:assert digest_file(ROOT/r['source'])==digest_file(OUT/r['snapshot'])==r['sha256'],r
 for line in (OUT/'SHA256SUMS').read_text().splitlines():
  h,n=line.split('  ',1);assert digest_file(OUT/n)==h,n
 v=json.loads((OUT/'verification.json').read_text());assert digest_file(OUT/'BODYDATA.DAT')==v['output_sha256'];assert v['saved_signature_valid']and v['tampered_signature_rejected']and v['outer_crc_valid']and v['plaintext_verification']['every_plaintext_byte_matches']
 header=(OUT/'FDAT.header.4.18.bin').read_bytes();assert header[32:34]==bytes.fromhex('1804');assert zlib.crc32(header[12:512])==struct.unpack_from('<I',header,8)[0]
 cp=(HERE/'cp/cp418-native12.NONINSTALLABLE.bin').read_bytes();b=json.loads((HERE/'cp/build.json').read_text());assert hashlib.sha256(cp).hexdigest()==b['candidate_sha256'];undo=bytearray(cp)
 for p in reversed(b['patches']):
  at=p['offset'];after=bytes.fromhex(p['after']);before=bytes.fromhex(p['before']);assert undo[at:at+len(after)]==after;undo[at:at+len(before)]=before
 assert undo==(ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin').read_bytes()
 x,*_=geometry(OUT/'patched/nflasha8','cpapp-b.bin');assert x==cp
 x,*_=geometry(HERE/'ap/nflasha15','appFw.so');assert hashlib.sha256(x).hexdigest()==v['components']['appFw.so']['sha256']
 reports=['cp/loader_replay.json','cp/native_color_replay.json','cp/native53_replay.json','import/native_probe_replay.json','import/native_transfer_replay.json','gamma/final_replay.json']
 for name in reports:
  q=json.loads((HERE/name).read_text());assert q.get('passed',False);assert q.get('CP_sha256',q.get('candidate_sha256'))==b['candidate_sha256'],name
 import importlib.util
 spec=importlib.util.spec_from_file_location('native_config',HERE/'import/native_overwrite_config.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 assert m.pack(m.load(OUT/'parameters/native_config.json'))==(OUT/'parameters/R5NATIVE.BIN').read_bytes()
 print(json.dumps(dict(passed=True,source_files=len(rows),CP_reverse404_exact=True,BCD='4.18',DAT_sha256=v['output_sha256'],device_IO=False)))
if __name__=='__main__':main()
