#!/usr/bin/env python3
"""Compile the 4.13-derived native-12 importer. No camera or partition writes."""
from pathlib import Path
import sys,json,hashlib,subprocess,struct
ROOT=Path(__file__).resolve().parents[1]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'lib')]
from strict_ap_link import link,align,branch
RX,RW=0x8e90000,0x8eb0000
RX_CAPACITY=131072
# Formal4.36 already relocates the complete native PLT table to its RX tail.
# Two new dyn records occupy the first72 bytes; only the remaining original
# RX bytes may hold optional sound code. No new mapping or VA alias is added.
EXTRA_RX,EXTRA_BYTES=0x16d3ba0,22392
NATIVE_SHA={'r5sound_sha256_init':0x16d9a50,'r5sound_sha256_update':0x16d97f0,'r5sound_sha256_final':0x16d9970}
SOURCES=('r5_runtime_session.c','r5_stage413_thread.c','r5_grid420_log.c','r5_stage411_hooks.c','r5_stage413_probe.c','r5_stage413_transfer.c','r5_stage413_transfer_core.c','r5_native_transport_pie.c','r5_stage410_codec.c','r5_fsys_adapter.c','r5_scan_gate.c','sd_native_store.c','sd_native_persist.c','r5_lut_directory.c','r5_native_lut_directory.c','r5_lut_mount_guard.c','r5_filter_names423.c','r5_filter_selection423.c','r5_filter_runtime423.c','r5_filter_menu423.c','r5_filter_renderer423.c','r5_filter_renderer423.S')
def main():
 objdir=HERE/'objects';objdir.mkdir(exist_ok=True)
 native=json.loads((HERE.parent/'dependencies/native_bindings.json').read_text())
 menu_plan=json.loads((HERE.parent/'menu_research/menu_hooks.json').read_text())
 for directory in (HERE,HERE.parent/'menu_research'):
  extra=directory/'native_extra425.json'
  if extra.exists():
   plan=json.loads(extra.read_text());menu_plan['native_symbols'].update(plan.get('native_symbols',{}))
   menu_plan['calls']+=plan.get('calls',[])
   menu_plan['relocation_addend_remaps']+=plan.get('relocation_addend_remaps',[])
 native.update(menu_plan['native_symbols'])
 commands=[];objects=[]
 sources=[HERE.parent/'menu_research'/name if name.startswith(('r5_filter_menu423.','r5_filter_renderer423.')) else HERE/name for name in SOURCES]
 sources+=sorted((HERE.parent/'menu_research').glob('*425.c'))+sorted((HERE.parent/'menu_research').glob('*425.S'))
 sources+=sorted(HERE.glob('*425.c'))+sorted(HERE.glob('*425.S'))
 sources+=[HERE.parent/'menu_research/r5_filter_menu_icon434.S']
 sound_sources=[HERE.parent/'menu_research/r5_sound_menu437.c']
 sound_sources+=sorted(HERE.glob('r5sound_*.c'))
 sound_sources+=[HERE/name for name in ['r5_shutter_ap.c','r5_shutter_backend_native.c','r5_shutter_bridge_native.c','r5_shutter_scheduler.c']]
 # Compile sound implementation as one TU so Clang's existing merge/outliner
 # can share only newly added helpers. Baseline4.36 objects are unchanged.
 # Menu stays a root object; the amalgam is dependency-GC eligible as before.
 sound_menu=sound_sources[0];sound_implementation=sound_sources[1:]
 amalgam=objdir/'r5sound_all.c'
 amalgam.write_text(''.join('#include "'+str(source.resolve())+'"\n' for source in sound_implementation))
 sources+=[sound_menu,amalgam]
 compile_sound=[sound_menu,amalgam]
 for source in sources:
  name=source.name
  obj=objdir/(Path(name).stem+('_asm' if Path(name).suffix=='.S' else '')+'.o');command=['clang','--target=aarch64-none-elf','-Oz','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-ffunction-sections','-fdata-sections','-mno-outline-atomics','-mllvm','-enable-machine-outliner=always','-mllvm','-machine-outliner-reruns=2','-mllvm','-enable-merge-functions','-Wall','-Wextra','-Werror','-I',str(HERE)]
  if source in compile_sound:
   command+=['-mllvm','-enable-merge-functions','-DR5SS_SHARED_MEMSET','-fno-jump-tables','-Wno-misleading-indentation','-I',str(HERE/'include')]
  if source==amalgam:command+=['-DR5SS_NATIVE_SHA256']
  if Path(name).suffix!='.S':command+=['-std=c11']
  if name.endswith('425.c'):command+=['-fno-jump-tables']
  if name!='r5_stage411_hooks.c':command+=['-mgeneral-regs-only']
  command+=['-c',str(source),'-o',str(obj)]
  subprocess.run(command,check=True);commands.append(command);objects.append(obj)
 extra_output={};section_gc={}
 extra_objects=[obj for source,obj in zip(sources,objects)if source in compile_sound]
 gc_objects=[obj for obj in extra_objects if obj.name!='r5_sound_menu437.o']
 code,data,memory,sy,rels,layout=link(objects,RX,RW,bytes(align(8*56,16)),{**native,**NATIVE_SHA,'r5_stage411_dlsym':0x16dac90,'r5_native_fsys_open':0x3691104,'r5_native_fsys_write':0x3691174,'r5_native_fsys_read':0x3691138,'r5_native_fsys_close':0x3691124,'name_id':0x16db4f0,'name_char':0x16d9370,'r5_native_creative_sequence_request':0x24b0780},gc_objects=gc_objects,gc_report=section_gc,extra_rx_objects=extra_objects,extra_rx_base=EXTRA_RX,extra_rx_size=EXTRA_BYTES,extra_rx_output=extra_output,merge_strings=True,
  drop_unused_functions=('r5_publish_staged_look','r5_stage_look_store','r5_filter_reload_request','r5_transfer_ap_active_mask','r5_session_finish','r5_session_event_epoch','r5ss_backend_session'))
 assert not data and 0<memory<=196608 and align(len(code),8)+22464+64<=RX_CAPACITY,(len(code),memory,len(extra_output['data']))
 assert all(r['kind']!=257 for r in rels)
 hooks=[('startup',0x18012e4,'60a26e39'),('initial',0x34dae68,'60c21091'),('completed',0x34e5140,'60c21091'),('media',0x33c3cd4,'a003168b'),('inbound',0x3554d4c,'20008052'),('power',0x35b2a78,'fd7bbba9')]
 code=bytearray(code)
 for name,site,expected in hooks:
  sym='r5_stage411_'+name+'_hook';section=next(x for x in layout if x['name']=='.text.'+sym);lo=sy[sym]-RX
  nops=[i for i in range(lo,lo+section['size'],4)if code[i:i+4]==bytes.fromhex('1f2003d5')]
  assert len(nops)==(2 if name=='inbound'else 1)
  for off,dest in zip(nops,[0x3554ec8,0x3554d50]if name=='inbound'else[site+4]):code[off:off+4]=branch(RX+off,dest)
 menu_hooks=[dict(name='custom_menu_'+r['symbol'],site=int(r['va'],16),before=r['before'],after=branch(int(r['va'],16),sy[r['symbol']],r.get('link',True)).hex())for r in menu_plan['calls']]
 (HERE/'runtime_rx.bin').write_bytes(code)
 (HERE/'runtime_extra_rx.bin').write_bytes(extra_output['data'])
 report=dict(schema='r5-native12-ap-module/2',version='4.55-sound-recovery',rx=RX,rw=RW,rx_bytes=len(code),bss_bytes=memory,headers_reserved=448,extra_rx_base=EXTRA_RX,extra_rx_capacity=EXTRA_BYTES,extra_rx_bytes=len(extra_output['data']),section_gc=section_gc,commands=commands,symbols=sy,relocations=rels,sections=layout,hooks=[dict(name=n,site=s,before=b,after=branch(s,sy['r5_stage411_'+n+'_hook']).hex())for n,s,b in hooks]+menu_hooks,menu_relocation_addend_remaps=menu_plan['relocation_addend_remaps'],sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(set(sources)-{amalgam}|set(sound_implementation)|set(HERE.glob('*.h'))|set((HERE.parent/'menu_research').glob('*.h'))|{Path(__file__),HERE/'build_ap_image.py',ROOT/'lib/strict_ap_link.py'})},limitations=['Compile/link proof only. No AP loader/device/menus or native overwrite proof.'])
 (HERE/'module_audit.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k]for k in ('rx_bytes','bss_bytes','hooks')}))
if __name__=='__main__':main()
