"""Strict offline acceptance gate for actual 4.28 inputs; no device I/O."""
from pathlib import Path
import hashlib,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from package428 import REQUIRED_RECEIPTS,REQUIRED_CHECKS

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
 assert build['rx_bytes']<=65536 and audit['bss_bytes']<=131072
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
  if row['mode'] in ('success','touch','timeout','reenter','reload','reload_timeout'):
   assert names.count('pop')==1 and names.index('parent_value_before_pop')<names.index('pop')
  if row['mode'] in ('failure','parent_bad','reload_failure','reload_parent_bad'):assert 'pop' not in names
  if row['mode']!='stock':
   assert row['background2_not_constructed'] and row['update_widgets_not_constructed']
   assert row['update_text_and_touch_hidden'] and row['no_reload_requests']
 worker=receipts['sync_tests/worker425_verified.json'];assert worker['cases']==11
 for name,digest in worker['source_sha256'].items():assert sha(ROOT/name)==digest,name
 for name in ('sync_tests/exact_request_bias0.json','sync_tests/exact_request_bias40000000.json'):
  q=receipts[name];assert q['total']==38 and q['source_sha256']==ap
 wrappers=receipts['sync_tests/refresh_wrapper425_verified.json'];assert wrappers['cases']==10
 thread=receipts['sync_tests/thread_ownership425_verified.json'];assert thread['UI']['thread_id']==3 and thread['E4']['thread_id']==4
 cross=receipts['crosscore/ap_cp425.json'];assert cross['actual_selects']==28 and cross['native_refreshes']==28 and cross['actual_AP_sender_inbound_and_CP_receive_task_executed']
 inherited=receipts['inherited425.json'];assert inherited['CP_exactly_frozen423'] and inherited['grid_lifecycle_422_preserved'] and inherited['BIN_v4_codec_unchanged']
 sd=receipts['sync_tests/sd425_final_binding.json'];assert sd['passed']
 rollback=receipts['rollback428_verified.json']
 for field in ('exact425_reproduced_before_changes','no426_427_menu_changes',
               'manual_update_text_touch_focus_and_submit_removed',
               'page_object_has_no_reload_dependency','automatic_import_and_worker_unchanged'):
  assert rollback[field],field
 assert rollback['baseline425_sha256']=='11cd80055a7781eee61663dbc9ef0a8fff74fdeeeb9a6c3a59b8a7de379ac95c'
 assert rollback['production_source_changes']==['menu_research/r5_filter_page425.c']
 for row in rollback['inherited_production_sources']:assert sha(ROOT/row['path'])==row['sha256']
 sync=receipts['sync_tests/sync_inheritance428_verified.json']
 assert sync['all_import_sources_unchanged_from_final425'] and sync['all_importer_code_constants_BSS_addresses_exact']
 assert sync['grid_lifecycle422_preserved_by_frozen_CP_identity']
 inputs=[]
 for p in HERE.rglob('*'):
  if p.is_file() and p.suffix in ('.py','.c','.h','.S','.json','.md') and '__pycache__' not in p.parts and 'release_tests' not in p.parts:
   inputs.append(bound(p))
 inputs += [bound(HERE/'ap/appFw.so'),bound(HERE/'ap/nflasha15'),bound(HERE/'import/runtime_rx.bin'),bound(HERE/'sync_tests/reference_ap448.so')]
 required=[str((HERE/n).relative_to(ROOT)) for n in REQUIRED_RECEIPTS]
 checks={k:True for k in REQUIRED_CHECKS}
 report=dict(passed=True,version='4.28',AP_sha256=ap,AP_partition_sha256=sha(HERE/'ap/nflasha15'),CP_sha256=inherited['CP_sha256'],required_checks=checks,required_receipts=required,receipts=[bound(HERE/n)for n in REQUIRED_RECEIPTS],inputs=inputs,camera_io=False,device_acceptance_tested=False,limitations=['M4-style Background2 exclusion and all UI rendering validated by native data/CPU replays only; physical transparency, fonts and full GUI scheduling await camera acceptance.','Synchronous completion means exact CP selected state, exact native E4 execute return, a later exact CP ACK, durable sidecar and actual parent value resource verification; no LCD/ISP frame completion witness.','UI wait yields up to20 seconds. An overlong native Fsys call may exceed deadlines; page keeps the exact pending transaction and a later UI event resolves it.','Failed commit keeps the page; best-effort rollback may fail. No hardware rollback guarantee.','OSAL same-destination FIFO and downstream native parameter application completion are not independently established.','CP grid/parameter consumers inherited exactly from frozen4.23 with4.22 lifecycle.'])
 out=HERE/'release_tests/final_gate.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(passed=True,AP_sha256=ap,receipts=len(required),inputs=len(inputs))))
if __name__=='__main__':main()
