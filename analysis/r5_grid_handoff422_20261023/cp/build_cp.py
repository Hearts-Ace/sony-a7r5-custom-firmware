"""Offline native12 prototype, source404; release gated by integrated replays."""
from pathlib import Path
import sys,json,hashlib,struct,subprocess
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;WORK=OUT.parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools'),str(ROOT/'research/r5_custom_lut/scripts'),str(ROOT/'research/r5_custom_lut/evidence/sd405_cp_binding')]
from replay_gamma_owned_consumers import link
from build_r5_m4strict_cp import bw
from evaluate_rx_page_v2 import trampoline,branch,mov16
BASE=0x108000;RX=0x1195500
SOURCE=ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin';SHA='8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32'
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 raw=SOURCE.read_bytes();assert sha(raw)==SHA;objects=[];commands=[]
 for src in [OUT/'cp_stage413_probe.c',OUT/'cp_stage413_gate.S',OUT/'cp_transfer.c',OUT/'native_color.c',OUT/'grid_gate.S',OUT/'grid_observe.S',OUT/'grid_lifecycle.S',OUT/'cc1_gate.S',OUT/'b13_gate.S',WORK/'gamma/native_gamma.c']:
  obj=OUT/(src.stem+'.o');cmd=['clang','--target=arm-none-eabi','-mthumb','-march=armv7-a','-mfloat-abi=soft','-Oz','-fno-jump-tables','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-ffunction-sections','-fdata-sections','-fstack-usage','-Wall','-Wextra','-Werror','-I',str(OUT),'-I',str(WORK/'import'),'-I',str(WORK/'gamma'),'-c',str(src),'-o',str(obj)]
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
 fixslots('r5_grid420_builder_original',[0x231658]);fixslots('r5_grid420_upload_original',[0x414f48]);fixslots('r5_native419_grid_gate',[0x230ee6]);fixslots('r5_cp_stage413_gate',[0x496068,0x49604e,0x496056]);fixslots('r5_native418_cc1_gate',[0x71e72a]);fixslots('r5_native418_b13_gate',[0x71d6f2,0x71d6f2,0x71d6d0])
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
 assert raw[0x230f0a-BASE:0x230f0c-BASE].hex()=='00e0'
 patch(0x230f0a-BASE,bytes.fromhex('ffe7'),'Retarget displaced native branch to guard instruction boundary')
 # Native controller guard/validator/retry: exact R5 boundaries only.
 for at,expected,symbol in [(0x230f0c,'bcb14846','r5_grid421_guard'),(0x2312f0,'002565e1','r5_grid421_validator'),(0x230f62,'4ff61450','r5_grid421_retry')]:
  assert raw[at-BASE:at-BASE+4].hex()==expected,(hex(at),raw[at-BASE:at-BASE+4].hex())
  patch(at-BASE,bw(at,sy[symbol]&~1),'R5 custom grid guarded controller lifecycle')
 assert raw[0x230ee0-BASE:0x230ee6-BASE]==bytes.fromhex('002ac5f88421')
 patch(0x230ee0-BASE,bw(0x230ee0,sy['r5_native419_grid_gate']&~1)+bytes.fromhex('00bf'),'Native grid table selection before original correction builder/upload')
 for at,symbol in [(0x231654,'r5_grid420_builder'),(0x414f44,'r5_grid420_upload')]:
  assert raw[at-BASE:at-BASE+4]==bytes.fromhex('f0b503af');patch(at-BASE,bw(at,sy[symbol]&~1),'Grid diagnostic call/return observer; native prologue displaced')
 def bl(at,target):
  b=bytearray(bw(at,target&~1));struct.pack_into('<H',b,2,struct.unpack_from('<H',b,2)[0]|0x4000);return b
 assert raw[0x719f16-BASE:0x719f1a-BASE]==bl(0x719f16,0x230da8)
 patch(0x719f16-BASE,bl(0x719f16,sy['r5_grid422_controller']),'422 source-snapshot immutable grid handoff after original controller')
 assert raw[0x49604a-BASE:0x49604e-BASE]==bytes.fromhex('307818b1');patch(0x49604a-BASE,bw(0x49604a,sy['r5_cp_stage413_gate']&~1),'Original receive task')
 assert raw[0x71e726-BASE:0x71e72a-BASE]==bytes.fromhex('435a6518');patch(0x71e726-BASE,bw(0x71e726,sy['r5_native418_cc1_gate']&~1),'Native CC1 pointer, preserve original arithmetic/adjustments')
 assert raw[0x71d6f8-BASE:0x71d6fc-BASE]==bytes.fromhex('00f091fe');patch(0x71d6f8-BASE,bl(0x71d6f8,sy['r5_native418_matrix']),'Native selected matrix input')
 assert raw[0x71d6cc-BASE:0x71d6d0-BASE]==bytes.fromhex('352b10d1');patch(0x71d6cc-BASE,bw(0x71d6cc,sy['r5_native418_b13_gate']&~1),'Selected BW/SE full block13; original identity fallback')
 gm=json.loads((ROOT/'analysis/r5_native_grid420_20261022/gamma/getter_build_dynamic/gates.json').read_text());gcode=(ROOT/'analysis/r5_native_grid420_20261022/gamma/getter_build_dynamic/gates.bin').read_bytes();gva=int(gm['RX'],16)
 assert gm['schema']=='r5-native-gamma418-gates/2','FixedBSS getter forbidden: overlaps page table'
 assert gva+len(gcode)<=RX;assert raw[gva-BASE:gva-BASE+len(gcode)]==bytes(len(gcode));patch(gva-BASE,gcode,'Dynamic heap Gamma table getter, sealed common ready')
 for p in gm['patches']:
  at=p['offset'];assert raw[at:at+len(bytes.fromhex(p['before']))]==bytes.fromhex(p['before']);patch(at,bytes.fromhex(p['after']),p.get('reason','Gamma getter/bounds'))
 reverse=bytearray(candidate)
 for p in reversed(patches):reverse[p['offset']:p['offset']+len(bytes.fromhex(p['before']))]=bytes.fromhex(p['before'])
 assert reverse==raw
 (OUT/'cp420-grid.NONINSTALLABLE.bin').write_bytes(candidate);(OUT/'native12.text.bin').write_bytes(code)
 report=dict(schema='r5-native12-build/1',source_sha256=SHA,candidate_sha256=sha(candidate),installable=False,DAT_generated=False,code_bytes=len(code),RX=hex(RX),symbols={k:hex(v)for k,v in sy.items()},patches=patches,compile_commands=commands,reverse404_exact=True,BSS_extension_bytes=32,heap_bytes=207880,grid422_offset=52352,grid422_table_offset=52360,grid422_classes=8,grid422_packed_bytes=155520,packed_header_offset=52352,packed_table_offset=52360,packed_levels=8,packed_slot_stride=12960,bank_bytes=28768,Gamma_context_bytes=23484,old_selection_identity_hooks=False,limits=['Integrated loader/transport/native fallback/render tests required before packaging. No camera execution.'])
 source_paths=set([Path(c[c.index('-c')+1]) for c in commands])
 source_paths.update(OUT.glob('*.h'));source_paths.update((WORK/'import').glob('*.h'));source_paths.update((WORK/'gamma').glob('*.h'))
 source_paths.update([Path(__file__),ROOT/'analysis/r5_native_grid420_20261022/gamma/getter_build_dynamic/gates.json',ROOT/'analysis/r5_native_grid420_20261022/gamma/getter_build_dynamic/gates.bin'])
 report['sources']={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(source_paths)}
 (OUT/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k]for k in ['candidate_sha256','code_bytes','heap_bytes','installable']}))
if __name__=='__main__':main()
