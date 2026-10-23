"""Offline 4.22 packaging with a read-only TAR overlay to conserve disk.
Never opens a camera or modifies original/reference files. Packaging is gated
on final source-bound component replays. Every byte is re-decrypted afterward.
"""
from pathlib import Path
import argparse,hashlib,io,json,os,shutil,struct,sys,tarfile,types
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from build_corrected_fl2_fl3 import geometry,digest_file,digest_stream
from rebuild_tar import update_sum
OUT=ROOT/'research/r5_custom_lut/build_r5_4.22_grid_restore_20261023'
BASE=ROOT/'build_r5_m4strict_4.04_20261015'
AP_SOURCE=ROOT/'analysis/r5_runtime_load421_20261022'
AP_SHA='4066b686a6ba4ff3709393142822b33a18f2da5411829222f3721576e7b7f6b0'
MODULE_SHA='96d7247abf10369dfbda8209b7c67e29ee51d6c3af4568dd364a4d125719460b'
sha=lambda b:hashlib.sha256(b).hexdigest()
def save(p,q):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(q,indent=2,ensure_ascii=False)+'\n')
class OverlayStream(io.RawIOBase):
 def __init__(self,source,rows):self.f=source.open('rb');self.rows=rows;self.position=0;self.length=source.stat().st_size
 def readable(self):return True
 def seekable(self):return True
 def tell(self):return self.position
 def seek(self,n,whence=0):
  self.position=n if whence==0 else self.position+n if whence==1 else self.length+n
  if self.position<0:raise ValueError('Negative offset')
  return self.position
 def read(self,n=-1):
  n=max(0,self.length-self.position)if n<0 else min(n,max(0,self.length-self.position));start=self.position;self.f.seek(start);result=bytearray(self.f.read(n));end=start+len(result)
  for lo,hi,path in self.rows:
   if lo<end and hi>start:
    a,b=max(start,lo),min(end,hi)
    with path.open('rb')as f:f.seek(a-lo);replacement=f.read(b-a)
    assert len(replacement)==b-a;result[a-start:b-start]=replacement
  self.position=end;return bytes(result)
 def close(self):self.f.close();super().close()
class Overlay:
 def __init__(self,source,rows):self.source,self.rows=source,rows
 def open(self,mode):assert mode=='rb';return OverlayStream(self.source,self.rows)
 def stat(self):return self.source.stat()
def cp_partition():
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'patched').mkdir(exist_ok=True);(OUT/'evidence').mkdir(exist_ok=True)
 assert not(OUT/'BODYDATA.DAT').exists(),'Refuse changing an already packaged release'
 source=BASE/'patched/nflasha8';old,offsets,unit,meta=geometry(source,'cpapp-b.bin');new=(HERE/'cp/cp420-grid.NONINSTALLABLE.bin').read_bytes();assert len(old)==len(new)
 assert sha(old)=='8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32'
 dest=OUT/'patched/nflasha8';shutil.copyfile(source,dest)
 with dest.open('r+b')as f:
  for i,at in enumerate(offsets):chunk=new[i*unit:(i+1)*unit];f.seek(at);f.write(chunk)
  f.flush();os.fsync(f.fileno())
 actual,o,u,m=geometry(dest,'cpapp-b.bin');assert actual==new and(o,u,m)==(offsets,unit,meta)
 spans=sorted((at,at+min(unit,len(new)-i*unit))for i,at in enumerate(offsets))
 with source.open('rb')as x,dest.open('rb')as y:
  pos=0
  for a,b in spans:assert x.read(a-pos)==y.read(a-pos);x.seek(b);y.seek(b);pos=b
  assert x.read()==y.read()
 save(OUT/'evidence/cp_partition.json',dict(passed=True,CP_sha256=sha(new),partition_sha256=digest_file(dest),original_partition_sha256=digest_file(source),all_other_bytes_unchanged=True,full_component_readback=True))
