"""Native restoration cache replay. Only synthetic CPU RAM/MMIO.

The reference executes the unmodified native builder body through its original
prologue. Fixtures supply runtime raw bytes explicitly; they are not camera RAM.
"""
from replay_handoff422 import *

RROOT=A+0x1000;RSTATE=A+0x2000;RSOURCE=A+0x9000
class Reference:
 def __init__(self,raw):
  self.e=Harness(CP421.read_bytes(),raw,'native-reference');self.maximum_stack=0
 def packed(self,kind,transform,level,source,root3=0):
  e=self.e;u=e.u;ctx=A+0x3000;env=A+0x4000;out=A+0x5000;work=A+0x6000;meta=A+0x8000;target=work+0x5c
  u.mem_write(RROOT,bytes(64));u.mem_write(RSTATE,bytes(0x200));u.mem_write(env,bytes(16));u.mem_write(meta,bytes(16))
  w(u,ctx,RROOT,env);w(u,out+8,RSTATE,work,meta)
  u.mem_write(RROOT+3,bytes([root3]));u.mem_write(RROOT+0x2f,bytes([level]));u.mem_write(env+6,b'\x01');u.mem_write(meta+11,b'\x03')
  w(u,RSTATE+0x184,RSOURCE if source is not None else 0);u.mem_write(RSTATE+0x188,bytes([kind,transform]))
  if source is not None:u.mem_write(RSOURCE,source)
  u.mem_write(target-16,b'\xa5'*16);u.mem_write(target+1620,b'\x5a'*16)
  trampoline=A+0x70000;u.mem_write(trampoline,bytes.fromhex('f0b503afdff800f0')+struct.pack('<I',0x231659))
  e.track_stack=True;e.minimum_sp=SP;e.call(trampoline,ctx,out);e.track_stack=False
  self.maximum_stack=max(self.maximum_stack,SP-e.minimum_sp)
  assert bytes(u.mem_read(target-16,16))==b'\xa5'*16 and bytes(u.mem_read(target+1620,16))==b'\x5a'*16
  if source is not None:assert bytes(u.mem_read(RSOURCE,len(source)))==source
  return bytes(u.mem_read(target,1620))

def setup(cp,raw,symbols):return Harness(cp,raw,'restore-cache',symbols)
def entry(e,i,at=B):return at+RESTORE_FIRST+i*RESTORE_ENTRY
def immutable(e,at=B):return {i:bytes(e.u.mem_read(entry(e,i,at),RESTORE_ENTRY)) for i in range(32) if r32(e.u,entry(e,i,at))==2}
def assert_immutable(e,before,at=B):
 for i,value in before.items():assert bytes(e.u.mem_read(entry(e,i,at),RESTORE_ENTRY))==value,(i,'published entry mutated')
def restore(e,kind=1,transform=0,level=8,source=NATIVE_RAW,source_at=RSOURCE,special=0,generation=B):
 u=e.u;u.mem_write(RROOT,bytes(64));u.mem_write(RSTATE,bytes(0x200));u.mem_write(RROOT+0x2f,bytes([level]));u.mem_write(RROOT+0x36,bytes([special]))
 w(u,RSTATE+0x184,source_at if source is not None else 0);u.mem_write(RSTATE+0x188,bytes([kind,transform]))
 if source is not None:u.mem_write(source_at,source)
 root_before=bytes(u.mem_read(RROOT,64));state_before=bytes(u.mem_read(RSTATE,0x200));before=immutable(e,generation)
 e.track_stack=True;e.minimum_sp=SP;e.call(e.symbols['r5_grid422_restore'],generation,RROOT,RSTATE);e.track_stack=False
 ptr=u.reg_read(UC_ARM_REG_R0);e.maximum_restore_stack=max(getattr(e,'maximum_restore_stack',0),SP-e.minimum_sp)
 assert bytes(u.mem_read(RROOT,64))==root_before and bytes(u.mem_read(RSTATE,0x200))==state_before
 if source is not None:assert bytes(u.mem_read(source_at,len(source)))==source
 assert_immutable(e,before,generation)
 for at,guard in e.prepared_guards:assert bytes(u.mem_read(at,len(guard)))==guard
 if ptr:
  assert generation+RESTORE_FIRST+RESTORE_PACKED<=ptr<generation+ALLOCATION and (ptr-generation-RESTORE_FIRST-RESTORE_PACKED)%RESTORE_ENTRY==0
  assert r32(u,ptr-RESTORE_PACKED)==2
 return ptr

