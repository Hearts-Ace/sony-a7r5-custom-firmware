#!/usr/bin/env python3
"""Compile the 4.13-derived native-12 importer. No camera or partition writes."""
from pathlib import Path
import sys,json,hashlib,subprocess,struct
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'research/r5_custom_lut/scripts'),str(ROOT/'vendor/audit-python'),str(ROOT/'research/r5_custom_lut/evidence/sd405_ap_native_directory_binding')]
from strict_ap_link import link,align,branch
RX,RW=0x8e90000,0x8ea0000
SOURCES=('r5_stage413_thread.c','r5_stage411_hooks.c','r5_stage413_probe.c','r5_stage413_transfer.c','r5_stage413_transfer_core.c','r5_native_transport_pie.c','r5_stage410_codec.c','r5_fsys_adapter.c','r5_scan_gate.c','sd_native_store.c','sd_native_persist.c','r5_lut_directory.c','r5_native_lut_directory.c','r5_lut_mount_guard.c','native12_names.c')
def main():
 objdir=HERE/'objects';objdir.mkdir(exist_ok=True)
 native=json.loads((ROOT/'research/r5_custom_lut/build_r5_4.13_stage5c_20261021/evidence/native_bindings.json').read_text())
 commands=[];objects=[]
 for name in SOURCES:
  source=HERE/name if name!='native12_names.c' else HERE.parent/'names'/name
  obj=objdir/(Path(name).stem+'.o');command=['clang','--target=aarch64-none-elf','-Oz','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-ffunction-sections','-fdata-sections','-mno-outline-atomics','-mllvm','-enable-machine-outliner=never','-Wall','-Wextra','-Werror','-I',str(HERE),'-std=c11']
  if name!='r5_stage411_hooks.c':command+=['-mgeneral-regs-only']
  command+=['-c',str(source),'-o',str(obj)]
  subprocess.run(command,check=True);commands.append(command);objects.append(obj)
 code,data,memory,sy,rels,layout=link(objects,RX,RW,bytes(align(8*56,16)),{**native,'r5_stage411_dlsym':0x16dac90,'r5_native_fsys_open':0x3691104,'r5_native_fsys_read':0x3691138,'r5_native_fsys_close':0x3691124,'name_id':0x16db4f0,'name_char':0x16d9370})
 assert not data and 0<memory<=65536 and len(code)<65536
 assert all(r['kind']!=257 for r in rels)
 hooks=[('startup',0x18012e4,'60a26e39'),('initial',0x34dae68,'60c21091'),('completed',0x34e5140,'60c21091'),('media',0x33c3cd4,'a003168b'),('inbound',0x3554d4c,'20008052')]
 code=bytearray(code)
 for name,site,expected in hooks:
  sym='r5_stage411_'+name+'_hook';section=next(x for x in layout if x['name']=='.text.'+sym);lo=sy[sym]-RX
  nops=[i for i in range(lo,lo+section['size'],4)if code[i:i+4]==bytes.fromhex('1f2003d5')]
  assert len(nops)==(2 if name=='inbound'else 1)
  for off,dest in zip(nops,[0x3554ec8,0x3554d50]if name=='inbound'else[site+4]):code[off:off+4]=branch(RX+off,dest)
 name_hook=dict(name='native12_name',site=0x1885b38,before='6e56f997',after=branch(0x1885b38,sy['r5_native12_text_label'],True).hex())
 (HERE/'runtime_rx.bin').write_bytes(code)
 report=dict(schema='r5-native12-ap-module/2',rx=RX,rw=RW,rx_bytes=len(code),bss_bytes=memory,headers_reserved=448,commands=commands,symbols=sy,relocations=rels,sections=layout,hooks=[dict(name=n,site=s,before=b,after=branch(s,sy['r5_stage411_'+n+'_hook']).hex())for n,s,b in hooks]+[name_hook],sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(list(HERE.glob('*'))+[HERE.parent/'names/native12_names.c'])if p.suffix in ('.c','.h','.py')},limitations=['Compile/link proof only. No AP loader/device/menus or native overwrite proof.'])
 (HERE/'module_audit.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k]for k in ('rx_bytes','bss_bytes','hooks')}))
if __name__=='__main__':main()