def archive():
 source=BASE/'patched/firmware.tar'
 replacements={'0700_part_image/dev/nflasha8':OUT/'patched/nflasha8','0700_part_image/dev/nflasha15':AP_SOURCE/'ap/nflasha15'}
 with tarfile.open(source,'r:')as t:
  members=t.getmembers();by={m.name:m for m in members};assert len(by)==len(members)
  name='0701_part_image_sum/part_image.sum';mapping={n.removeprefix('0700_part_image/'):p for n,p in replacements.items()}
  text,changes=update_sum(t.extractfile(name).read().decode('ascii'),mapping,{n:p.stat().st_size for n,p in mapping.items()})
  assert len(changes)==2;p=OUT/'patched/part_image.sum';p.write_text(text);replacements[name]=p
 rows=[]
 for n,p in sorted(replacements.items(),key=lambda kv:by[kv[0]].offset_data):
  m=by[n];assert p.stat().st_size==m.size;rows.append((m.offset_data,m.offset_data+m.size,p))
 overlay=Overlay(source,rows);h=digest_stream(overlay.open('rb'));facts=[]
 with source.open('rb')as a,overlay.open('rb')as b:
  pos=0
  for lo,hi,path in rows:
   left=lo-pos
   while left:n=min(4<<20,left);assert a.read(n)==b.read(n);left-=n
   with path.open('rb')as p:
    left=hi-lo
    while left:n=min(4<<20,left);assert b.read(n)==p.read(n);left-=n
   a.seek(hi);pos=hi
  while True:
   x=a.read(4<<20);y=b.read(len(x));assert x==y
   if not x:break
 with tarfile.open(source,'r:')as a,overlay.open('rb')as f,tarfile.open(fileobj=f,mode='r:')as b:
  assert [m.get_info()for m in a.getmembers()]==[m.get_info()for m in b.getmembers()]
  for m in members:
   if not m.isfile():continue
   before,after=digest_stream(a.extractfile(m)),digest_stream(b.extractfile(m));assert after==(digest_file(replacements[m.name])if m.name in replacements else before)
   assert (before!=after)==(m.name in replacements);facts.append(dict(name=m.name,sha256=after,baseline_sha256=before,changed=before!=after))
 q=dict(passed=True,source_sha256=digest_file(source),output_sha256=h,bytes=source.stat().st_size,changed_members=list(replacements),members=facts,crc_updates=changes,virtual_archive=True,all_other_bytes_headers_padding_trailer_unchanged=True,overlay_source=str(source.relative_to(ROOT)),overlay_ranges=[dict(start=lo,end=hi,path=str(p.relative_to(ROOT)),sha256=digest_file(p))for lo,hi,p in rows])
 save(OUT/'evidence/archive_verification_422.json',q);return overlay

def read_receipt(base,name):
 path=base/name;q=json.loads(path.read_text());assert q['passed'],str(path)
 return q,dict(path=str(path.relative_to(ROOT)),sha256=digest_file(path),passed=True)
def reused_ap_evidence():
 """Explicitly reference unchanged 4.21 AP checks, never relabel them 4.22."""
 asha=digest_file(AP_SOURCE/'ap/appFw.so');assert asha==AP_SHA
 assert digest_file(AP_SOURCE/'import/runtime_rx.bin')==MODULE_SHA
 rows=[]
 for name in ['sd_final_replay.json','sd_retained_replay.json']:
  q,r=read_receipt(AP_SOURCE,name);assert q['candidate_sha256']==asha,name
  assert q['cases']>=(150 if name=='sd_final_replay.json'else 2),name
  rows.append(dict(r,cases=q['cases']))
 for name in ['current_enqueue_bias0.json','current_enqueue_bias40000000.json']:
  q,r=read_receipt(AP_SOURCE,name);assert q['source_sha256']==asha,name;rows.append(r)
 q,r=read_receipt(AP_SOURCE,'ap_session_replay.json');assert q['module_sha256']==MODULE_SHA;rows.append(r)
 for name in ['import/host_tests.json','import/grid_persist_tests.json','import/log420_tests.json']:
  q,r=read_receipt(AP_SOURCE,name);rows.append(r)
 q,r=read_receipt(AP_SOURCE,'ap/ap_build.json');assert q['AP_sha256']==asha and q['native_readonly_e2fsck_passed']
 assert q['partition_sha256']==digest_file(AP_SOURCE/'ap/nflasha15')
 audit=AP_SOURCE/'import/module_audit.json';assert digest_file(audit)==q['module_audit_sha256']
 # Audit all actual compiled C/header inputs. Test-fixture scripts were updated
 # after that AP build and are separately bound by the old final receipts.
 sources=json.loads(audit.read_text())['sources'];production=[]
 for name,h in sources.items():
  if Path(name).suffix not in ('.c','.h','.S'):continue
  p=ROOT/name;assert digest_file(p)==h,name
  production.append(dict(path=name,sha256=h))
 rows.append(r)
 report=dict(schema='r5-422-unchanged-ap-evidence-reuse/1',passed=True,
  AP_sha256=asha,module_sha256=MODULE_SHA,partition_sha256=q['partition_sha256'],
  AP_path=str((AP_SOURCE/'ap/appFw.so').relative_to(ROOT)),
  partition_path=str((AP_SOURCE/'ap/nflasha15').relative_to(ROOT)),
  module_audit=dict(path=str(audit.relative_to(ROOT)),sha256=digest_file(audit)),
  production_sources=production,reused_421_receipts=rows,
  reexecuted_for_422=False,reason='AP module, AP image, configuration format and file worker unchanged; new CP receives fresh cross-core and component regressions.')
 save(HERE/'release_tests/reused_ap421.json',report);return asha,report
