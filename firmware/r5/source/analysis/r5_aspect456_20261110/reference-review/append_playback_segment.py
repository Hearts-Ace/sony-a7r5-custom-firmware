#!/usr/bin/env python3
"""Append exact preview playback helpers to a caller SHA-bound final AP.
No aspect menu descriptors, dynamic relocations, constructors or prior modules change.
"""
from pathlib import Path
import argparse,hashlib,io,json,struct,subprocess,sys
H=Path(__file__).resolve().parent;ROOT=H.parents[2]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'projects/firmware/development/shutter-sound-recovery455/src/lib')]
from strict_ap_link import link,branch
from elftools.elf.elffile import ELFFile
SHA=lambda d:hashlib.sha256(d).hexdigest()
EXTERNALS=dict(aspect_native_still_size_body=0x2dbf3b4,aspect_playback_badge_continue=0x23de63c,
 aspect_playback_pixels_continue=0x23dfa34,aspect_playback_pixels_store=0x23dfa28,
 aspect_native_zoom_map=0x2dbf7f0,aspect_native_zoom_policy_descriptor=0x53db910,
 aspect_native_zoom_policy_continue=0x24906a0,aspect_native_zoom_domain_continue=0x2492234,
 aspect_native_current_content=0x28a0a08,aspect_model_lock=0x2e7d208,aspect_model_unlock=0x2e7cee4)
HOOKS=[(0x2dbf3b0,'aspect_native_still_size',False,'fd7bbfa9'),
 (0x23de638,'aspect_playback_badge',False,'00008012'),
 (0x23dfa30,'aspect_playback_pixels',False,'031c8252'),
 (0x30c6f1c,'aspect_playback_zoom_map',True,branch(0x30c6f1c,0x2dbf7f0,True).hex()),
 (0x249069c,'aspect_playback_zoom_policy',False,'020c80b9'),
 (0x2492230,'aspect_playback_zoom_domain',False,'f30b40f9')]
def build(base,expected,out):
 raw=base.read_bytes();assert SHA(raw)==expected,'base SHA mismatch'
 out.mkdir(parents=True,exist_ok=False);module=out/'module';module.mkdir()
 elf=ELFFile(io.BytesIO(raw));segs=list(elf.iter_segments());assert elf['e_machine']=='EM_AARCH64'
 def off(va,n=4):
  for s in segs:
   if s['p_type']=='PT_LOAD' and s['p_vaddr']<=va and va+n<=s['p_vaddr']+s['p_filesz']:return s['p_offset']+va-s['p_vaddr']
  raise ValueError(('Unmapped',hex(va)))
 align=lambda n:(n+65535)&-65536
 owners=[(i,s)for i,s in enumerate(segs)if s['p_type']=='PT_LOAD' and s['p_vaddr']==0x8ee0000 and s['p_flags']==5]
 assert len(owners)==1,'Requires isolated aspect RX segment at 8ee0000'
 index,owner=owners[0];assert owner['p_filesz']==owner['p_memsz']
 start=(owner['p_vaddr']+owner['p_filesz']+15)&-16
 rx=start-4096
 objects=[];commands=[];sources={}
 for name in ('ap_still_size.S','ap_playback_badge.S','ap_playback_pixels.S','ap_playback_zoom.S'):
  src=H/'source'/name;obj=module/(src.stem+'.o');cmd=['clang','--target=aarch64-none-elf','-c',str(src),'-o',str(obj)]
  subprocess.run(cmd,check=True,capture_output=True);objects.append(obj);commands.append(cmd);sources[str(src.relative_to(ROOT))]=SHA(src.read_bytes())
 code,rw,mem,sy,relocs,layout=link(objects,rx+4096,rx+65536,b'',EXTERNALS)
 assert not rw and not mem and len(code)<61440 and all(r['kind']!=257 for r in relocs)
 image=bytearray(raw);patches=[]
 def edit(at,data,expect):
  assert raw[at:at+len(data)]==expect,('Before mismatch',hex(at));image[at:at+len(data)]=data
  patches.append(dict(offset=at,before=expect.hex(),after=data.hex()))
 for va,sym,bl,before in HOOKS:edit(off(va),branch(va,sy[sym],bl),bytes.fromhex(before))
 assert raw[off(0x434eab8,12):off(0x434eab8,12)+12]==struct.pack('<III',0x5041,0x5049,0)
 edit(off(0x434eabc),struct.pack('<I',0x507a),struct.pack('<I',0x5049))
 rxfile=owner['p_offset'];codefile=rxfile+start-owner['p_vaddr']
 newsize=start-owner['p_vaddr']+len(code)
 later=[s for s in segs if s['p_type']=='PT_LOAD' and s['p_vaddr']>owner['p_vaddr']]
 assert later and owner['p_vaddr']+newsize<=min(s['p_vaddr']for s in later),'Module exceeds virtual RX padding'
 assert codefile+len(code)<=min(s['p_offset']for s in later),'Module exceeds file padding'
 assert raw[codefile:codefile+len(code)]==bytes(len(code)),'RX padding is not zero'
 edit(codefile,code,bytes(len(code)))
 phoff=elf['e_phoff']+index*56
 edit(phoff+32,struct.pack('<QQ',newsize,newsize),struct.pack('<QQ',owner['p_filesz'],owner['p_memsz']))
 reverse=bytearray(image[:len(raw)])
 for p in reversed(patches):reverse[p['offset']:p['offset']+len(bytes.fromhex(p['before']))]=bytes.fromhex(p['before'])
 assert reverse==raw
 newelf=ELFFile(io.BytesIO(image))
 for name in('.dynamic','.rela.dyn','.rela.plt','.dynsym','.dynstr','.init_array','.fini_array'):
  assert elf.get_section_by_name(name).data()==newelf.get_section_by_name(name).data(),name
 target=out/'appFw-NONINSTALLABLE.so';target.write_bytes(image)
 report=dict(status='NONINSTALLABLE_AP_PLAYBACK',base_sha256=expected,sha256=SHA(image),bytes=len(image),
  RX=owner['p_vaddr'],code_start=start,rx_file=rxfile,code_bytes=len(code),symbols=sy,sources=sources,commands=commands,
  relocations=relocs,layout=layout,patches=patches,reverse_exact=True,raw_crop_hooks=[],current_ratios=['1.618:1','2.39:1','5:4','1.85:1'],
  hook_contract=[dict(va=hex(va),symbol=sym,kind='BL'if bl else'B',before=before)for va,sym,bl,before in HOOKS],
  resource_ids=['0x02001e9c','0x02001e9d','0x02001e9e','0x02001e8d','0x02001e8e','0x02001e8f'],
  program_header_count_unchanged=True,dynamic_tables_unchanged=True,camera_io=False,device_tested=False)
 (module/'rx.bin').write_bytes(code);(out/'patch.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k]for k in('sha256','bytes','code_bytes','reverse_exact')}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--base-sha256',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();build(a.base,a.base_sha256,a.output)
