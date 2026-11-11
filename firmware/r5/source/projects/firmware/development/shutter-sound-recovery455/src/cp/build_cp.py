"""Offline native12 prototype, source404; release gated by integrated replays."""
from pathlib import Path
import sys,json,hashlib,struct,subprocess,zlib
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent;WORK=OUT.parent
sys.path[:0]=[str(ROOT/'lib')]
from thumb_link import link
from thumb_ops import bw
from arm_ops import trampoline,branch,mov16
BASE=0x108000;RX=0x1195260;SOUND=0x1a3a000;SOUND_SOURCE=0x1198000;SOUND_BYTES=2240
DEAD_SECTIONS={'.text.r5_native_gamma418_put','.text.r5_boot_bank_seal'}
SOURCE=ROOT/'inputs/cp_baseline.bin';SHA='8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32'
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 raw=SOURCE.read_bytes();assert sha(raw)==SHA;objects=[];commands=[]
 for src in [OUT/'cp_stage413_probe.c',OUT/'cp_stage413_gate.S',OUT/'cp_transfer.c',OUT/'custom_filter423.c',OUT/'native_color.c',OUT/'grid_observe.S',OUT/'cc1_gate.S',OUT/'b13_gate.S',WORK/'gamma/native_gamma.c',OUT/'r5_resident_crc.c']:
  obj=OUT/(src.stem+'.o');cmd=['clang','--target=arm-none-eabi','-mthumb','-march=armv7-a','-mfloat-abi=soft','-Oz','-fno-jump-tables','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-ffunction-sections','-fdata-sections','-fstack-usage','-Wall','-Wextra','-Werror','-I',str(OUT),'-I',str(WORK/'cp_include'),'-I',str(WORK/'gamma'),'-c',str(src),'-o',str(obj)]
  subprocess.run(cmd,check=True);objects.append(obj);commands.append(cmd)
 # The original Gamma gates end at1195260; use their existing16B alignment
 # gap, not native initialized data (which ends1195070). Only two private
 # helpers with no incoming relocation are omitted. Live filter code remains.
 guard_objects=[]
 for name in ['r5_sound_page.S','r5_sound_guard_hooks.S','r5_sound_gain_guard.S']:
  src=OUT/name;obj=OUT/(src.stem+'.o');cmd=commands[0][:]
  cmd[cmd.index('-c')+1]=str(src);cmd[cmd.index('-o')+1]=str(obj)
  cmd+=['-DR5SS_SOUND_BYTES='+str(SOUND_BYTES)]
  subprocess.run(cmd,check=True);commands.append(cmd);guard_objects.append(obj)
 provisional={'r5ss_cp_extended_consume':SOUND|1,'r5ss_cp_completion_hook':SOUND|1,'r5ss_cp_gain_hook':SOUND|1,'r5ss_guard_expected_crc_inverse':0xdeadbeef}
 code,sy=link(objects+guard_objects,base=RX,externals=provisional,drop_sections=DEAD_SECTIONS)
 sound_objects=[]
 for name in ['r5_sound_receive.c','r5_sound_snapshot.c','r5_sound_completion.c','r5_sound_completion_hooks.S','r5_sound_completion_state.c','r5_sound_gain.c','r5_sound_gain_hooks.S']:
  src=OUT/name;obj=OUT/(src.stem+'.o');cmd=commands[0][:]
  cmd[cmd.index('-c')+1]=str(src);cmd[cmd.index('-o')+1]=str(obj)
  cmd+=['-DR5SS_FILTER_CONSUME_ADDRESS='+hex(sy['r5_cp_stage413_consume'])+'u']
  subprocess.run(cmd,check=True);commands.append(cmd);sound_objects.append(obj)
 sound_code,sound_sy=link(sound_objects,base=SOUND,read_only=True)
 assert sound_sy['r5ss_cp_extended_consume']==SOUND|1 and len(sound_code)==SOUND_BYTES
 sound_code=bytearray(sound_code);stub=(sound_sy['r5ss_cp_completion_original']&~1)-SOUND
 assert sound_code[stub+4:stub+8]==bytes.fromhex('dff800f0')
 assert struct.unpack_from('<I',sound_code,stub+8)[0]==0x6549e1
 link_audit={}
 code,sy=link(objects+guard_objects,base=RX,drop_sections=DEAD_SECTIONS,audit=link_audit,externals={
  'r5ss_cp_extended_consume':sound_sy['r5ss_cp_extended_consume'],
  'r5ss_cp_completion_hook':sound_sy['r5ss_cp_completion_hook'],
  'r5ss_cp_gain_hook':sound_sy['r5ss_cp_gain_hook'],
  'r5ss_guard_expected_crc_inverse':(~zlib.crc32(sound_code))&0xffffffff})
 code=bytearray(code);stub=(sy['r5ss_cp_guard_original']&~1)-RX
 assert code[stub+4:stub+8]==bytes.fromhex('00bf00bf')
 code[stub+4:stub+8]=bw(RX+stub+4,0x6549e0)
 assert link_audit['dropped_bytes']==144
 # The removed helpers are not native patch roots or exported firmware APIs.
 # Their former4.36 entry addresses have no numeric literal consumers in the
 # SHA-bound baseline; all private direct calls are accounted by relocations.
 numeric_consumers={}
 for name,address in [('r5_native_gamma418_put',0x1196e31),('r5_boot_bank_seal',0x11960d5)]:
  hits=[]
  for value in(address,address&~1):
   at=raw.find(struct.pack('<I',value))
   if at>=0:hits.append(at)
  assert not hits,(name,hits)
  numeric_consumers[name]={'former436_entry':hex(address),'baseline_numeric_pointer_hits':hits,'native_patch_root':False}
 link_audit['removed_helper_numeric_consumers']=numeric_consumers
 def fixslots(symbol,targets):
  off=(sy[symbol]&~1)-RX
  ends=[(x&~1)-RX for x in sy.values()if (x&~1)>=(sy[symbol]&~1)+1];end=min(ends,default=len(code))
  at=off;found=[]
  while at+4<=end:
   if code[at:at+4]==bytes.fromhex('00bf00bf'):found.append(at);at+=4
   else:at+=2
  assert len(found)==len(targets),(symbol,found,targets)
  for at,target in zip(found,targets):code[at:at+4]=bw(RX+at,target)
 fixslots('r5_grid420_upload_original',[0x414f48]);fixslots('r5_cp_stage413_gate',[0x496068,0x49604e,0x496056]);fixslots('r5_native418_cc1_gate',[0x71e72a]);fixslots('r5_native418_b13_gate',[0x71d6f2,0x71d6f2,0x71d6d0])
 resident_used=len(code)
 assert resident_used<=7584,(resident_used,7584)
 code+=bytes(7584-resident_used)
 assert RX+len(code)==0x1197000
 candidate=bytearray(raw);patches=[]
 def patch(at,data,reason):
  before=raw[at:at+len(data)];assert candidate[at:at+len(data)]==before
  assert all(at+len(data)<=p['offset']or at>=p['offset']+len(bytes.fromhex(p['after']))for p in patches)
  candidate[at:at+len(data)]=data;patches.append(dict(offset=at,before=before.hex(),after=data.hex(),reason=reason))
 old=trampoline();loader=bytearray(old[:-12]);loader+=mov16(0,0x5000)+mov16(0,0x119,True)+struct.pack('<III',0xe1a02000,0xe3a01a01,0xe3a0300e);loader+=branch(0x108f40+len(loader),0x108768,True);loader+=old[-12:]
 # Keep all guards/fallbacks resident. Copy the optional immutable code to a
 # descriptor-reserved page beyond the unchanged native BSS clear endpoint.
 # Native MMU init removes bootstrap pages, so no sound code lives there.
 # EXEC_MODE selects the same RAM/NOR supply convention as native text.
 loader=bytearray(loader[:-12])
 loader+=mov16(0,SOUND&65535)+mov16(0,SOUND>>16,True)
 loader+=mov16(1,SOUND_SOURCE&65535)+mov16(1,SOUND_SOURCE>>16,True)
 loader+=mov16(2,SOUND_BYTES)
 loader+=mov16(12,0x2000)+mov16(12,0x3e4,True)+struct.pack('<II',0xe5dcc000,0xe35c0000)
 sound_nor=0xd0200000+SOUND_SOURCE-BASE
 for word in [mov16(1,sound_nor&65535),mov16(1,sound_nor>>16,True)]:
  loader+=struct.pack('<I',(struct.unpack('<I',word)[0]&0x0fffffff)|0x10000000)
 copy_loop=0x108f40+len(loader)
 loader+=struct.pack('<III',0xe4913004,0xe4803004,0xe2522004)
 jump=struct.unpack('<I',branch(0x108f40+len(loader),copy_loop))[0]
 loader+=struct.pack('<I',(jump&0x0fffffff)|0x10000000)
 loader+=mov16(0,SOUND&65535)+mov16(0,SOUND>>16,True)+struct.pack('<III',0xe1a02000,0xe3a01a01,0xe3a0300f)
 loader+=branch(0x108f40+len(loader),0x108768,True);loader+=old[-12:]
 assert len(loader)<=0xc0 and raw[0xf40:0xf40+len(loader)]==bytes(len(loader))
 patch(0xf40,loader,'4.36 mapper adds immutable sound copy and reserved runtime RX page')
 patch(0x6d0,branch(0x1086d0,0x108f40,True),'Final native mapping detour')
 patch(0x20140,struct.pack('<I',0x118000),'Initialized data include existing RX padding')
 patch(0x2014c,struct.pack('<I',0x8a4000),'Reserve sound page through1A3B000; native clear endpoint/page tables unchanged')
 assert raw[0x5e3ee8-BASE:0x5e3eec-BASE]==mov16(3,0x9448)
 patch(0x5e3ee8-BASE,mov16(3,0x9498),'Original primary clear includes16B completion and32B private gain binding')
 assert raw[RX-BASE:RX-BASE+len(code)]==bytes(len(code));patch(RX-BASE,code,'Native12 receiver and common immutable parameter source')
 assert raw[SOUND_SOURCE-BASE:SOUND_SOURCE-BASE+len(sound_code)]==bytes(len(sound_code))
 patch(SOUND_SOURCE-BASE,sound_code,'Immutable copy source; runtime destination is reserved1A3A000')
 assert raw[0x6549dc-BASE:0x6549e0-BASE]==bytes.fromhex('f0b503af')
 patch(0x6549dc-BASE,bw(0x6549dc,sy['r5ss_cp_guard_cleanup']&~1),'Resident kind17 observer with complete native fallback')
 assert raw[0x1998b8-BASE:0x1998be-BASE]==bytes.fromhex('28798df80400')
 patch(0x1998b8-BASE,bw(0x1998b8,sy['r5ss_cp_guard_gain']&~1)+bytes.fromhex('00bf'),'Owned kind17 gain only; resident PTE/CRC guard and exact native fallback')
 # Every original grid-controller caller resolves to719f16. The captured
 # immutable wrapper now owns custom selection at that callsite. Retain the
 # original native source assignment, guard/validator/retry and branch bytes;
 # never perform a second, late STATE lookup inside the native controller.
 for at,expected in [(0x230ee0,'002ac5f88421'),(0x230f0a,'00e0'),(0x230f0c,'bcb14846'),(0x2312f0,'002565e1'),(0x230f62,'4ff61450')]:
  assert raw[at-BASE:at-BASE+len(bytes.fromhex(expected))].hex()==expected
 for at,symbol in [(0x414f44,'r5_grid420_upload')]:
  assert raw[at-BASE:at-BASE+4]==bytes.fromhex('f0b503af');patch(at-BASE,bw(at,sy[symbol]&~1),'Grid diagnostic call/return observer; native prologue displaced')
 def bl(at,target):
  b=bytearray(bw(at,target&~1));struct.pack_into('<H',b,2,struct.unpack_from('<H',b,2)[0]|0x4000);return b
 assert raw[0x719f16-BASE:0x719f1a-BASE]==bl(0x719f16,0x230da8)
 patch(0x719f16-BASE,bl(0x719f16,sy['r5_grid422_controller']),'422 source-snapshot immutable grid handoff after original controller')
 assert raw[0x49604a-BASE:0x49604e-BASE]==bytes.fromhex('307818b1');patch(0x49604a-BASE,bw(0x49604a,sy['r5_cp_stage413_gate']&~1),'Original receive task')
 assert raw[0x71e726-BASE:0x71e72a-BASE]==bytes.fromhex('435a6518');patch(0x71e726-BASE,bw(0x71e726,sy['r5_native418_cc1_gate']&~1),'Native CC1 pointer, preserve original arithmetic/adjustments')
 assert raw[0x71d6f8-BASE:0x71d6fc-BASE]==bytes.fromhex('00f091fe');patch(0x71d6f8-BASE,bl(0x71d6f8,sy['r5_native418_matrix']),'Native selected matrix input')
 assert raw[0x71d6cc-BASE:0x71d6d0-BASE]==bytes.fromhex('352b10d1');patch(0x71d6cc-BASE,bw(0x71d6cc,sy['r5_native418_b13_gate']&~1),'Selected BW/SE full block13; original identity fallback')
 gm=json.loads((WORK/'gamma/getter_build423/gates.json').read_text());gcode=(WORK/'gamma/getter_build423/gates.bin').read_bytes();gva=int(gm['RX'],16)
 assert gm['schema']=='r5-native-gamma423-view-gates/1','FixedBSS getter forbidden: overlaps page table'
 assert gva+len(gcode)<=RX;assert raw[gva-BASE:gva-BASE+len(gcode)]==bytes(len(gcode));patch(gva-BASE,gcode,'Dynamic heap Gamma table getter, sealed common ready')
 for p in gm['patches']:
  at=p['offset'];assert raw[at:at+len(bytes.fromhex(p['before']))]==bytes.fromhex(p['before']);patch(at,bytes.fromhex(p['after']),p.get('reason','Gamma getter/bounds'))
 reverse=bytearray(candidate)
 for p in reversed(patches):reverse[p['offset']:p['offset']+len(bytes.fromhex(p['before']))]=bytes.fromhex(p['before'])
 assert reverse==raw
 (OUT/'cp423.NONINSTALLABLE.bin').write_bytes(candidate);(OUT/'native12.text.bin').write_bytes(code)
 report=dict(schema='r5-native12-build/1',source_sha256=SHA,candidate_sha256=sha(candidate),installable=False,DAT_generated=False,code_bytes=len(code),RX=hex(RX),symbols={k:hex(v)for k,v in sy.items()},patches=patches,compile_commands=commands,reverse404_exact=True,BSS_extension_bytes=48,heap_bytes=522152,grid422_offset=52352,grid422_table_offset=52360,grid422_classes=8,grid422_packed_bytes=155520,packed_header_offset=52352,packed_table_offset=52360,packed_levels=8,packed_slot_stride=12960,restore_cache_offset=207880,restore_used_offset=207880,restore_entry_offset=207888,restore_entry_bytes=2936,restore_entry_count=32,restore_ready_limit=31,restore_entry_ready_offset=0,restore_entry_key_offset=4,restore_entry_raw_offset=8,restore_entry_raw_bytes=1216,restore_entry_work_offset=1224,restore_entry_packed_offset=1316,restore_entry_packed_bytes=1620,restore_error_resource=5,restore_error_unsupported=6,bank_bytes=28768,Gamma_context_bytes=20028,old_selection_identity_hooks=False,limits=['Integrated loader/transport/native fallback/render tests required before packaging. No camera execution.'])
 report['sound_symbols']={k:hex(v)for k,v in {**sound_sy,**{k:v for k,v in sy.items()if k.startswith('r5ss_')}}.items()}
 report['BSS_extension_bytes']=0x8a4000-0x8a2448
 report['link_audit']=link_audit
 report['sound_page_guard']={'PTE':['0x01a3a63e'],'runtime_VA':hex(SOUND),'copy_source_RAM':hex(SOUND_SOURCE),'copy_source_NOR':hex(sound_nor),'descriptor_BSS_end':'0x1a3b000','native_BSS_clear_end':'0x1a39498','L1_table':'0x1a3c000','L2_table':'0x1a40000','table_source':'active TTBR0, native identity-mapped table pool','full_code_crc32':hex(zlib.crc32(sound_code)),'code_bytes':len(sound_code),'resident_used_bytes':resident_used,'resident_padding_bytes':7584-resident_used,'resident_guard_begin':hex(sy['r5ss_cp_sound_page_error']&~1),'resident_guard_end_exclusive':hex(RX+len(code)),'no_bootstrap_descriptor_code':True,'dropped_unreferenced_sections':sorted(DEAD_SECTIONS),'dropped_bytes':144,'ordinary_non_e6':'direct original filter consumer; no optional-page reads','fallback':'original filter consume / full native cleanup'}
 report['private_gain']={'native_hook':'0x1998b8','native_continuation':'0x1998be','binding_state':'0x1a39478','binding_bytes':32,'native_callers':['0x6550fb','0x655541','0x656079'],'owned_kind':17,'owned_scalar':7,'fallback':'exact original ldrb/strb and all registers/APSR','registry_written':False,'native_path_written':False,'resident_crc_dedup_bytes':68}
 source_paths=set([Path(c[c.index('-c')+1]) for c in commands])
 report['restore_key']={'source_present_bit':24,'kind_shift':16,'transform_shift':8,'level_classes':[0,1,2,3,4,5,6,7,8],'level_ge8_maps_to':8,'kind0_nonnull_raw_bytes':162,'kind1_nonnull_raw_bytes':1215,'kind2_nonnull_raw_bytes':162,'null_raw_bytes':0}
 report['retired_grid_detours']=['0x230ee0','0x230f0a','0x230f0c','0x2312f0','0x230f62']
 report['controller_handoff']={'callsite':'0x719f16','max_root3':1,'native_index_range':[0,3],'legacy_destination':'index<=2 || (index==3 && env6==1)','added_destination':'index==3 && root1==1 && env_domain==6 && env6==0','custom_enable':'selected configuration always has599; immutable table ready && root2c4==0; late native packet gates retained','native_fallback':'selection0 original controller enable/strength retained; immutable original-builder packed table submitted','unsupported_root36':'explicit disable, packed0, submit0, diag reason6'}
 report['custom_filter423']={'selected_range':[0,12],'active_view_va':'0x1a39458','accepted_alias_va':'0x1a3945c','last_sequence_va':'0x1a39460','last_selected_va':'0x1a39464','view_offset':50896,'view_bytes':24,'views':13,'off_expanded75_table_offset':48796,'extra_Gamma_offset':301840,'Gamma_context_bytes':20028,'Gamma_native_record_groups':10,'Gamma_tail_aliases':[['ST','NT'],['BW','SE']],'data_publication':'canonical bank only; SELECT release-publishes active view','selected0':'native route/normal route plus75-row expanded native table for delayed custom IDs','per_selection_heap_allocations':0,'sixteen_generation_maximum_bytes':8354432,'mandatory_grid':True,'full_frame_atomic_switch_proven':False}
 source_paths.update(OUT.glob('*.h'));source_paths.update((WORK/'cp_include').glob('*.h'));source_paths.update((WORK/'gamma').glob('*.h'))
 source_paths.update([Path(__file__),WORK/'gamma/getter_gates.py',WORK/'gamma/getter_build423/gates.json',WORK/'gamma/getter_build423/gates.bin'])
 report['sources']={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(source_paths)}
 (OUT/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k]for k in ['candidate_sha256','code_bytes','heap_bytes','installable']}))
if __name__=='__main__':main()