def gates():
 csha=digest_file(HERE/'cp/cp420-grid.NONINSTALLABLE.bin');asha,ap=reused_ap_evidence()
 build=json.loads((HERE/'cp/build.json').read_text());assert build['candidate_sha256']==csha and build['reverse404_exact']
 assert build['BSS_extension_bytes']==32 and build['bank_bytes']==28768
 assert build['sources'],'CP source manifest missing'
 for name,h in build['sources'].items():assert digest_file(ROOT/name)==h,('CP build source changed',name)
 assert build['restore_entry_count']==32 and build['restore_ready_limit']==31
 assert build['restore_cache_offset']==build['restore_used_offset']==207880
 assert build['restore_entry_offset']==build['restore_cache_offset']+8
 assert build['restore_entry_bytes']==2936 and build['restore_entry_raw_bytes']==1216
 assert build['restore_entry_packed_bytes']==1620
 assert build['restore_entry_offset']+build['restore_entry_count']*build['restore_entry_bytes']==build['heap_bytes']
 assert build['restore_entry_raw_offset']+build['restore_entry_raw_bytes']<=build['restore_entry_work_offset']
 assert build['restore_entry_packed_offset']+build['restore_entry_packed_bytes']==build['restore_entry_bytes']
 assert build['restore_key']==dict(source_present_bit=24,kind_shift=16,transform_shift=8,level_classes=list(range(9)),level_ge8_maps_to=8,kind0_nonnull_raw_bytes=162,kind1_nonnull_raw_bytes=1215,kind2_nonnull_raw_bytes=162,null_raw_bytes=0)
 assert build['retired_grid_detours']==['0x230ee0','0x230f0a','0x230f0c','0x2312f0','0x230f62']
 assert build['controller_handoff']==dict(callsite='0x719f16',max_root3=1,native_index_range=[0,3],legacy_destination='index<=2 || (index==3 && env6==1)',added_destination='index==3 && root1==1 && env_domain==6 && env6==0',custom_enable='immutable table ready && root2c4==0; late native packet gates retained',native_fallback='original controller enable/strength retained; immutable original-builder packed table submitted',unsupported_root36='explicit disable, packed0, submit0, diag reason6')
 cp_reports=['cp/loader_replay.json','cp/native_color_replay.json','cp/native53_replay.json','cp/grid_replay.json','cp/observer_abi_replay.json','import/grid_status_replay.json','gamma/final_route_replay.json','gamma/same_look_gamma_updates.json','tests/generations.json','release_tests/component_replays.json','tests/handoff422.json','tests/restore_cache422.json','tests/root_execution_binding.json']
 rows=[]
 for name in cp_reports:
  q,r=read_receipt(HERE,name)
  assert q.get('CP_sha256',q.get('candidate_sha256',q.get('source_cp_sha256',q.get('cp_sha256'))))==csha,(name,'CP hash unbound');rows.append(r)
 q,r=read_receipt(HERE,'gamma/compact_getter_replay.json');rows.append(r)
 assert q['hooks']==11 and q['checks']==2464 and q['code_bytes']==496
 assert q['all_GPR_SP_LR_PC_NZCVQ_GE_equal'] and q['all_capacity_pointer_ready_fallbacks_equal'] and q['stack_writes_only']
 assert q['native_Gamma_data_routes_bounds_unchanged']is True and q['maximum_stack_bytes']==32
 assert q['source_CP_sha256']==build['source_sha256']
 assert q['immutable_old_gates_sha256']==digest_file(ROOT/'analysis/r5_native_grid420_20261022/gamma/getter_build_dynamic/gates.bin')
 assert q['compact_gates_sha256']==digest_file(HERE/'gamma/getter_build_compact/gates.bin')
 for name,h in q['sources'].items():assert digest_file(ROOT/name)==h,('Compact Gamma source changed',name)
 gm=json.loads((HERE/'gamma/getter_build_compact/gates.json').read_text());gr=(HERE/'gamma/getter_build_compact/gates.bin').read_bytes()
 cp=(HERE/'cp/cp420-grid.NONINSTALLABLE.bin').read_bytes();at=int(gm['RX'],16)-0x108000
 assert int(build['RX'],16)==int(gm['RX'],16)+len(gr)
 assert int(build['RX'],16)+build['code_bytes']<=0x1197000
 assert cp[at:at+len(gr)]==gr
 for p in gm['patches']:assert cp[p['offset']:p['offset']+len(bytes.fromhex(p['after']))]==bytes.fromhex(p['after'])
 q=json.loads((HERE/'tests/handoff422.json').read_text())
 assert q['bin_sha256']=='b97a8f36a50fb97ee513ed6dbf93f6dd4acdc7c51447c55ba88ee719f9a1512a'
 assert q['suite']=='native-handoff422/3' and q['cases']==204 and len(q['rows'])==q['cases']
 for name in ['native_wrapper','native_controller','native_packet_and_descriptor','two_AA_lanes','actual_config_writer','logical_enable_byte0','ordinary_and_copy','original_bankguard','packed_generation_guard','levels_1_through_7_and_full','explicit_look_off_preserves_MMIO_and_disables','old_source_survives_new_global','root3_saved_snapshot_consistent','same_generation_upload_copy_diagnostics','native_nonzero_restore_on_clear_missing','old_native_routes_clear_missing','late_source_mutation_isolated','empty_or_missing_generation_hardware_clear_verified']:
  assert q['summary'][name]is True,('Native handoff coverage missing',name)
 assert q['summary']['cross_generation_upload_diagnostics_complete']is False
 q=json.loads((HERE/'tests/restore_cache422.json').read_text())
 assert q['suite']=='native-restore-cache422/1' and q['cases']==411 and len(q['rows'])==q['cases']
 assert q['bin_sha256']=='b97a8f36a50fb97ee513ed6dbf93f6dd4acdc7c51447c55ba88ee719f9a1512a'
 for name in ['native_nonzero_restore_on_clear_missing','restore_cache_31ready_plus_scratch','restore_cache_full_disables','restore_cache_pending_skipped','immutable_restore_entries','source_level_aliases','null_source_transform1_native_math','kind0_nonnull162','source_address_independent_identity','unsupported_restoration_disables','heap_guard','live_context_unchanged','old_native_routes_clear_missing','interleaved_builders_isolated','deferred_old_request_immutable','same_generation_native_diagnostics_unmapped','unified_load_replace_restore_reload']:
  assert q['summary'][name]is True,('Native restoration coverage missing',name)
 for name in ['tests/handoff422.json','tests/restore_cache422.json']:
  binding=json.loads((HERE/name).read_text())['execution_binding']
  assert binding['all_inputs_unchanged']is True and binding['before']==binding['after']
  assert binding['before'][str(HERE/'cp/cp420-grid.NONINSTALLABLE.bin')]==csha
  assert binding['before'][str(HERE/'cp/build.json')]==digest_file(HERE/'cp/build.json')
  for path,h in binding['before'].items():assert digest_file(Path(path))==h,(name,'Replay dependency changed',path)
 q=json.loads((HERE/'tests/generations.json').read_text())
 assert q['allocation_bytes']==build['heap_bytes'] and q['allocation_count']==16
 assert(q['packed_slots'],q['packed_level_classes'],q['packed_words_per_table'])==(12,8,405)
 for name in ['all_packed_words_checked','all_retired_packed_generations_immutable','stale_seal_rejected','pending_owner_cancelled_on_reuse','empty_Gamma_seal','native_initial_and_retained_allocation_OOM_checked']:
  assert q[name]is True,('Generation coverage missing',name)
 q=json.loads((HERE/'release_tests/component_replays.json').read_text());assert q['suites']==8
 assert q['build_sha256']==digest_file(HERE/'cp/build.json') and q['CP_fixed_before_and_after_each_suite']is True
 assert q['source_dependencies_fixed_before_and_after_each_suite']is True
 for path,h in q['sources'].items():assert digest_file(ROOT/path)==h,('Component dependency changed',path)
 for row in q['rows']:
  assert row['passed'] and digest_file(HERE/row['receipt'])==row['receipt_sha256']
  assert digest_file(HERE/row['script'])==row['script_sha256']
  assert digest_file(HERE/row['execution_binding'])==row['execution_binding_sha256']
 q=json.loads((HERE/'cp/grid_replay.json').read_text())
 assert q['cases']==48 and q['fallback_cases']==8
 for name in ['installed_wrapper_callsite','native_controller_packet_AA_two_lanes','retired_detours_strict404_exact','independent405word_model','all12_raw_and_heap_guards']:assert q[name]is True,name
 q=json.loads((HERE/'tests/root_execution_binding.json').read_text())
 assert q['schema']=='r5-422-root-execution-binding/1' and q['build_sha256']==digest_file(HERE/'cp/build.json')
 assert q['input_hashes_fixed_before_and_after_each_suite']is True and len(q['rows'])==3
 for path,h in q['sources'].items():assert digest_file(ROOT/path)==h,('Root replay dependency changed',path)
 for row in q['rows']:
  assert row['passed']is True and digest_file(ROOT/row['receipt'])==row['receipt_sha256']
  assert digest_file(ROOT/row['log'])==row['log_sha256']
 for name in ['tests/ap_transfer.json','tests/retained_transfer.json']:
  q,r=read_receipt(HERE,name);assert q.get('CP_sha256',q.get('cp_sha256'))==csha and q.get('AP_sha256',q.get('ap_sha256',q.get('candidate_sha256')))==asha,name
  assert q['cases']>=(110 if name=='tests/ap_transfer.json'else 8),name
  assert q['cp_hash_fixed_before_each_case']is True,name
  rows.append(r)
 cpq=json.loads((OUT/'evidence/cp_partition.json').read_text());assert cpq['passed'] and cpq['CP_sha256']==csha and cpq['partition_sha256']==digest_file(OUT/'patched/nflasha8')
 v=json.loads((BASE/'verification.json').read_text());assert v['version']=='4.04' and v['source_commit']=='086df3b1e33dfa0206553ac2bb003535c58ddb80'
 assert digest_file(BASE/'patched/firmware.tar')==v['archive_sha256']
 assert set(v['components'])=={'appFw.so','cpapp-b.bin','nflasha5'}
 components={n:dict(row,path=str((BASE/'patched'/n).relative_to(ROOT)))for n,row in v['components'].items()}
 components['appFw.so']=dict(path=str((AP_SOURCE/'ap/appFw.so').relative_to(ROOT)),sha256=asha,reused_421_unchanged=True)
 components['cpapp-b.bin']=dict(path=str((HERE/'cp/cp420-grid.NONINSTALLABLE.bin').relative_to(ROOT)),sha256=csha)
 for row in components.values():assert digest_file(ROOT/row['path'])==row['sha256']
 report=dict(upstream_commit='086df3b1e33dfa0206553ac2bb003535c58ddb80',components=components,
  CP_sha256=csha,AP_sha256=asha,fresh_422_receipts=rows,
  CP_build_sha256=digest_file(HERE/'cp/build.json'),
  native_restore_cache={name:build[name]for name in ['heap_bytes','restore_cache_offset','restore_entry_offset','restore_entry_count','restore_ready_limit','restore_entry_bytes','restore_entry_raw_bytes','restore_entry_packed_bytes','restore_error_resource','restore_error_unsupported','restore_key']},
  reused_ap421_manifest=dict(path=str((HERE/'release_tests/reused_ap421.json').relative_to(ROOT)),sha256=digest_file(HERE/'release_tests/reused_ap421.json')),
  camera_io=False,passed=True)
 save(HERE/'release_tests/release_gate_manifest.json',report);return report
