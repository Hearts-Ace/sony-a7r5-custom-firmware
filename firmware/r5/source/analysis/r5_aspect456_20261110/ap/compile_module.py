#!/usr/bin/env python3
"""Build standalone R5 aspect candidate code/data; never edits an AP or DAT."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'projects/firmware/development/shutter-sound-recovery455/src/lib'))
from strict_ap_link import link
NATIVE={
 'r5_native_aspect_rows':0x3f46600,
 'r5_native_aspect_get':0x1c448dc,
 'r5_native_aspect_set':0x1c61d14,
 'r5_native_aspect_commit':0x1c93d88,
 'r5_native_aspect_send':0x355882c,
 'r5_native_row_insert':29957780,
 'r5_stage411_dlsym':0x16dac90,
 'r5_aspect_freeze_continue':0x3565f7c,
 'r5_aspect_native_apply_continue':0x1bc7724,
 'r5_aspect_native_size_continue':0x1bcfd1c,
 'r5_aspect_original_rows_register':0x8e9770c,
 'r5_aspect_original_row_normalize':0x8e97798,
 'r5_aspect_original_row_available':0x8e977d0,
 'r5_aspect_original_row_available_direct':0x8e97864,
 'r5_aspect_original_row_parent':0x8e978a4,
}
SOURCES=['r5_aspect_state.c','r5_aspect_menu.c','r5_aspect_persist.c','r5_aspect_wire.S']
def build(out,rx=0x8ee1000,rw=0x8ef0000):
 if out.exists():raise ValueError('Output must be a new directory')
 out.mkdir(parents=True)
 objects=[];commands=[]
 for name in SOURCES:
  source=HERE/name;obj=out/(source.stem+'.o')
  cmd=['clang','--target=aarch64-none-elf','-Oz','-ffreestanding','-fno-builtin',
       '-fno-stack-protector','-fno-unwind-tables','-ffunction-sections',
       '-fdata-sections','-mno-outline-atomics','-Wall',
       '-Wextra','-Werror','-I',str(HERE)]
  if source.suffix=='.c':cmd+=['-std=c11','-mgeneral-regs-only']
  cmd+=['-c',str(source),'-o',str(obj)]
  subprocess.run(cmd,check=True);commands.append(cmd);objects.append(obj)
 code,data,memory,symbols,rels,layout=link(objects,rx,rw,b'',NATIVE)
 (out/'rx.bin').write_bytes(code);(out/'rw.bin').write_bytes(data)
 report=dict(schema='r5-aspect-candidate-module/1',status='NONINSTALLABLE_COMPONENT',
   rx=rx,rw=rw,rx_bytes=len(code),rw_file_bytes=len(data),rw_memory_bytes=memory,
   symbols=symbols,relocations=rels,sections=layout,native_symbols=NATIVE,
   commands=commands,sources={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest()
                             for n in SOURCES+['r5_aspect_state.h']},
   limitations=['No AP mutation or firmware package generated',
                'Native callbacks and lifecycle need full integration verification'])
 (out/'module.json').write_text(json.dumps(report,indent=2)+'\n')
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
 p.add_argument('--rx',type=lambda x:int(x,0),default=0x8ee1000)
 p.add_argument('--rw',type=lambda x:int(x,0),default=0x8ef0000)
 a=p.parse_args();report=build(a.output,a.rx,a.rw)
 print(json.dumps({k:report[k] for k in ('rx_bytes','rw_file_bytes','rw_memory_bytes')}))
