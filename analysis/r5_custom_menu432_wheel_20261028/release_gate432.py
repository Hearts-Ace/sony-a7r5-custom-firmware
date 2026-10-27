"""Strict offline acceptance gate for actual 4.32 inputs; no device I/O."""
from pathlib import Path
import hashlib,io,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from package432 import REQUIRED_RECEIPTS,REQUIRED_CHECKS
from elftools.elf.elffile import ELFFile

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
 assert build['version']==audit['version']=='4.32'
 for name,digest in audit['sources'].items():assert sha(ROOT/name)==digest,name
 receipts={n:read(HERE/n) for n in REQUIRED_RECEIPTS}
 for n,q in receipts.items():assert q['passed'] and q['AP_sha256']==ap,n
 main=receipts['main_menu425_replay.json'];assert len(main['rows'])==6
 for row in main['rows']:
  assert row['old_alias_keys_checked']==1589
  if row['label']=='candidate425':
   assert len(row['views'])==4 and all(v['produced_mid_present']==1 for v in row['views'])
 assert receipts['title_native_verification425.json']['cases']==16
 page=receipts['menu_research/page425_replay.json']
 interaction=receipts['menu_research/interaction431_verified.json']
 assert page==interaction
 modes={'move_confirm','held_sparse','touch_stays','true_failure','pending_recovery',
        'parent_projection_retry','stale_sequence','back_after_failure','empty_confirm',
        'removed_update','navigation_boundary','stock','reenter','oom','layout'}
 assert len(interaction['cases'])==30
 assert {(r['bias'],r['mode']) for r in interaction['cases']}=={(b,m) for b in ('0x0','0x40000000') for m in modes}
 for field in ('movement_applies_and_saves','successful_movement_keeps_page','confirm_no_duplicate_request',
               'parent_error_distinct','true_apply_failure_retains_page','exact_pending_sequence'):
  assert interaction[field],field
 for row in page['cases']:
  if row['mode']=='stock':assert row['stock_factory_delegated'];continue
  assert row['created_widgets']==[[0,106],[1,107],[9,28],[11,2],[12,2],[13,2]]+[[i,20]for i in range(22,27)]
  assert row['background2_not_constructed'] and row['native_adjustment_widgets_absent']
  assert row['menu_mid']=='0x635' and row['independent_row_pid']=='0x1607'
  assert row['update_widgets_not_constructed'] and row['no_reload_requests']
 wheel=read(HERE/'menu_research/wheel432_verified.json')
 assert wheel['passed'] and wheel['version']=='4.32' and wheel['AP_sha256']==ap
 for field in ('wheel_updates_focus_and_preview','same_request_path','no_original_look_setter','batched_steps_verified'):
     assert wheel[field],field
 assert wheel['batch_contract']=='Repeated native wheel events each advance one available item, clamped at boundaries. No unverified message count is interpreted.'
 assert len(wheel['cases'])==26 and len(wheel['baseline431'])==8
 regular='bidirectional_burst_boundary_mixed_closing'
 current_rows=[row for row in wheel['cases'] if row['mode']==regular]
 assert len(current_rows)==16
 assert {(row['bias'],row['layout'],row['mask']) for row in current_rows}=={(bias,layout,hex(mask)) for bias in ('0x0','0x40000000') for layout in (0,1) for mask in (4095,258,0,2048)}
 for row in current_rows:
     available=[0]+[i for i in range(1,13)if int(row['mask'],16)&(1<<(i-1))]
     count=len(available)
     forward=[available[min(i+1,count-1)] for i in range(count+3)]
     backward=[available[max(count-2-i,0)] for i in range(count+3)]
     assert [state['selected'] for state in row['states']]==forward+backward
     for state in row['states']:
         assert state['native_list_focus']==available.index(state['selected'])
         assert int(state['full_name_resource'],16)==0x02ff4400+state['selected']
     assert row['private_requests']==(2*count if count>1 else 1)
     assert row['no_original_look_setter']
 remaining=[row for row in wheel['cases'] if row['mode']!=regular]
 assert len(remaining)==10
 assert {(row['bias'],row['mode']) for row in remaining}=={(bias,mode) for bias in ('0x0','0x40000000') for mode in ('pending','failure','stale_serial','wrong_mid','stock')}
 for row in remaining:
     assert row['selected']==(2 if row['mode']=='pending' else 0)
     assert row['no_original_look_setter'] is (row['mode']!='stock')
 assert {(row['bias'],row['event']) for row in wheel['baseline431']}=={(bias,hex(event)) for bias in ('0x0','0x40000000') for event in (0x2050000,0x2050001,0x2050004,0x2050005)}
 for row in wheel['baseline431']:
     assert row['private_projection_unchanged'] and '0x1a6d8cc' in row['native_escape']
 assert sha(ROOT/'analysis/r5_custom_menu431_interaction_20261027/ap/appFw.so')=='3c832336b73fc5d8b5a902faebd07249821888a17d3609831def42d4419ba941'
 wheel_contract=read(HERE/'wheel_evidence/native_wheel432.json')
 assert wheel_contract['passed'] and wheel_contract['original_sha256']=='a8d5cd444bf08a03a70aedc3cc32bdd857b89b468ac10bf8365d640e8d390d75'
 assert wheel_contract['dispatcher']=='0x1a6d8cc' and wheel_contract['cases_count']==len(wheel_contract['cases'])==36
 assert [row['event'] for row in wheel_contract['native_contract']]==[hex(0x2050000+i)for i in range(6)]
 assert [row['index']for row in wheel_contract['native_contract']]==list(range(16,22))
 assert [row['handler']for row in wheel_contract['native_contract']]==['0x22083b4','0x22083d0','0x2207dd4','0x2207e98','0x1a62ebc','0x1a62e8c']
 assert all(row['adjust']==0 for row in wheel_contract['native_contract'])
 normalization=wheel_contract['normalization_tables']
 assert [(row['prefix'],row['entries'])for row in normalization]==[('0x1000000',890),('0x4000000',850)]
 assert all(row['wheel_matches']==[] for row in normalization)
 semantics=wheel_contract['message_count_semantics']
 assert semantics['message_step_count_read'] is False and semantics['message_direction_read'] is False
 assert semantics['physical_detents_or_acceleration_observed'] is False
 messages=('0x0','0x30001000','0xdeadbee000')
 expected_contract={(bias,'dispatch',hex(event),'unmapped')for bias in ('0x0','0x40000000')for event in range(0x2050000,0x2050006)}
 expected_contract|={(bias,'fixed_step',hex(event),message)for bias in ('0x0','0x40000000')for event in (0x2050000,0x2050001)for message in messages}
 expected_contract|={(bias,'repost',hex(event),message)for bias in ('0x0','0x40000000')for event in (0x2050004,0x2050005)for message in messages}
 assert {(row['bias'],row['kind'],row['event'],row['message'])for row in wheel_contract['cases']}==expected_contract
 for row in wheel_contract['cases']:
     if row['kind']=='fixed_step':
         assert row['signed_step']==(1 if row['event']=='0x2050000' else -1)
         assert row['handler_message_not_dereferenced']
         assert row['result']['w1']==(1 if row['signed_step']==1 else 0xffffffff)
     elif row['kind']=='repost':
         result=row['result']
         assert result['x0']==row['message'] and result['w2']==2 and result['w3']==0xd9
         assert result['w1']==(0x2050000 if row['event']=='0x2050004' else 0x2050001)
 style=read(HERE/'style_evidence/native_list431.json')
 assert style['passed'] and style['original_sha256']=='a8d5cd444bf08a03a70aedc3cc32bdd857b89b468ac10bf8365d640e8d390d75'
 assert sha(ROOT/'assets/firmware/a8d5cd444bf0-appFw.so')==style['original_sha256']
 assert style['executed_entry']=='0x1892068' and len(style['cases'])==48
 assert {(r['bias'],r['mode'],r['focus']) for r in style['cases']}=={(b,m,f) for b in ('0x0','0x40000000') for m in range(4) for f in (0,1,3,6,9,12)}
 for row in style['cases']:
  active=[r for r in row['rows'] if r['active']]
  assert len(active)==1 and active[0]['logical']==row['focus']
  assert int(active[0]['resource'],16)==0x02ff4300+row['focus']
 pool=style['pool_static_evidence']
 assert (pool['initializer'],pool['pointer_table'],pool['view_constructor'],pool['native_create'])==('0x182ae14','0x74c0470','0x182ad30','0x182b41c')
 assert (pool['arena_pointer_field'],pool['arena_capacity_field'],pool['arena_used_field'])==('0x3e98','0x3ea0','0x3ea4')
 assert [r['capacity'] for r in pool['pools']]==[0x600000,0x400000,0x400000,0x40000,0x20000,0x20000]
 assert [r['index'] for r in pool['pools']]==list(range(6))
 ap_bytes=(HERE/'ap/appFw.so').read_bytes();elf=ELFFile(io.BytesIO(ap_bytes))
 for row in pool['pools']:
  va=int(row['capacity_instruction'],16)
  segment=next(seg for seg in elf.iter_segments()if seg['p_type']=='PT_LOAD' and seg['p_vaddr']<=va<seg['p_vaddr']+seg['p_filesz'])
  offset=segment['p_offset']+va-segment['p_vaddr']
  assert ap_bytes[offset:offset+4].hex()==row['capacity_instruction_bytes']
 highlight=receipts['style_evidence/native_list431_verified.json']
 assert highlight['original_sha256']==style['original_sha256'] and highlight['compiled_projection']
 assert highlight['native_row_generation']=='0x1892068' and highlight['native_scroll_configuration']=='0x1892414'
 assert len(highlight['cases'])==76
 combos=set()
 for row in highlight['cases']:
  combos.add((row['bias'],row['layout'],row['mask'],row['selected']))
  available=[0]+[i for i in range(1,13)if int(row['mask'],16)&(1<<(i-1))]
  assert row['available']==available and row['absolute_focus']==available.index(row['selected'])
  assert row['native_highlight_count']==1 and row['mode']==0
  assert row['native_scroll_stride']==66.0 and row['native_scroll_focus']==[row['absolute_focus']]*2
  for key in ('compiled_projection_executed','native_generation_executed','no_prefix_in_short_text','no_touch_exit'):
   assert row[key],key
 assert combos=={(b,l,hex(m),n) for b in ('0x0','0x40000000') for l in (0,1) for m in (4095,258,0,2048) for n in [0]+[i for i in range(1,13)if m&(1<<(i-1))]}
 parent=receipts['parent_evidence/parent431_verified.json']
 assert parent['cases']==6 and parent['native_values_checked']==78
 assert parent['event_end_update_call']['address']=='0x1ec7428' and parent['event_end_update_call']['target']=='0x1e97ef8'
 assert parent['event_end_update_call']['evidence']=='static'
 assert {(r['bias'],r['lower_screen']) for r in parent['rows']}=={(b,screen) for b in ('0x0','0x40000000') for screen in ('0x2ec','0x32d','0x315')}
 for row in parent['rows']:
  assert row['view_pools']==[dict(screen_id='0xd9',native_view_pool_index=0),dict(screen_id='0x2d7',native_view_pool_index=0),dict(screen_id='0x2ed',native_view_pool_index=1)]
  assert row['native_values']==list(range(0x02ff4300,0x02ff4300+13))
  for key in ('old_parent_destroyed','fresh_parent_from_pop','native_end_of_event_refresh','old_list_unchanged','safe_preclose_resolver'):
   assert row[key],key
 nativeview=receipts['menu_research/native_view426_verified.json']
 assert nativeview['native_create_entry']=='0x182b41c' and nativeview['native_create_vtable_slot']=='0x57830a8'
 assert len(nativeview['cases'])==4
 assert {(q['bias'],q['layout']) for q in nativeview['cases']}=={(b,l) for b in ('0x0','0x40000000') for l in (0,1)}
 allowed_widgets=[[0,106],[1,107],[9,28],[11,2],[12,2],[13,2]]+[[i,20]for i in range(22,27)]
 for q in nativeview['cases']:
  assert q['actual_constructed_widgets']==allowed_widgets
  assert q['update_resource']=='0x0' and q['update_visible_param'] is False and q['update_widgets_absent'] and q['full_text_bridge']=='关闭'
  assert q['right_adjustment_widgets_absent'] and q['native_create_executed'] and q['compiled_project_accepted_native_param_map']
  dispatch=q['native_dispatch_entries'];assert len(dispatch)==34 and {x['index'] for x in dispatch}==set(range(34))
  actual=[[x['index'],x['type']]for x in dispatch if not x['parameter_only']]
  assert actual==q['actual_constructed_widgets']==allowed_widgets
  assert [x for x in dispatch if x['index']==14][0]['parameter_only']
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
 assert len(allocator['cases'])==8
 assert {(r['bias'],r['layout'],r['arena_capacity'])for r in allocator['cases']}=={(b,l,c)for b in ('0x0','0x40000000')for l in (0,1)for c in (0x600000,0x20000)}
 for row in allocator['cases']:
  assert row['passed'] and row['native_capacity_assert_executed'] and 0<row['arena_used']<row['arena_capacity']
  assert row['native_list'] is (row['arena_capacity']>=0xb0000)
  if row['native_list']:assert 600000<row['arena_used']<0xb0000
  else:assert row['arena_used']<45184

 review=receipts['menu_research/review429_verified.json'];assert len(review['cases'])==4
 for row in review['cases']:
  if row['mode']=='reserved_pool':
   for field in ('factories_return_nonzero_reserved_objects','native_controller_factory_wrapper_executed',
                 'native_manager_factory_return_dereference_executed','native_presenter_factory_wrapper_executed',
                 'parent_bytes_preserved','destructor_variants_cleanup_once',
                 'reentry_reuses_reserved_objects','no_OSAL_allocation_or_free'):
    assert row[field],field

 delta=receipts['delta432_verified.json'];assert delta['nonpage_production_sources_exact431']
 assert delta['startup_production_sources_exact430'] and delta['actual_final_AP_SD_cases']==180
 assert delta['same_boot_bank_retry'] and delta['full_content_deduplication'] and delta['ready_slot_not_blocked_by_other_slot']
 names=receipts['menu_research/name_input429_verified.json'];assert len(names['cases'])==2
 assert names['stock_text_exact428_except_declared_module_hooks'] and names['original_D9_styles_unchanged']
 for row in names['cases']:
  assert row['repeated_and_held_keys'] and row['sparse_slots'] and row['adjustment_widgets_absent']
  assert row['no_original_input_dispatch_or_setter'] and row['no_update_entry_or_reload'] and row['stale_inputs_consumed']
  assert {r['number']for r in row['names']}==set(range(13))
 worker=receipts['sync_tests/worker425_verified.json'];assert worker['cases']==15
 for name,digest in worker['source_sha256'].items():assert sha(ROOT/name)==digest,name
 for name in ('sync_tests/exact_request_bias0.json','sync_tests/exact_request_bias40000000.json'):
  q=receipts[name];assert q['total']==38 and q['source_sha256']==ap
 wrappers=receipts['sync_tests/refresh_wrapper425_verified.json'];assert wrappers['cases']==10
 thread=receipts['sync_tests/thread_ownership425_verified.json'];assert thread['UI']['thread_id']==3 and thread['E4']['thread_id']==4
 cross=receipts['crosscore/ap_cp425.json'];assert cross['actual_selects']==30 and cross['native_refreshes']==30 and cross['actual_AP_sender_inbound_and_CP_receive_task_executed']
 inherited=receipts['inherited425.json'];assert inherited['CP_exactly_frozen423'] and inherited['grid_lifecycle_422_preserved'] and inherited['BIN_v4_codec_unchanged']
 sd=receipts['sync_tests/sd430_replay.json'];assert sd['passed'] and sd['AP_sha256']==ap and sd['cases']==180
 assert sd['manual_reload_production_wrapper_executed'] and sd['current_set_digest_boundary_checked']
 grid=receipts['sync_tests/grid430_verified.json'];assert len(grid['cases'])==7
 inputs=[]
 for p in HERE.rglob('*'):
  if p.is_file() and p.suffix in ('.py','.c','.h','.S','.json','.md') and '__pycache__' not in p.parts and 'release_tests' not in p.parts:
   inputs.append(bound(p))
 inputs += [bound(HERE/'ap/appFw.so'),bound(HERE/'ap/nflasha15'),bound(HERE/'import/runtime_rx.bin')]
 # Native parent replay uses frozen VM fixture utilities; bind those dynamic
 # Python imports explicitly alongside the actual current candidate.
 inputs += [bound(ROOT/name) for name in (
  'analysis/r5_custom_menu430_startup_20261027/menu_research/replay_page425.py',
  'analysis/r5_custom_menu430_startup_20261027/replay_main_menu425.py',
  'analysis/r5_custom_menu430_startup_20261027/menu_research/read_menu.py',
  'analysis/r5_custom_filter423_20261023/import/module_audit.json',
  'analysis/r5_custom_filter423_20261023/ap/appFw.so',
  'analysis/r5_custom_menu431_interaction_20261027/ap/appFw.so',
  'analysis/r5_custom_menu431_interaction_20261027/import/module_audit.json')]
 inputs += [bound(HERE/'wheel_evidence/native_wheel_disassembly.txt')]
 required=[str((HERE/n).relative_to(ROOT)) for n in REQUIRED_RECEIPTS]
 checks={k:True for k in REQUIRED_CHECKS}
 report=dict(passed=True,version='4.32',AP_sha256=ap,AP_partition_sha256=sha(HERE/'ap/nflasha15'),CP_sha256=inherited['CP_sha256'],required_checks=checks,required_receipts=required,receipts=[bound(HERE/n)for n in REQUIRED_RECEIPTS],inputs=inputs,camera_io=False,device_acceptance_tested=False,limitations=['Real native MID/ROW getters, menu-open routing, create_screen dispatch/map initialization and custom text bridge run offline. Lowest-level widget allocation and UX drawing remain fixtures; physical font/LCD geometry/occlusion, transparency and GUI event timing await camera acceptance.','Movement applies and durably saves on the worker, retaining the page; confirm/back verifies the committed descriptor through the original resource resolver, then native pop reconstructs and updates the parent. It never dereferences the destroyed parent presenter. CP ACK/E4 execution and the resolver are control-plane witnesses, without LCD/ISP frame completion evidence.','UI wait yields up to20 seconds. An overlong native Fsys call may exceed deadlines; page keeps the exact pending transaction and a later UI event resolves it.','Failed commit keeps the page; parent display refresh failures use a separate status. Best-effort rollback may fail; no hardware rollback guarantee.','OSAL same-destination FIFO and downstream native parameter application completion are not independently established.','CP grid/parameter consumers inherited exactly from frozen4.23 with4.22 lifecycle.', 'Wheel burst checks replay individual canonical native events; each event means one step. No hardware detent rate, payload step-count protocol or physical preview frame is inferred.'])
 out=HERE/'release_tests/final_gate.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(passed=True,AP_sha256=ap,receipts=len(required),inputs=len(inputs))))
if __name__=='__main__':main()
