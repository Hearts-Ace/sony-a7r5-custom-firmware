"""Offline native12 prototype, source404; release gated by integrated replays."""
from pathlib import Path
import sys,json,hashlib,struct,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent;WORK=OUT.parent
sys.path[:0]=[str(ROOT/'lib')]
from thumb_link import link
from thumb_ops import bw
from arm_ops import trampoline,branch,mov16
BASE=0x108000;RX=0x1195270
SOURCE=ROOT/'inputs/cp_baseline.bin';SHA='8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32'
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 raw=SOURCE.read_bytes();assert sha(raw)==SHA;objects=[];commands=[]
 for src in [OUT/'cp_stage413_probe.c',OUT/'cp_stage413_gate.S',OUT/'cp_transfer.c',OUT/'custom_filter423.c',OUT/'native_color.c',OUT/'grid_observe.S',OUT/'cc1_gate.S',OUT/'b13_gate.S',WORK/'gamma/native_gamma.c']:
  obj=OUT/(src.stem+'.o');cmd=['clang','--target=arm-none-eabi','-mthumb','-march=armv7-a','-mfloat-abi=soft','-Oz','-fno-jump-tables','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-ffunction-sections','-fdata-sections','-fstack-usage','-Wall','-Wextra','-Werror','-I',str(OUT),'-I',str(WORK/'cp_include'),'-I',str(WORK/'gamma'),'-c',str(src),'-o',str(obj)]
  subprocess.run(cmd,check=True);objects.append(obj);commands.append(cmd)
 code,sy=link(objects,base=RX);code=bytearray(code)
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
 assert RX+len(code)<=0x1197000
 candidate=bytearray(raw);patches=[]
 def patch(at,data,reason):
  before=raw[at:at+len(data)];assert candidate[at:at+len(data)]==before
  assert all(at+len(data)<=p['offset']or at>=p['offset']+len(bytes.fromhex(p['after']))for p in patches)
  candidate[at:at+len(data)]=data;patches.append(dict(offset=at,before=before.hex(),after=data.hex(),reason=reason))
 old=trampoline();loader=bytearray(old[:-12]);loader+=mov16(0,0x5000)+mov16(0,0x119,True)+struct.pack('<III',0xe1a02000,0xe3a01a01,0xe3a0300e);loader+=branch(0x108f40+len(loader),0x108768,True);loader+=old[-12:]
 assert len(loader)==76 and raw[0xf40:0xf8c]==bytes(76)
 patch(0xf40,loader,'Original mapper plus RX1196000 and1195000 same verified76B trampoline')
 patch(0x6d0,branch(0x1086d0,0x108f40,True),'Final native mapping detour')
 patch(0x20140,struct.pack('<I',0x118000),'Initialized data include existing RX padding')
 patch(0x2014c,struct.pack('<I',0x8a2468),'32B state only; original page table and last BSS page preserved')
 assert raw[0x5e3ee8-BASE:0x5e3eec-BASE]==mov16(3,0x9448)
 patch(0x5e3ee8-BASE,mov16(3,0x9468),'Original primary clear extends32B')
 assert raw[RX-BASE:RX-BASE+len(code)]==bytes(len(code));patch(RX-BASE,code,'Native12 receiver and common immutable parameter source')
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
 report=dict(schema='r5-native12-build/1',source_sha256=SHA,candidate_sha256=sha(candidate),installable=False,DAT_generated=False,code_bytes=len(code),RX=hex(RX),symbols={k:hex(v)for k,v in sy.items()},patches=patches,compile_commands=commands,reverse404_exact=True,BSS_extension_bytes=32,heap_bytes=522152,grid422_offset=52352,grid422_table_offset=52360,grid422_classes=8,grid422_packed_bytes=155520,packed_header_offset=52352,packed_table_offset=52360,packed_levels=8,packed_slot_stride=12960,restore_cache_offset=207880,restore_used_offset=207880,restore_entry_offset=207888,restore_entry_bytes=2936,restore_entry_count=32,restore_ready_limit=31,restore_entry_ready_offset=0,restore_entry_key_offset=4,restore_entry_raw_offset=8,restore_entry_raw_bytes=1216,restore_entry_work_offset=1224,restore_entry_packed_offset=1316,restore_entry_packed_bytes=1620,restore_error_resource=5,restore_error_unsupported=6,bank_bytes=28768,Gamma_context_bytes=20028,old_selection_identity_hooks=False,limits=['Integrated loader/transport/native fallback/render tests required before packaging. No camera execution.'])
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
