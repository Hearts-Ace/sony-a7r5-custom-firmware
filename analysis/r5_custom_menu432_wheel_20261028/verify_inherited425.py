"""Verify exact inherited parameter/grid sources and frozen CP; offline only."""
from pathlib import Path
import hashlib,io,json,sys,struct
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'vendor/audit-python')]
from elftools.elf.elffile import ELFFile
OLD=ROOT/'analysis/r5_custom_filter423_20261023'
CP_SHA='8b38e753f34b1667d79b69079d911b9e6595f1ce1b873cb8e014437c6b4c494d'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 cp=OLD/'cp/cp423.NONINSTALLABLE.bin';assert sha(cp)==CP_SHA
 manifest_path=ROOT/'research/r5_custom_lut/build_r5_4.28_rollback425_20261024/evidence/source_manifest.json'
 assert sha(manifest_path)=='98d68092f4006b716f072ee95684ae57848e25f77b82d45a43a6539f1780648f'
 manifest=json.loads(manifest_path.read_text())
 pinned={r['path']:r['sha256'] for r in manifest['rows']}
 changes={'r5_filter_runtime423.c','r5_filter_runtime423.h','r5_stage413_thread.c','r5_grid420_log.c','r5_runtime_session.c'}
 inherited=[]
 for p in sorted((OLD/'import').iterdir()):
  if p.suffix not in ('.c','.h'):continue
  assert sha(p)==pinned[str(p.relative_to(ROOT))]
  q=HERE/'import'/p.name
  if p.name not in changes:
   assert q.read_bytes()==p.read_bytes(),p.name
   inherited.append(dict(path=str(q.relative_to(ROOT)),sha256=sha(q),source=str(p.relative_to(ROOT))))
 raw=(HERE/'ap/appFw.so').read_bytes();elf=ELFFile(io.BytesIO(raw));audit=json.loads((HERE/'import/module_audit.json').read_text());build=json.loads((HERE/'ap/ap_build.json').read_text())
 assert hashlib.sha256(raw).hexdigest()==build['AP_sha256'] and build['reverse_to407_exact']
 assert build['secondary_identity']['preserves_424_secondary_ID_fix']
 assert build['rx_bytes']<=65536 and 0<audit['bss_bytes']<=196608
 assert len(raw)==97452032
 for s in elf.iter_segments():
  if s['p_type']=='PT_LOAD':assert s['p_filesz']<=s['p_memsz'] and s['p_flags']&3!=3
 rels={at:(info,addend) for at,info,addend in struct.iter_unpack('<QQq',elf.get_section_by_name('.rela.dyn').data())}
 for entry in audit['menu_relocation_addend_remaps']:
  assert rels[int(entry['va'],16)]==(1027,audit['symbols'][entry['symbol']])
 orig=ELFFile(io.BytesIO((ROOT/'assets/firmware/a8d5cd444bf0-appFw.so').read_bytes()))
 assert elf.get_section_by_name('.rela.plt').data()==orig.get_section_by_name('.rela.plt').data()
 gate_path=OLD/'release_tests/final_gate.json';gate=json.loads(gate_path.read_text());assert gate['passed'] and gate['CP_sha256']==CP_SHA
 for name in ('r5_grid422.h','r5_stage423_codec.c','r5_filter_selection423.c','r5_filter_names423.c','sd_native_store.c','sd_native_persist.c','r5_stage413_transfer_core.c'):
  assert any(Path(r['path']).name==name for r in inherited),name
 report=dict(passed=True,AP_sha256=build['AP_sha256'],CP_sha256=CP_SHA,version='4.32',inherited_source_count=len(inherited),inherited_sources=inherited,CP_exactly_frozen423=True,grid_lifecycle_422_preserved=True,BIN_v4_codec_unchanged=True,selection_file_atomic_IO_unchanged=True,native_Gamma_tail_preserved=True,secondary_menu_identity_424_preserved=True,ELF_PLT_exact407=True,no_WX_segments=True,AP_reverse407_exact=True,inherited_gate=dict(path=str(gate_path.relative_to(ROOT)),sha256=sha(gate_path)),limits=['CP parameter/grid consumers are inherited by exact 4.23 component identity and frozen acceptance receipts, not newly executed on the camera.','4.32 changes only the private page against frozen4.31; wheel and button navigation share the same transaction. Startup yielding, SD recovery and worker sources remain byte-identical to4.30 and execute in current-AP SD/worker replay; current menu interaction and D9 parent lifecycle are validated separately.','No physical LCD, camera heap, frame/JPEG or loader execution.'],camera_io=False)
 (HERE/'inherited425.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='inherited_sources'}))
if __name__=='__main__':main()