def source_manifest():
 rows=[]
 for p in sorted(HERE.rglob('*')):
  if p.is_file() and p.suffix in ('.py','.c','.h','.S') and '__pycache__'not in p.parts:
   rows.append(dict(path=str(p.relative_to(ROOT)),sha256=digest_file(p)))
 dependencies=['research/r5_custom_lut/build_r5_4.16_bcd_fixed_20261021/source/pack_bcd.py','tools/build_corrected_fl2_fl3.py','tools/rebuild_tar.py','tools/sign_r5_firmware.py','tools/fdat_encrypt.py','tools/ext2read.py','tools/patch_images.py','tools/apply_fl2_fl3_cn2_property.py','tools/build_r5_m4strict_cp.py','tools/verify_r5_m4strict_cp_cpu.py','research/r5_custom_lut/scripts/replay_correction_builder.py','research/r5_custom_lut/scripts/replay_gamma_owned_consumers.py','research/r5_custom_lut/evidence/sd405_cp_binding/evaluate_rx_page_v2.py','analysis/r5_incremental413_20261021/cp/replay_loader_stage413.py','analysis/r5_native_grid420_20261022/gamma/getter_build_dynamic/gates.json','analysis/r5_native_grid420_20261022/gamma/getter_build_dynamic/gates.bin','analysis/r5_grid_restore422_20261023/gamma/getter_build_compact/gates.json','analysis/r5_grid_restore422_20261023/gamma/getter_build_compact/gates.bin','vendor/fwtool.py-a7iv/fwtool/sony/constants.py','vendor/fwtool.py-a7iv/fwtool/sony/fdat.py','vendor/fwtool.py-a7iv/fwtool/sony/dat.py']
 for name in dependencies:
  p=ROOT/name;rows.append(dict(path=name,sha256=digest_file(p)))
 # Preserve the executed test/helper/data inputs, including external native
 # baselines, not merely the current entry scripts. They are also rechecked
 # after encryption so receipts cannot drift during a long package run.
 source_sets=[json.loads((HERE/'release_tests/component_replays.json').read_text())['sources'],json.loads((HERE/'tests/root_execution_binding.json').read_text())['sources']]
 for name in ['tests/handoff422.json','tests/restore_cache422.json']:
  source_sets.append(json.loads((HERE/name).read_text())['execution_binding']['before'])
 for sources in source_sets:
  for name,h in sources.items():
   p=Path(name);p=p if p.is_absolute()else ROOT/p
   assert digest_file(p)==h,name
   rows.append(dict(path=str(p.relative_to(ROOT)),sha256=h))
 by={}
 for row in rows:
  if row['path']in by:assert by[row['path']]==row['sha256']
  by[row['path']]=row['sha256']
 rows=[dict(path=name,sha256=h)for name,h in sorted(by.items())]
 q=dict(schema='r5-422-source-manifest/1',rows=rows,
  note='Manifest of new source tree and direct packaging/replay dependencies; unchanged AP production sources and receipts are separately bound by reused_ap421.json. No private key material included.')
 save(OUT/'evidence/source_manifest.json',q)
 return q
