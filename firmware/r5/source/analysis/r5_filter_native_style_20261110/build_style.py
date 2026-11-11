#!/usr/bin/env python3
"""Append a D9 display-only module to the isolated aspect AP segments."""
from pathlib import Path
import argparse,hashlib,io,json,struct,subprocess,sys
H=Path(__file__).resolve().parent;ROOT=H.parents[1]
sys.path[:0]=[str(ROOT/'projects/firmware/development/shutter-sound-recovery455/src/lib')]
from strict_ap_link import link,branch
from elftools.elf.elffile import ELFFile
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True)
 p.add_argument('--audit',type=Path,default=ROOT/'analysis/r5_aspect456_20261110/full/base455/work/import/module_audit.json')
 p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=False)
 raw=a.base.read_bytes();e=ELFFile(io.BytesIO(raw));segs=list(e.iter_segments());audit=json.loads(a.audit.read_text());native=dict(audit['symbols'])
 exported=['r5_filter_controller425','r5_filter_presenter425','r5_filter_parent_presenter425','r5_filter_page_text425',
           'r5_filter_parent_refresh425','r5sound_menu_event425','r5sound_menu_event2d6_443']
 for name in exported:native.pop(name,None)
 rxowner=next((i,s) for i,s in enumerate(segs) if s['p_type']=='PT_LOAD' and s['p_vaddr']==0x8ee0000)
 rwowner=next((i,s) for i,s in enumerate(segs) if s['p_type']=='PT_LOAD' and s['p_vaddr']==0x8ef0000)
 ri,rs=rxowner;wi,ws=rwowner;rx=(rs['p_vaddr']+rs['p_filesz']+15)&-16;rw=(ws['p_vaddr']+ws['p_memsz']+15)&-16
 sources=[H/n for n in ('r5_filter_page_style.c',)]
 objects=[];commands=[]
 for s in sources:
  obj=out/(s.name+'.o');cmd=['clang','--target=aarch64-none-elf','-Oz','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-mgeneral-regs-only','-fno-jump-tables','-ffunction-sections','-fdata-sections','-Wall','-Wextra','-Werror','-I',str(H),'-c',str(s),'-o',str(obj)]
  subprocess.run(cmd,check=True);commands.append(cmd);objects.append(obj)
 code,data,memory,sy,relocs,layout=link(objects,rx,rw,b'',native)
 assert not data and all(r['kind']!=257 for r in relocs)
 assert rx+len(code)<=ws['p_vaddr'] and rw+memory<=0x8f00000
 image=bytearray(raw);patches=[]
 def edit(at,new,reason):
  old=bytes(image[at:at+len(new)]);assert len(old)==len(new);image[at:at+len(new)]=new
  patches.append(dict(offset=at,before=old.hex(),after=new.hex(),reason=reason))
 def off(va,n=4):
  for s in segs:
   if s['p_type']=='PT_LOAD' and s['p_vaddr']<=va and va+n<=s['p_vaddr']+s['p_filesz']:return s['p_offset']+va-s['p_vaddr']
  raise ValueError(hex(va))
 at=rs['p_offset']+rx-rs['p_vaddr'];assert raw[at:at+len(code)]==bytes(len(code))
 edit(at,code,'New display-only page module in zero RX padding')
 newsize=rx+len(code)-rs['p_vaddr'];edit(e['e_phoff']+ri*56+32,struct.pack('<QQ',newsize,newsize),'Expand existing aspect RX only')
 edit(e['e_phoff']+wi*56+40,struct.pack('<Q',rw+memory-ws['p_vaddr']),'Private D9 view ownership BSS after aspect state')
 # Exact existing exported entry detours avoid changing generic resource callers
 # or worker references; all old callers resolve the new owned page state.
 for name in exported:
  if name in sy:
   va=audit['symbols'][name];edit(off(va),branch(va,sy[name]),'Redirect original '+name+' entry to display module')
 # Entry veneers also cover registration-created callbacks without changing
 # RELATIVE arrays. Functions are AAPCS compatible and preserve original flow.
 reverse=bytearray(image)
 for patch in reversed(patches):
  at=patch['offset'];reverse[at:at+len(bytes.fromhex(patch['before']))]=bytes.fromhex(patch['before'])
 assert reverse==raw
 (out/'appFw-NONINSTALLABLE.so').write_bytes(image);(out/'rx.bin').write_bytes(code)
 report=dict(passed=True,status='DISPLAY_CANDIDATE_NONINSTALLABLE',base_sha256=sha(a.base),sha256=hashlib.sha256(image).hexdigest(),
  rx=rx,rw=rw,rx_bytes=len(code),rw_memory_bytes=memory,symbols=sy,relocations=relocs,layout=layout,
  patches=patches,reverse_exact=True,old_program_header_count_unchanged=True,
  sources={s.name:sha(s) for s in sources+[H/'r5_filter_menu423.h',H/'r5_sound_menu437.h']},audit_sha256=sha(a.audit),commands=commands,
  scope='Private D9 using original aspect Fn style entries; left abbreviations and selected full name; original async path retained',
  device_tested=False,limits=['Pending independent native lifecycle/render output replay; no installable package'])
 (out/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('sha256','rx_bytes','rw_memory_bytes','reverse_exact')}))
if __name__=='__main__':main()