def main():
 p=argparse.ArgumentParser();p.add_argument('--cp',type=Path,default=HERE/'cp/cp420-grid.NONINSTALLABLE.bin');p.add_argument('--output',type=Path);a=p.parse_args()
 binding_before=execution_sources(__file__,a.cp,a.cp.with_name('build.json'))
 cp=a.cp.read_bytes();build=json.loads(a.cp.with_name('build.json').read_text());assert build['candidate_sha256']==sha(cp);symbols={k:int(v,16)for k,v in build['symbols'].items()}
 raw=(ROOT/'exports/fl2_fl3_grid_compare_20261023/R5NATIVE.BIN').read_bytes();reference=Reference(raw);rows=[];max_stack=0
 def add(suite,**values):rows.append(dict(suite=suite,**values))
 # Each kind/transform gets an independent cache. Values>=8 deduplicate to8.
 # level0 is independently keyed: kind0/transform0 nonnull uses different math.
 for kind,transform in itertools.product((0,1,2),(0,1,2)):
  e=setup(cp,raw,symbols);source=NATIVE_RAW if kind==1 else NATIVE_RAW[:162];full_pointer=None
  for level in (0,1,2,3,4,5,6,7,8,15,255):
   ptr=restore(e,kind,transform,level,source);expected=reference.packed(kind,transform,level,source);got=bytes(e.u.mem_read(ptr,1620));assert got==expected,(kind,transform,level)
   if level in (8,15,255):
    if full_pointer is None:full_pointer=ptr
    assert ptr==full_pointer
   add('native_matrix',kind=kind,transform=transform,level=level,pointer=hex(ptr),packed_sha256=sha(got),native_byte_exact=True)
  assert r32(e.u,B+RESTORE_HEADER)==9
  max_stack=max(max_stack,e.maximum_restore_stack)
 e=setup(cp,raw,symbols)
 for kind,transform,level in itertools.product((0,1,2),(0,1,2),(1,8,255)):
  ptr=restore(e,kind,transform,level,None);expected=reference.packed(kind,transform,level,None);got=bytes(e.u.mem_read(ptr,1620));assert got==expected
  if kind==1 and transform==1:assert any(got),'null transform1 was incorrectly treated as zero/absent'
  add('null_source',kind=kind,transform=transform,level=level,pointer=hex(ptr),packed_sha256=sha(got),native_byte_exact=True,packed_nonzero=any(got))
 # Source address is not part of identity; presence, kind, transform, level,
 # and exact captured bytes are. Only a READY entry can be shared.
 e=setup(cp,raw,symbols);first=restore(e);saved=immutable(e);same=restore(e,source_at=RSOURCE+0x1000);assert first==same
 changed=bytes([NATIVE_RAW[0]^1])+NATIVE_RAW[1:];other=restore(e,source=changed);assert other!=first;assert_immutable(e,saved)
 add('identity',same_bytes_other_address_deduplicate=True,changed_raw_new_entry=True,published_entries_immutable=True)
 e=setup(cp,raw,symbols);pending=entry(e,0);w(e.u,pending,1,0x1010008);e.u.mem_write(pending+8,NATIVE_RAW);e.u.mem_write(pending+RESTORE_PACKED,b'\xee'*1620);w(e.u,B+RESTORE_HEADER,1);before=bytes(e.u.mem_read(pending,RESTORE_ENTRY));ptr=restore(e);assert ptr!=pending+RESTORE_PACKED and bytes(e.u.mem_read(pending,RESTORE_ENTRY))==before
 assert bytes(e.u.mem_read(ptr,1620))==reference.packed(1,0,8,NATIVE_RAW)
 add('pending',building_entry_never_reused=True,building_bytes_unchanged=True,ready_exact_native=True)
 # Simulate physical contention. No scratch is available even if a READY hit
 # exists: the helper fails explicitly without reading unfinished entries.
 e=setup(cp,raw,symbols)
 for i in range(32):w(e.u,entry(e,i),1)
 ptr=restore(e);assert ptr==0 and r32(e.u,B+52252+12)==5 and r32(e.u,B+RESTORE_HEADER)==0
 add('all_building',pointer_zero=True,reason=5,no_unfinished_entry_used=True)
 # 31 sealed entries retain one scratch. A known hit is still serviceable;
 # the32nd distinct request fails and leaves all published data unchanged.
 e=setup(cp,raw,symbols);pointers=[];sources=[]
 for i in range(31):
  source=bytes([i])+NATIVE_RAW[1:];sources.append(source);ptr=restore(e,source=source);assert ptr and ptr not in pointers;pointers.append(ptr)
 assert r32(e.u,B+RESTORE_HEADER)==31
 before=immutable(e);assert len(before)==31
 for i in (0,15,30):assert restore(e,source=sources[i])==pointers[i]
 failed=restore(e,source=bytes([127])+NATIVE_RAW[1:]);assert failed==0 and r32(e.u,B+52252+12)==5 and r32(e.u,B+RESTORE_HEADER)==31
 assert_immutable(e,before);assert sum(r32(e.u,entry(e,i))==0 for i in range(32))==1
 add('capacity',committed=31,physical=32,scratch=1,known_hits_after_full=True,new_source_rejected=True,reason=5,all_published_entries_immutable=True)
 # Pause a real first helper while its entry is BUILDING, run a second helper
 # on a disjoint stack with changed source bytes, then resume the first CPU
 # context. Both results must equal their own captured source, neither may read
 # the other's unfinished packed area. This is controlled single-CPU interleave.
 e=setup(cp,raw,symbols);u=e.u;pause={'armed':True,'stopped':False}
 def pause_builder(c,pc,n,_):
  if pause['armed'] and pc==(symbols['r5_grid420_builder_original']&~1):pause['stopped']=True;c.emu_stop()
 hook=u.hook_add(UC_HOOK_CODE,pause_builder)
 u.mem_write(RROOT,bytes(64));u.mem_write(RROOT+0x2f,b'\x08');u.mem_write(RSTATE,bytes(0x200));w(u,RSTATE+0x184,RSOURCE);u.mem_write(RSTATE+0x188,b'\x01\x00');u.mem_write(RSOURCE,NATIVE_RAW)
 for reg,value in ((UC_ARM_REG_R0,B),(UC_ARM_REG_R1,RROOT),(UC_ARM_REG_R2,RSTATE),(UC_ARM_REG_SP,SP),(UC_ARM_REG_LR,STOP|1)):u.reg_write(reg,value)
 u.emu_start(symbols['r5_grid422_restore']|1,STOP,count=3000000);assert pause['stopped']
 saved_cpu=u.context_save();saved_stack=bytes(u.mem_read(SP-0x1000,0x1000));first_pending=entry(e,0);first_pending_raw=bytes(u.mem_read(first_pending+8,1215));assert first_pending_raw==NATIVE_RAW and r32(u,first_pending)==1
 pause['armed']=False
 changed=bytes((v^0x3f)for v in NATIVE_RAW);u.mem_write(RSOURCE,changed)
 # Move the helper call stack below the suspended one using a temporary stop
 # trampoline. Registers and every saved stack byte are restored afterwards.
 for reg,value in ((UC_ARM_REG_R0,B),(UC_ARM_REG_R1,RROOT),(UC_ARM_REG_R2,RSTATE),(UC_ARM_REG_SP,SP-0x4000),(UC_ARM_REG_LR,STOP|1)):u.reg_write(reg,value)
 u.emu_start(symbols['r5_grid422_restore']|1,STOP,count=3000000);second_ptr=u.reg_read(UC_ARM_REG_R0);assert second_ptr and second_ptr!=first_pending+RESTORE_PACKED
 second_bytes=bytes(u.mem_read(second_ptr,1620));assert second_bytes==reference.packed(1,0,8,changed)
 assert r32(u,first_pending)==1 and bytes(u.mem_read(first_pending+8,1215))==NATIVE_RAW
 u.mem_write(SP-0x1000,saved_stack);u.context_restore(saved_cpu);u.emu_start(u.reg_read(UC_ARM_REG_PC)|1,STOP,count=3000000);first_ptr=u.reg_read(UC_ARM_REG_R0)
 assert first_ptr==first_pending+RESTORE_PACKED and bytes(u.mem_read(first_ptr,1620))==reference.packed(1,0,8,NATIVE_RAW) and bytes(u.mem_read(second_ptr,1620))==second_bytes
 assert r32(u,B+RESTORE_HEADER)==2;u.hook_del(hook)
 add('interleaved_builders',first_snapshot_before_source_mutation=True,building_entry_skipped=True,two_private_entries=True,both_native_byte_exact=True,both_entries_immutable=True)
 # Check every retained entry across actual AA consumption, not only direct
 # helper calls. Deferred requests retain the captured packed pointer after a
 # new current generation and raw-source mutation.
 for copy in (False,True):
  e=setup(cp,raw,symbols);e.publish_fixture(B+0x80000,mask=0);r=e.frame(dict(look='FL2',copy=copy),consume=False);pointer=int(r['final']['state_bank'],16);old=bytes(e.u.mem_read(pointer,1620));saved=immutable(e,B+0x80000)
  e.publish_fixture(B+0x100000,mask=0);e.u.mem_write(0x198c1ca,bytes((v^0x55) for v in NATIVE_RAW));w(e.u,AA+0xb90,DEV0,DEV0,DEV1,DEV1)
  e.call(0xaac942,AA,COPY) if copy else e.call(0xaac708,AA)
  if copy:assert bytes(e.u.mem_read(COPY,1620))==old
  else:
   for mmio in (MMIO0,MMIO1):assert b''.join(bytes(e.u.mem_read(mmio+a,n))for a,n in model.CHUNKS)==old
  assert_immutable(e,saved,B+0x80000);add('deferred_old_request',copy=copy,new_global_ignored=True,raw_mutation_ignored=True,two_AA_lanes_native_bytes=True,whole_ready_entry_immutable=True)
 # Original legal routes may choose to disable; otherwise they must bind a
 # correct original table. Reuse the native cache across the transition to
 # expose missing generation identity, with kind/type and transform fixtures.
 routes={f'domain{domain}_direct{direct}_root1{root1}':dict(root1=root1,direct=direct,domain=domain)for domain,direct,root1 in itertools.product((6,8,11),(0,1),(0,1))}
 for j,(route,kind,transform,root3,preserve) in enumerate(itertools.product(routes,(1,2),(0,1),(0,1),(False,True))):
  copy=bool(j&1);mask=0 if j&2 else 0x80;e=setup(cp,raw,symbols);e.frame(dict(look='FL2',copy=copy,**routes[route]));e.publish_fixture(B+0x80000,mask=mask)
  source=NATIVE_RAW if kind==1 else NATIVE_RAW[:162];expected=reference.packed(kind,transform,8,source)
  r=e.frame(dict(look='FL2',copy=copy,root3=root3,preserve_native_cache=preserve,native_metadata=dict(kind=kind,transform=transform),suite='old_route_native_restoration',**routes[route]))
  enabled=bytes.fromhex(r['descriptor_hex'])[0];restored=r['bank_sha256']==sha(expected) and r['final']['state_submit']==1;disabled=enabled==0 and all(x['enable']==0 for x in r['lanes'])
  assert restored or disabled,(route,kind,transform,root3,preserve,r['final'])
  add('old_route_native_restoration',route=route,kind=kind,transform=transform,root3=root3,preserve_cache=preserve,copy=copy,mask=mask,native_table_restored=restored,original_policy_disabled=disabled)
 # The wrapper owns exactly the generation captured before original control.
 # In particular an old-empty->new-custom switch inside the controller must
 # not let a legacy selector reinterpret the new custom grid as factory RAM.
 for j,(route,transition) in enumerate(itertools.product(routes,('custom_to_custom','empty_to_custom','custom_to_empty','off_to_on'))):
  e=setup(cp,raw,symbols);old=B;new=B+0x80000;new_grid=bytes((v^0x2f)for v in e.grid)
  oldmask=0 if transition=='empty_to_custom' else 0xc0;e.publish_fixture(old,mask=oldmask)
  e.publish_fixture(new,new_grid,mask=0 if transition=='custom_to_empty' else 0xc0);w(e.u,0x1a39448,old)
  q=dict(look='FL3' if transition=='off_to_on' else 'FL2',copy=bool(j&1),switch_at_controller=new,suite='captured_generation_isolation',**routes[route])
  # Off-to-on uses the exact explicit FL3 off record in the old generation,
  # then enables that same slot only in the newly published configuration.
  if transition=='off_to_on':
   w(e.u,new+64+2392*7+1172,1);e.u.mem_write(new+64+2392*7+1176,new_grid);e.call(symbols['r5_grid422_prepare'],new)
  r=e.frame(q)
  if transition=='empty_to_custom':
   expected=reference.packed(1,0,8,NATIVE_RAW);assert r['bank_sha256']==sha(expected) and r['final']['state_raw_source']=='0x198c1ca',(route,transition,r['final'])
   assert old+RESTORE_FIRST<=int(r['final']['state_bank'],16)<old+ALLOCATION
  elif transition=='off_to_on':assert bytes.fromhex(r['descriptor_hex'])[0]==0 and r['final']['state_bank']=='0x0' and r['final']['state_submit']==0,(route,r['final'])
  else:
   expected=model.model(e.grid,e.order,8);assert r['bank_sha256']==sha(expected) and old+52360<=int(r['final']['state_bank'],16)<old+207880,(route,transition,r['final'])
  add('captured_generation_isolation',route=route,transition=transition,copy=q['copy'],captured_old_source_retained=True,late_current_global_not_selected=True)
 # Stay within the same immutable generation while changing FL2custom to an
 # unconfigured ST/native look, then back to FL2. Native restoration must clear
 # the diagnostic bank map; the later custom request must restore it correctly.
 for j,route in enumerate(routes):
  copy=bool(j&1);e=setup(cp,raw,symbols);first=e.frame(dict(look='FL2',copy=copy,**routes[route]));diag_before=first['diagnostics'][hex(B)];index=first['final']['index']
  middle=e.frame(dict(look='ST',copy=copy,preserve_native_cache=True,**routes[route]));diag_mid=middle['diagnostics'][hex(B)]
  source_at=int(middle['final']['state_raw_source'],16);kind=middle['final']['state_kind'];transform=middle['final']['state_transform'];source=bytes(e.u.mem_read(source_at,1215 if kind==1 else 162))if source_at else None
  assert middle['bank_sha256']==sha(reference.packed(kind,transform,8,source))
  field='copy_calls' if copy else 'upload_calls';assert diag_mid[f'bank_pointer{index}']==0 and diag_mid[f'bank_slot{index}']==0 and diag_mid[field]==diag_before[field],(route,diag_before,diag_mid)
  final=e.frame(dict(look='FL2',copy=copy,preserve_native_cache=True,**routes[route]));diag_after=final['diagnostics'][hex(B)]
  assert final['bank_sha256']==first['bank_sha256'] and final['final']['state_bank']==first['final']['state_bank'] and diag_after[f'bank_pointer{index}']==int(final['final']['state_bank'],16) and diag_after[f'bank_slot{index}']==7 and diag_after[field]==diag_mid[field]+2
  add('same_generation_custom_native_custom',route=route,copy=copy,native_packed_correct=True,native_diagnostic_bank_unmapped=True,native_upload_not_counted_as_custom=True,custom_return_same_pointer=True,custom_diagnostic_restored=True)
 # Complete the common user flow: load FL2, replace same-look content, restore
 # native by clear/missing, then load another custom generation and switch off
 # and on again. All MMIO/copy contents are retained through the whole sequence.
 for copy,mask in itertools.product((False,True),(0,0x80)):
  e=setup(cp,raw,symbols);r0=e.frame(dict(look='FL2',copy=copy));new_grid=bytes((v^0x35)for v in e.grid);e.publish_fixture(B+0x80000,new_grid);r1=e.frame(dict(look='FL2',copy=copy,preserve_native_cache=True));assert r1['bank_sha256']==sha(model.model(new_grid,e.order,8)) and r1['bank_sha256']!=r0['bank_sha256']
  e.publish_fixture(B+0x100000,mask=mask);r2=e.frame(dict(look='FL2',copy=copy,preserve_native_cache=True));assert r2['bank_sha256']==sha(reference.packed(1,0,8,NATIVE_RAW))
  e.publish_fixture(B+0x180000);r3=e.frame(dict(look='FL2',copy=copy,preserve_native_cache=True));assert r3['bank_sha256']==r0['bank_sha256']
  r4=e.frame(dict(look='FL3',copy=copy,preserve_native_cache=True));assert bytes.fromhex(r4['descriptor_hex'])[0]==0 and r4['final']['state_bank']=='0x0' and r4['final']['state_submit']==0
  r5=e.frame(dict(look='FL2',copy=copy,preserve_native_cache=True));assert r5['bank_sha256']==r0['bank_sha256'] and all(x['enable']==1 for x in r5['lanes'])
  add('unified_load_replace_restore_reload',copy=copy,mask=mask,same_look_content_update=True,native_restore=True,custom_reload=True,explicit_off=True,look_switch_back=True)
 # Controller resource/unsupported fallback must actively disable the stage.
 # A previous custom table is kept in MMIO so enable0 is independently checked.
 for copy,root3,failure in itertools.product((False,True),(0,1),('building','capacity','unsupported')):
  reason=6 if failure=='unsupported' else 5
  e=setup(cp,raw,symbols);e.frame(dict(look='FL2',copy=copy));new=B+0x80000;e.publish_fixture(new,mask=0)
  if failure=='building':
   for i in range(32):w(e.u,entry(e,i,new),1)
  elif failure=='capacity':
   for i in range(31):assert restore(e,source=bytes([i])+NATIVE_RAW[1:],generation=new)
  q=dict(look='FL2',copy=copy,root3=root3,suite='controller_failure_disables')
  if reason==6:q['native_metadata']=dict(kind=3,transform=0)
  r=e.frame(q);assert r['final']['state_enable']==0 and r['final']['state_bank']=='0x0' and r['final']['state_submit']==0 and all(x['enable']==0 for x in r['lanes'])
  assert r['diagnostics'][hex(new)]['last_reason']==reason
  add('controller_failure',copy=copy,root3=root3,reason=reason,failure=failure,enable_zero=True,bank_zero=True,submit_zero=True,snapshot=r['saved_snapshot'])
 for copy,root3 in itertools.product((False,True),(0,1)):
  e=setup(cp,raw,symbols);e.frame(dict(look='FL2',copy=copy));e.publish_fixture(B+0x80000,mask=0)
  r=e.frame(dict(look='FL2',copy=copy,root3=root3,special=1,suite='unsupported_root36_disables'))
  assert r['final']['state_enable']==0 and r['final']['state_bank']=='0x0' and r['final']['state_submit']==0 and all(x['enable']==0 for x in r['lanes'])
  assert r['diagnostics'][hex(B+0x80000)]['last_reason']==6
  add('unsupported_root36',copy=copy,root3=root3,reason=6,disabled=True)
 # Unsupported helper inputs do not reserve any cache entry.
 for kind,transform,special in ((3,0,0),(255,0,0),(1,3,0),(1,255,0),(1,0,1),(1,0,255)):
  e=setup(cp,raw,symbols);ptr=restore(e,kind=kind,transform=transform,special=special);assert ptr==0 and r32(e.u,B+52252+12)==6 and r32(e.u,B+RESTORE_HEADER)==0
  add('unsupported_helper',kind=kind,transform=transform,root36=special,reason=6,no_reservation=True)
 binding_after=execution_sources(__file__,a.cp,a.cp.with_name('build.json'));assert binding_before==binding_after,'execution inputs changed during suite'
 summary=dict(native_nonzero_restore_on_clear_missing=True,restore_cache_31ready_plus_scratch=True,restore_cache_full_disables=True,restore_cache_pending_skipped=True,immutable_restore_entries=True,source_level_aliases=True,null_source_transform1_native_math=True,kind0_nonnull162=True,source_address_independent_identity=True,unsupported_restoration_disables=True,heap_guard=True,live_context_unchanged=True,old_native_routes_clear_missing=True,interleaved_builders_isolated=True,deferred_old_request_immutable=True,same_generation_native_diagnostics_unmapped=True,unified_load_replace_restore_reload=True)
 report=dict(passed=True,suite='native-restore-cache422/1',cp_path=str(a.cp),cp_sha256=sha(cp),bin_sha256=sha(raw),cases=len(rows),summary=summary,maximum_restore_stack_bytes=max_stack,original_builder_stack_bytes=reference.maximum_stack,rows=rows,limits=['Offline synthetic CPU RAM/MMIO; no device/SD/ISP pixels.','All raw contents are fixtures, not the actual camera factory RAM.','Original builder byte equality is the oracle for nonlinear transform1; no independent mathematical model.','Pending/full states are deterministic synthetic contention; hardware cache coherency and simultaneous CPUs remain unproved.','Capacity bound31READY plus one scratch is verified; physical heap margin and retained generation pressure need device acceptance.'])
 report['execution_binding']=dict(before=binding_before,after=binding_after,all_inputs_unchanged=True)
 out=a.output or HERE/'tests/restore_cache422.json';out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(rows),cp_sha256=sha(cp),output=str(out),maximum_restore_stack_bytes=max_stack,original_builder_stack_bytes=reference.maximum_stack)))
if __name__=='__main__':main()