def package():
 gate=gates();source_manifest();v=archive();source=ROOT/'research/r5_custom_lut/build_r5_4.16_bcd_fixed_20261021/source/pack_bcd.py';pack=types.ModuleType('native422_package');pack.__file__=str(ROOT/'tools/build_r5_m4strict403.py');exec(compile(source.read_text(),str(source),'exec'),pack.__dict__)
 for name in ['release_gate_manifest.json','reused_ap421.json']:
  shutil.copyfile(HERE/'release_tests'/name,OUT/'evidence'/name)
 original_digest=pack.digest_file;pack.digest_file=lambda p:digest_stream(v.open('rb'))if p is v else original_digest(p)
 pack.OUT=OUT;pack.TAR=v;pack.TAG='422';pack.VERSION='4.22';pack.components=gates;pack.build_package()
 q=json.loads((OUT/'verification.json').read_text());q.pop('exact_four_member_scope_verified',None)
 q.update(runtime_lifecycle='unchanged4.21 AP sessions and SD worker; immutable CP generations with request-bound custom/native grid handoff', firmware_release='4.22', experimental_candidate=True, camera_tested=False, runtime_grid='request-bound immutable405-node custom packed tables and runtime-native restore snapshots with original builder/uploader; native policy gates preserved; coordinates/response uncalibrated', config_version=3, SD_import_policy='complete replacement; omitted looks cleared; empty BIN clears all', SD_diagnostic_log='R5IMPORT.LOG', hot_reload=False, base_firmware='4.04 native baseline plus12 ordinal SD parameter/name overwrite',version_encoding='BCD',encoded_version_hex='2204',virtual_archive=True,no_old_slot_selection_tokens=True,no_Q_identity_table=True,extra_compensation_matrix_included=False,compensation_grid_included=True,native12_order=['ST','PT','NT','VV','VV2','FL','FL2','FL3','IN','SH','BW','SE'],SD_file='R5NATIVE.BIN',device_acceptance_tested=False,
  native_restore_cache=gate['native_restore_cache'],maximum_retained_CP_heap_bytes=16*gate['native_restore_cache']['heap_bytes'],
  compact_Gamma_getters=dict(code_bytes=496,old_code_bytes=968,bytes_saved=472,maximum_stack_bytes=32,differential_cases=2464),
  unchanged_AP_reused_from='4.21',release_gate_manifest_sha256=digest_file(HERE/'release_tests/release_gate_manifest.json'),source_manifest_sha256=digest_file(OUT/'evidence/source_manifest.json'),
  AP_log_session_marker='BOOT421',CP_protocol_BUILD='0x420',legacy_diagnostic_markers_preserved=True,
  limitations=['Offline instruction replay, filesystem comparison, signatures and complete independent decryption passed; these do not demonstrate camera boot, real shutter scheduling, ISP acceptance or final JPG pixels.',
  '4.21 user observation showed live shooting preview grid but no visible JPG difference. 4.22 repairs reproduced native handoff coverage gaps; the unique triggering state of that shutter was not captured.',
  'Original native mode/late enable gates remain. Real camera lifecycle, memory budget and preview/JPG behavior need acceptance.',
  'Native restoration uses runtime RAM source snapshots and retained immutable cache entries; its bounds, resource behavior and CPU/MMIO restoration are replayed, while real camera/ISP acceptance is unverified.',
  'Native raw snapshot copies are not atomic against concurrent source producers; source stability during the short copy and physical CPU/cache coherency remain device boundaries. Resource/unsupported failures disable the audited stage and report a reason rather than keep a prior table enabled.',
  'Old-generation packed table lifetime and source binding are covered, but upload diagnostic counters still consult the current global generation and can omit old-generation delayed consumers.',
  'No camera, block device or SD card was accessed for this build. Original conditional CP NOR update chain and version check are preserved.'])
 save(OUT/'verification.json',q)
 assert(OUT/'FDAT.header.4.22.bin').read_bytes()[32:34]==bytes.fromhex('2204')
 assert(OUT/'BODYDATA.DAT').is_file() and not(OUT/'BODYDATA.DAT').is_symlink() and(OUT/'BODYDATA.DAT').stat().st_size==754525608
 # Ensure all recorded source and receipt inputs remain exact after the long
 # encryption/decryption step. Never claim a receipt for a later source edit.
 for row in json.loads((OUT/'evidence/source_manifest.json').read_text())['rows']:
  assert digest_file(ROOT/row['path'])==row['sha256'],('Source changed while packaging',row['path'])
 assert digest_file(OUT/'evidence/release_gate_manifest.json')==q['release_gate_manifest_sha256']
 final_gate=json.loads((OUT/'evidence/release_gate_manifest.json').read_text())
 assert digest_file(HERE/'cp/build.json')==final_gate['CP_build_sha256']
 for row in final_gate['components'].values():assert digest_file(ROOT/row['path'])==row['sha256']
 for row in final_gate['fresh_422_receipts']:
  assert digest_file(ROOT/row['path'])==row['sha256']
 (OUT/'SHA256SUMS').write_text(''.join(digest_file(p)+'  '+str(p.relative_to(OUT))+'\n'for p in sorted(OUT.rglob('*'))if p.is_file()and p.name not in('SHA256SUMS','README.md')))
 print(json.dumps(dict(DAT=str(OUT/'BODYDATA.DAT'),SHA256=q['output_sha256'])))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--stage',choices=['images','package'],required=True);args=a.parse_args();cp_partition()if args.stage=='images'else package()
