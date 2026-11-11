"""Compile source-bound R5 aspect adapter only; does not patch firmware."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
UP=ROOT/'analysis/r5_454_regressions_20261105/upstream-latest/source/native/feature-integration/cp'
sys.path.insert(0,str(ROOT/'projects/firmware/development/shutter-sound-recovery455/src/lib'))
from thumb_link import link
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--dispatch',action='store_true');p.add_argument('--base',type=lambda x:int(x,0),default=0x1a3b000);p.add_argument('--state',type=lambda x:int(x,0),default=0x1a394a0);p.add_argument('--out',type=Path,default=HERE/'adapter-a');a=p.parse_args()
 out=a.out;out.mkdir(parents=True,exist_ok=False)
 source=(UP/'cp_capture_latch.c').read_text()
 replacements={
  'extern volatile uint32_t aspect_selected_custom;':'#define aspect_selected_custom (*(volatile uint32_t *)(ASPECT_STATE))',
  'static uint8_t task_ids[490];':'#define task_ids ((uint8_t *)(ASPECT_STATE+12u))',
  'static uint32_t frozen_id, frozen_request;':'#define frozen_id (*(uint32_t *)(ASPECT_STATE+4u))\n#define frozen_request (*(uint32_t *)(ASPECT_STATE+8u))',
  '0xfc1730':'0x1112c64','0xfc1724':'0x1112c58','0xfc1720':'0x1112c54','0x60a8':'0x6688',
  'sizeof(task_ids)':'490u','0x5866ac':'0x5f58b0','0xa0623d':'0xae08c9',
  '0x11c1f90':'0x163f3f0','0x10fe5d0':'0x157aa10','0xd14':'0xdbc','+0xa8':'+0xcc',
  '0x11c1f68':'0x163f3c8','0x585fb8':'0x5f51bc','0x3ed2b9':'0x4596f5',
  'task+0x5550':'task+0x5ae8','0x5988':'0x5f78','0x59ec':'0x5fdc',
  '0x53e8':'0x5980','0x53f0':'0x5988','0x5861f8':'0x5f53fc','task+0x55a4':'task+0x5b3c',
 }
 for old,new in replacements.items():
  assert old in source,old;source=source.replace(old,new)
 header=f'#define ASPECT_STATE {hex(a.state)}u\n'
 # Comments below the source are retained provenance, while all executable
 # constants above were independently matched against the R5 machine code.
 selector='''\nuint32_t aspect_cp_select(uint32_t wire) {
 if (wire>=5u && wire<=8u) {aspect_selected_custom=wire-1u;return 2u;}
 aspect_selected_custom=0;return wire;
}
'''
 # Do not carry the obsolete HEIF union processing helper into final code.
 source=source[:source.index('/* Native HEIF path:')]
 # RAW/JPEG encoded previews share these native requests; Bayer stays native.
 source=source.replace('(read32(task+0x5980)==1 || read32(task+0x5988)==1)', '(read32(task+0x5980)==1 || read32(task+0x5988)==1 || read32(task+0x5980)==2 || read32(task+0x5988)==2)')
 source=source.replace('(read32(task+0x5980)!=1 && read32(task+0x5988)!=1)', '(read32(task+0x5980)!=1 && read32(task+0x5988)!=1 && read32(task+0x5980)!=2 && read32(task+0x5988)!=2)')
 (out/'cp_capture_latch.c').write_text(header+source+selector)
 for name in ['crop_core.c','crop_core.h']:
  payload=(UP/name).read_text()
  if name=='crop_core.c':
   assert 'static const uint8_t numerators[4] = {17, 65, 5, 7};' in payload
   payload=payload.replace('static const uint8_t numerators[4] = {17, 65, 5, 7};','static const uint16_t numerators[4] = {809, 239, 5, 37};').replace('static const uint8_t denominators[4] = {6, 24, 4, 6};','static const uint16_t denominators[4] = {500, 100, 4, 20};')
  (out/name).write_text(payload)
 wrappers=(UP/'cp_crop_wrappers.S').read_text()
 for old,new in [('0x41d62d','0x48b9d9'),('0x53e8','0x5980'),('0x53f0','0x5988'),('0x5480','0x5a18')]:
  assert old in wrappers;wrappers=wrappers.replace(old,new)
 wrappers=wrappers.replace('mov.w r5,#0x5a18','movw r5,#0x5a18')
 start=wrappers.index('.section .text.aspect_heif_packet_hook');end=wrappers.index('.macro NOTIFY',start)
 wrappers=wrappers[:start]+wrappers[end:]
 # Existing selector wrapper already preserves all call-clobbered registers.
 selector_asm=(UP/'cp_selector_wrapper.S').read_text().replace('#0xa8','#0xcc')
 selector_asm=selector_asm.replace('    mov r0, r1','    mrs r12,apsr\n    push {r4,r12}\n    mov r0, r1').replace('    pop {r0-r3, r12, pc}','    pop {r4,r12}\n    msr apsr_nzcvqg,r12\n    pop {r0-r3, r12, pc}')
 (out/'cp_wrappers.S').write_text(wrappers+'\n'+selector_asm)
 objects=[];commands=[]
 (out/'raw_emb.c').write_bytes((HERE/'raw_emb.c').read_bytes())
 names=['crop_core.c','cp_capture_latch.c','cp_wrappers.S','raw_emb.c']
 if a.dispatch:
  (out/'aspect_module_dispatch.S').write_bytes((HERE/'aspect_module_dispatch.S').read_bytes());names.append('aspect_module_dispatch.S')
 for name in names:
  obj=out/(Path(name).stem+'.o')
  cmd=['clang','--target=arm-none-eabi','-mthumb','-march=armv7-a','-mfloat-abi=soft','-Oz','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-ffunction-sections','-fdata-sections','-fstack-usage','-Wall','-Wextra','-Werror','-I',str(out),'-c',str(out/name),'-o',str(obj)]
  subprocess.run(cmd,check=True);objects.append(obj);commands.append(cmd)
 code,symbols=link(objects,base=a.base,read_only=True)
 (out/'adapter.bin').write_bytes(code)
 native=(ROOT/'unpacked/r5/cp_data/cpapp-b.bin').read_bytes()
 sites={
 'selector':(0x33f322,'aspect_cp_select_hook',4),'freeze':(0xadf128,'aspect_freeze_copy',4),
 'capture':(0xadd846,'aspect_capture_copy',4),'jpeg_main':(0x473562,'aspect_jpeg_copy_hook',4),
 'jpeg_scn':(0x472a0e,'aspect_jpeg_copy_hook',4),'thumbnail':(0x46e07e,'aspect_thumbnail_clear_hook',4),
 'notify_primary':(0xae77d8,'aspect_notify_primary_hook',4),'notify_secondary':(0xae7822,'aspect_notify_secondary_hook',4),
 'notify_clear':(0xae7a20,'aspect_notify_release_hook',4),
 'raw_emb':(0x48a00a,'aspect_raw_emb_build',4),
 'pool_reset':(0x4614a4,'aspect_pool_reset_hook',4),'pool_release':(0xae088a,'aspect_pool_release',4)}
 report={'schema':'r5-aspect-cp-adapter/1','firmware_emitted':False,'installable':False,
 'R5_stock_sha256':sha(native),'code_bytes':len(code),'code_sha256':sha(code),'RX':hex(a.base),'state':hex(a.state),'state_bytes':504,
 'upstream_commit':'79c3663b1ac4fda98047c2c4f5769b9d60d25920',
 'sources':{n:sha((UP/n).read_bytes()) for n in ['crop_core.c','crop_core.h','cp_capture_latch.c','cp_crop_wrappers.S','cp_selector_wrapper.S']},
 'symbols':{k:hex(v) for k,v in symbols.items()},'commands':commands,
 'ratios':{'4':[809,500],'5':[239,100],'6':[5,4],'7':[37,20]},
 'production_sources':{n:sha((out/n).read_bytes())for n in names+['crop_core.h']},
 'hooks':{k:{'VA':hex(at),'source_bytes':native[at-0x108000:at-0x108000+n].hex(),'target':symbol} for k,(at,symbol,n) in sites.items()},
 'R5_contract':{'pool':hex(0x1112c54),'max_count':490,'task_stride':hex(0x6688),'current_state':hex(0x157aa10),'frozen_state':hex(0x163f3f0),'request_id':hex(0x163f3c8),'aspect_state_offset':hex(0xcc),'aspect_task_offset':hex(0x24),'format_offsets':[hex(0x5980),hex(0x5988)],'main_roi':hex(0x5f78),'scn_roi':hex(0x5fdc),'thm_roi':hex(0x5fe8)},
 'remaining':['RX/state placement and native boot/MMU proof','resident guarded dispatch','AVCAM format dimensions','complete AP and output integration']}
 (out/'build.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'code_bytes':len(code),'state_bytes':504,'out':str(out),'firmware_emitted':False}))
if __name__=='__main__':main()
