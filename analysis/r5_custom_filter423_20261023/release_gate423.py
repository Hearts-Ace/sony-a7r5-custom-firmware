"""Freeze source-bound offline acceptance for the completed 4.23 candidate.

This consumes completed receipts; it does not replace native CPU replay or
device acceptance. No camera, removable media or block-device operations.
"""
from pathlib import Path
import hashlib,json,sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools'),str(HERE)]
import package423 as pack

AP='4017b746b8720b0b3c0b1b8d79b00472548361b335048656b72c71be77202717'
CP='8b38e753f34b1667d79b69079d911b9e6595f1ce1b873cb8e014437c6b4c494d'
MODULE='ea09b21bcbdd2466d9b8550c90e52e6555350548ffdcf57c521e6d85425e5941'
AUDIT='a62d36c5a94b50de5d7d7e669edc7a8b7d9c0fc2bdbb9c7a80558dc34ea9bff8'
def sha(p):return pack.digest_file(p)
def read(p):return json.loads(p.read_text())
def row(p):return dict(path=str(p.relative_to(ROOT)),sha256=sha(p))

def main():
 target=HERE/'release_tests/final_gate.json'
 assert not target.exists(),'Refuse replacing a frozen final gate'
 for name,expected in [('ap/appFw.so',AP),('cp/cp423.NONINSTALLABLE.bin',CP),
                       ('import/runtime_rx.bin',MODULE),('import/module_audit.json',AUDIT)]:
  assert sha(HERE/name)==expected,name
 receipts=[HERE/n for n in [
  'ap/ap_build.json','ap/menu_parent_patch.json',
  'ap_design/codec_test.json','ap_design/selection_store_test.json',
  'ap_design/runtime_test.json','ap_design/runtime_restore_test.json',
  'ap_design/ap_cp_data_replay.json','ap_design/ap_cp_select_replay.json',
  'ap_design/ap_cp_retained_replay.json','ap_design/sd_replay.json',
  'ap_design/ap_session_replay.json','ap_design/menu_foundation_replay.json',
  'menu_research/ap_1005_enter423_replay.json',
  'menu_research/native_1005_push_pop423_replay.json',
  'menu_research/menu_route423_verification.json',
  'menu_research/presenter_model423_replay.json',
  'menu_research/native_renderer423_replay.json',
  'menu_research/widget_node_detach423_replay.json',
  'cp/filter423_replay.json','cp/cc1_hook423_replay.json','cp/grid423_replay.json',
  'gamma/route423_replay.json','gamma/request423_replay.json']]
 receipts.append(pack.OUT/'evidence/cp_partition.json')
 for p in receipts:
  q=read(p);assert q['passed'] is True,p
  for key,expected in [('AP_sha256',AP),('candidate_sha256',AP),('CP_sha256',CP),
                       ('module_sha256',MODULE),('module_audit_sha256',AUDIT)]:
   if key in q:assert q[key]==expected,(p,key)
  if p.parent.name=='menu_research' and p.name in ('ap_1005_enter423_replay.json',
      'native_1005_push_pop423_replay.json','menu_route423_verification.json'):
   assert q['sha256']==AP,p
 inv=read(HERE/'ap_design/replay_inventory.json')
 assert inv['ap_sha256']==AP and inv['cp_sha256']==CP
 for r in inv['replay_inputs']+inv['replay_outputs']:
  assert sha(ROOT/r['path'])==r['sha256'],r['path']
 for r in inv['replay_outputs']:assert r['passed'] is True
 module=read(HERE/'import/module_audit.json');cpbuild=read(HERE/'cp/build.json')
 assert cpbuild['candidate_sha256']==CP and cpbuild['reverse404_exact'] is True
 bindings={}
 for source in (module['sources'],cpbuild['sources'],read(HERE/'ap_design/host_source_manifest.json')['sha256']):
  for name,digest in source.items():
   assert sha(ROOT/name)==digest,name
   if name in bindings:assert bindings[name]==digest,name
   bindings[name]=digest
 route=read(HERE/'menu_research/menu_route423_verification.json')
 for name,digest in route['artifacts'].items():assert sha(HERE/'menu_research'/name)==digest
 # Independently extract exact integrated components, rather than trusting
 # filenames or the standalone binary next to a partition image.
 for image,name,expected in [(HERE/'ap/nflasha15','appFw.so',AP),
   (pack.OUT/'patched/nflasha8','cpapp-b.bin',CP)]:
  component,_,_,_=pack.geometry(image,name)
  assert hashlib.sha256(component).hexdigest()==expected
 build=read(HERE/'ap/ap_build.json');ap=(HERE/'ap/appFw.so').read_bytes()
 code=(HERE/'import/runtime_rx.bin').read_bytes();lo=build['rx_file']
 assert ap[lo+448:lo+len(code)]==code[448:]
 header=pack.original_header_identity()
 inputs={ROOT/n for n in bindings}
 inputs.update(HERE/n for n in ['ap/appFw.so','ap/nflasha15','ap/e2fsck.log',
  'cp/cp423.NONINSTALLABLE.bin','cp/build.json','import/runtime_rx.bin',
  'import/module_audit.json','ap_design/replay_inventory.json',
  'ap_design/host_source_manifest.json','menu_research/menu_hooks.json',
  'menu_research/renderer_lifetime423_evidence.json',
  'menu_research/presenter_full_model423.bin','web_tests/interop_v4.bin'])
 inputs.add(pack.OUT/'patched/nflasha8')
 extras=[
  'research/r5_custom_lut/build_r5_4.07_stage1_20261020/patched/appFw.so',
  'research/r5_custom_lut/build_r5_4.13_stage5c_20261021/patched/nflasha15',
  'research/r5_custom_lut/build_r5_4.13_stage5c_20261021/evidence/native_bindings.json',
  'research/r5_custom_lut/evidence/sd405_ap_native_directory_binding/strict_ap_link.py',
  'research/r5_custom_lut/evidence/sd405_cp_binding/evaluate_rx_page_v2.py',
  'research/r5_custom_lut/scripts/replay_gamma_owned_consumers.py',
  'research/r5_custom_lut/scripts/build_color_consumers.py',
  'research/r5_custom_lut/scripts/replay_correction_builder.py',
  'research/r5_custom_lut/scripts/audit_sources.py',
  'tools/build_r5_m4strict_cp.py','tools/build_r5_m4strict_gamma.py',
  'tools/verify_r5_m4strict_cp_cpu.py','tools/ext2read.py','tools/patch_images.py',
  'tools/apply_fl2_fl3_cn2_property.py','tools/apply_fl2_fl3_property.py','tools/sony_bk4.py',
  'vendor/fwtool.py-a7iv/fwtool/io/__init__.py',
  'vendor/fwtool.py-a7iv/fwtool/util/__init__.py',
  'analysis/r5_grid_restore422_20261023/replay_handoff422.py',
  'exports/fl2_fl3_grid_compare_20261023/R5NATIVE.BIN',
  'unpacked/r5/usr_complete/lib/libObj.so',
  'BODYDATA.DAT','unpacked/r5/updater.img','unpacked/r5/firmware.fdat',
  'build_r5_partition1_20261014/r5-update-verification-public.pem',
  'build_r5_m4strict_4.04_20261015/verification.json',
  'build_r5_m4strict_4.04_20261015/patched/nflasha8',
  'build_r5_m4strict_4.04_20261015/patched/firmware.tar']
 inputs.update(ROOT/n for n in extras)
 inputs.update(pack.BASE/'patched'/n for n in read(pack.BASE/'verification.json')['components'])
 inputs.update(ROOT/r['path']for r in inv['replay_inputs'])
 report=dict(schema='r5-filter423-final-offline-gate/1',passed=True,version='4.23',
  AP_sha256=AP,CP_sha256=CP,module_sha256=MODULE,module_audit_sha256=AUDIT,
  menu_native_registration_render_selection_back_replayed=True,
  mandatory_grid_and_native_gamma_tail_preserved=True,
  integrated_AP_CP_components_independently_extracted=True,
  integrated_AP_runtime_after_reserved_headers_exact=True,original_header=header,
  inputs=[row(p)for p in sorted(inputs)],receipts=[row(p)for p in receipts],
  camera_io=False,device_acceptance_tested=False,
  limits=['Bounded offline native stages with explicit fixtures; the actual Sony loader/event loop, physical LCD and camera ISP/JPEG pixels are not acceptance-tested.',
   'Real camera heap/cache/stack budgets, power-loss filesystem durability and whole-frame switching across separate processing stages remain unverified.'])
 pack.save(target,report)
 print(json.dumps(dict(passed=True,inputs=len(report['inputs']),receipts=len(receipts),
  AP_sha256=AP,CP_sha256=CP,gate_sha256=sha(target))))

if __name__=='__main__':main()
