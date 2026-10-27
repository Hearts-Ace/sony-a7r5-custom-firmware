"""Strict offline acceptance gate for actual 4.29 inputs; no device I/O."""
from pathlib import Path
import hashlib,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from package429 import REQUIRED_RECEIPTS,REQUIRED_CHECKS

def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def bound(p):return dict(path=str(p.relative_to(ROOT)),sha256=sha(p))
def main():
 build=read(HERE/'ap/ap_build.json');audit=read(HERE/'import/module_audit.json')
 ap=sha(HERE/'ap/appFw.so');assert ap==build['AP_sha256']
 assert build['native_readonly_e2fsck_passed'] and build['only_AP_payload_changed'] and build['reverse_to407_exact']
 assert build['secondary_identity']['preserves_424_secondary_ID_fix']
 assert build['rx_bytes']<=65536 and audit['bss_bytes']<=196608
 assert build['version']==audit['version']=='4.29'
 for name,digest in audit['sources'].items():assert sha(ROOT/name)==digest,name
 receipts={n:read(HERE/n) for n in REQUIRED_RECEIPTS}
 for n,q in receipts.items():assert q['passed'] and q['AP_sha256']==ap,n
 main=receipts['main_menu425_replay.json'];assert len(main['rows'])==6
 for row in main['rows']:
  assert row['old_alias_keys_checked']==1589
  if row['label']=='candidate425':
   assert len(row['views'])==4 and all(v['produced_mid_present']==1 for v in row['views'])
 assert receipts['title_native_verification425.json']['cases']==16
 page=receipts['menu_research/page425_replay.json'];assert len(page['cases'])==22
 assert {r['mode'] for r in page['cases']}=={'success','failure','timeout','touch','parent_bad','layout','oom','reenter','stock','removed_update','navigation'}
 for row in page['cases']:
  if row['mode']=='stock':assert row['stock_factory_delegated'];continue
  if row['mode']=='oom':assert row['allocation_failure_safe'];continue
  events=row['event_order'];names=[x[0] for x in events]
  if row['mode'] in ('success','touch','timeout','removed_update','navigation'):
   assert names.count('pop')==1 and names.index('parent_value_before_pop')<names.index('pop')
   expected=1 if row['mode'] in ('success','touch','timeout') else 0
   assert events[names.index('parent_value_before_pop')][1]==0x02ff4300+expected
  if row['mode']=='reenter':assert names.count('pop')==1 and 'request' not in names
  if row['mode'] in ('failure','parent_bad'):assert 'pop' not in names
  assert row['background2_not_constructed'] and row['native_adjustment_widgets_absent']
  assert row['menu_mid']=='0x635' and row['independent_row_pid']=='0x1607'
  assert int(row['update_text_resource'],16)==0 and row['update_widgets_not_constructed'] and row['no_reload_requests']
  assert row['created_widgets']==[[0,106],[1,107],[9,2],[11,2],[12,2],[13,2]]+[[i,2]for i in range(16,22)]+[[i,20]for i in range(22,29)]
 nativeview=receipts['menu_research/native_view426_verified.json']
 assert nativeview['native_create_entry']=='0x182b41c' and nativeview['native_create_vtable_slot']=='0x57830a8'
 assert len(nativeview['cases'])==4
 assert {(q['bias'],q['layout']) for q in nativeview['cases']}=={(b,l) for b in ('0x0','0x40000000') for l in (0,1)}
 allowed_widgets=[[0,106],[1,107],[9,2],[11,2],[12,2],[13,2]]+[[i,2]for i in range(16,22)]+[[i,20]for i in range(22,29)]
 for q in nativeview['cases']:
  assert q['actual_constructed_widgets']==allowed_widgets
  assert q['update_resource']=='0x0' and q['update_visible_param'] is False and q['update_widgets_absent'] and q['full_text_bridge']=='关闭'
  assert q['right_adjustment_widgets_absent'] and q['native_create_executed'] and q['compiled_project_accepted_native_param_map']
  dispatch=q['native_dispatch_entries'];assert len(dispatch)==34 and {x['index'] for x in dispatch}==set(range(34))
  actual=[[x['index'],x['type']]for x in dispatch if not x['parameter_only']]
  assert actual==allowed_widgets
  assert [x for x in dispatch if x['index']==14][0]['parameter_only']
  assert all(x['parameter_only'] for x in dispatch if x['index'] in (2,3,4,5,6,7,8,10,14,15,29,30,31,32,33))
  assert q['name_offsets_resolved']==[x['name'] for x in dispatch]
 opened=receipts['menu_research/main_open426_replay.json'];assert len(opened['rows'])==2
 assert {r['bias'] for r in opened['rows']}=={'0x0','0x40000000'}
 for q in opened['rows']:
  assert q['native_1004_enter']=='0x21deab8' and q['menu']=='0x635' and q['target_screen']=='0xd9'
  assert q['queue_records']==1 and q['queue_record_bytes']==20 and q['descriptor_and_native_route']
  assert q['native_menu_pid']=='0x3b2' and q['menu_pid_after_enter']=='0x635' and q['row_pid_unchanged']=='0x1607'
  assert q['native_controller_factory_reached'] and q['exact_factory_slot']=='0x5071080'
 identity=receipts['menu_research/identity426_replay.json']
 assert identity['cases']==8 and len(identity['rows'])==8
 combinations={(r['version'],r['bias'],r['menu_mid'],r['option_row']) for r in identity['rows']}
 assert combinations=={(v,b,m,r) for v in ('frozen425','candidate426') for b in ('0x0','0x40000000') for m,r in (('0x635','0x1607'),('0x14c','0x635'))}
 for q in identity['rows']:
  frozen=q['version']=='frozen425'
  assert q['AP_sha256']==('11cd80055a7781eee61663dbc9ef0a8fff74fdeeeb9a6c3a59b8a7de379ac95c' if frozen else ap)
  wanted=q['option_row']=='0x635' if frozen else q['menu_mid']=='0x635'
  assert q['private_factory'] is wanted and q['stock_delegate'] is (not wanted)
  assert q['actual_accessor']==('0x28a87e8' if frozen else '0x28a8720')
 sync=receipts['sync_tests/sync_inheritance426_verified.json']
 assert sync['all_import_sources_unchanged_from_final425'] and sync['all_importer_code_constants_BSS_addresses_exact']
 assert sync['grid_lifecycle422_preserved_by_frozen_CP_identity'] and sync['reference_AP_sha256']=='11cd80055a7781eee61663dbc9ef0a8fff74fdeeeb9a6c3a59b8a7de379ac95c'
 for row in sync['sources']:assert sha(HERE/'import'/row['name'])==row['sha256']

 lifecycle=receipts['menu_research/native_lifecycle429_verified.json']
 assert len(lifecycle['cases'])==2
 assert {r['bias'] for r in lifecycle['cases']}=={'0x0','0x40000000'}
 for row in lifecycle['cases']:
  assert row['compiled_custom_gates'] and row['full_native_controller_ctor'] and row['full_native_dtor']
  assert row['first_view_update_argument']=='0x0' and row['native_query_preserves_layout']
  assert row['native_query_full_widget_loop_count']==34
  assert row['native_original_layout_and_param9_not_reached'] and row['each_object_cleaned_once_per_lifetime']
  assert row['static_objects_reused'] and row['no_OSAL_allocation_or_free']
  assert row['mid_change_and_closing_inputs_isolated']
  assert [(r['target'],r['kind'])for r in row['native_manager_layouts']]==[(1,'recreate'),(2,'same_class'),(0,'recreate')]
  assert len(row['real_helpers'])==2
 # Detailed allocator invariants are checked by its producer; the current AP
 # and immutable source binding are checked here and independently at delivery.
 allocator=receipts['menu_research/native_allocator429_verified.json']
 assert allocator['native_allocator_executed'] and allocator['native_create_executed']
 assert allocator['first_update_mode_zero_executed']
 assert len(allocator['cases'])==4 and all(r['passed'] and 0<r['arena_used']<45184 and r['native_capacity_assert_executed'] for r in allocator['cases'])
 review=receipts['menu_research/review429_verified.json'];assert len(review['cases'])==4
 for row in review['cases']:
  if row['mode']=='reserved_pool':
   for field in ('factories_return_nonzero_reserved_objects','native_controller_factory_wrapper_executed',
                 'native_manager_factory_return_dereference_executed','native_presenter_factory_wrapper_executed',
                 'parent_bytes_preserved','destructor_variants_cleanup_once',
                 'reentry_reuses_reserved_objects','no_OSAL_allocation_or_free'):
    assert row[field],field

 delta=receipts['production_delta429.json'];assert delta['changed_production_sources']==['menu_research/r5_filter_page425.c'] and delta['importer_production_sources_exact']
 names=receipts['menu_research/name_input429_verified.json'];assert len(names['cases'])==2
 assert names['stock_text_exact428_except_equivalent635_resolver'] and names['original_D9_styles_unchanged']
 for row in names['cases']:
  assert row['repeated_and_held_keys'] and row['sparse_slots'] and row['adjustment_widgets_absent']
  assert row['no_original_input_dispatch_or_setter'] and row['no_update_entry_or_reload'] and row['stale_inputs_consumed']
  assert {r['number']for r in row['names']}==set(range(13))
 worker=receipts['sync_tests/worker425_verified.json'];assert worker['cases']==11
 for name,digest in worker['source_sha256'].items():assert sha(ROOT/name)==digest,name
 for name in ('sync_tests/exact_request_bias0.json','sync_tests/exact_request_bias40000000.json'):
  q=receipts[name];assert q['total']==38 and q['source_sha256']==ap
 wrappers=receipts['sync_tests/refresh_wrapper425_verified.json'];assert wrappers['cases']==10
 thread=receipts['sync_tests/thread_ownership425_verified.json'];assert thread['UI']['thread_id']==3 and thread['E4']['thread_id']==4
 cross=receipts['crosscore/ap_cp425.json'];assert cross['actual_selects']==28 and cross['native_refreshes']==28 and cross['actual_AP_sender_inbound_and_CP_receive_task_executed']
 inherited=receipts['inherited425.json'];assert inherited['CP_exactly_frozen423'] and inherited['grid_lifecycle_422_preserved'] and inherited['BIN_v4_codec_unchanged']
 sd=receipts['sync_tests/sd425_final_binding.json'];assert sd['passed'] and sd['execution_inherited_by_exact_implementation_identity'] and sd['replay_cases']==162
 assert sd['all_importer_module_sections_exact'] and not sd['final_AP_executed_by_this_SD_replay']
 assert sha(ROOT/sd['receipt'])==sd['receipt_sha256'] and sha(ROOT/sd['reference_AP'])==sd['reference_AP_sha256']
 inputs=[]
 for p in HERE.rglob('*'):
  if p.is_file() and p.suffix in ('.py','.c','.h','.S','.json','.md') and '__pycache__' not in p.parts and 'release_tests' not in p.parts:
   inputs.append(bound(p))
 inputs += [bound(HERE/'ap/appFw.so'),bound(HERE/'ap/nflasha15'),bound(HERE/'import/runtime_rx.bin'),bound(HERE/'sync_tests/reference_ap448.so')]
 required=[str((HERE/n).relative_to(ROOT)) for n in REQUIRED_RECEIPTS]
 checks={k:True for k in REQUIRED_CHECKS}
 report=dict(passed=True,version='4.29',AP_sha256=ap,AP_partition_sha256=sha(HERE/'ap/nflasha15'),CP_sha256=inherited['CP_sha256'],required_checks=checks,required_receipts=required,receipts=[bound(HERE/n)for n in REQUIRED_RECEIPTS],inputs=inputs,camera_io=False,device_acceptance_tested=False,limitations=['Real native MID/ROW getters, menu-open routing, create_screen dispatch/map initialization and custom text bridge run offline. Lowest-level widget allocation and UX drawing remain fixtures; physical font/LCD geometry/occlusion, transparency and GUI event timing await camera acceptance.','Synchronous completion means exact CP selected state, exact native E4 execute return, a later exact CP ACK, durable sidecar and actual parent value resource verification; no LCD/ISP frame completion witness.','UI wait yields up to20 seconds. An overlong native Fsys call may exceed deadlines; page keeps the exact pending transaction and a later UI event resolves it.','Failed commit keeps the page; best-effort rollback may fail. No hardware rollback guarantee.','OSAL same-destination FIFO and downstream native parameter application completion are not independently established.','CP grid/parameter consumers inherited exactly from frozen4.23 with4.22 lifecycle.'])
 out=HERE/'release_tests/final_gate.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(passed=True,AP_sha256=ap,receipts=len(required),inputs=len(inputs))))
if __name__=='__main__':main()
