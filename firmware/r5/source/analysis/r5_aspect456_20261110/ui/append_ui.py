#!/usr/bin/env python3
"""Append the explicit AP+five-page-UI contract to exact4.55, without packaging.

The reviewed contract is deliberately external: missing menu integration or
before-bytes fails closed. Output is a NONINSTALLABLE research component.
"""
from pathlib import Path
import argparse,hashlib,io,json,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'projects/firmware/development/shutter-sound-recovery455/src/lib')]
from elftools.elf.elffile import ELFFile
from strict_ap_link import branch

BASE_SHA='23f5b11d8f79c7c984fc42a4e6d2cac9dc5b5d74bb327b3b36e77985112f3bf6'
RX=0x8ee0000;CODE=RX+0x1000;RW=0x8ef0000
def sha(raw):return hashlib.sha256(raw).hexdigest()
def align(value,alignment=0x10000):return(value+alignment-1)&-alignment

def build(base,module,contract,out):
 raw=base.read_bytes();assert sha(raw)==BASE_SHA,'Requires exact sound-recovery455 AP'
 report=json.loads((module/'module.json').read_text());sy=report['symbols']
 assert(report['rx'],report['rw'])==(CODE,RW),'Module address does not match isolated append'
 code=(module/'rx.bin').read_bytes();data=(module/'rw.bin').read_bytes()
 assert len(code)==report['rx_bytes']and len(data)==report['rw_file_bytes']
 assert len(code)<RW-CODE and report['rw_memory_bytes']>0
 for path,expected in report['sources'].items():assert sha((ROOT/path).read_bytes())==expected,('Source drift',path)
 plan=json.loads(contract.read_text())
 assert plan['base_sha256']==BASE_SHA and plan['status']=='REVIEWED_AP_CONTRACT'
 assert plan['complete_menu_contract']is True,'Partial menu contract cannot be applied'
 e=ELFFile(io.BytesIO(raw));assert e['e_machine']=='EM_AARCH64'and e['e_type']=='ET_DYN'and e['e_phnum']==8
 headers=[dict(s.header)for s in e.iter_segments()]
 oldloads=[s for s in headers if s['p_type']=='PT_LOAD']
 assert max(s['p_vaddr']+s['p_memsz']for s in oldloads)<=RX
 # No ABS64 support: all module addresses are derived from ADRP/ADD or branch
 # instructions, and initialized pointer objects are built by runtime code.
 assert all(row['kind']!=257 for row in report['relocations'])
 rxfile=align(len(raw));rwfile=align(rxfile+0x1000+len(code))
 image=bytearray(raw);image.extend(bytes(rxfile-len(raw)))
 image.extend(bytes(0x1000));image.extend(code);image.extend(bytes(rwfile-len(image)))
 image.extend(data)
 changes=[]
 def edit(offset,after,reason):
  before=bytes(image[offset:offset+len(after)]);assert len(before)==len(after)
  if before==after:return
  image[offset:offset+len(after)]=after
  changes.append(dict(offset=offset,before=before.hex(),after=after.hex(),reason=reason))
 def file_at(va,n=1):
  for s in headers:
   if s['p_type']=='PT_LOAD'and s['p_vaddr']<=va and va+n<=s['p_vaddr']+s['p_filesz']:
    return s['p_offset']+va-s['p_vaddr']
  raise ValueError(('Unbacked VA',hex(va),n))
 types={'PT_LOAD':1,'PT_DYNAMIC':2,'PT_GNU_EH_FRAME':0x6474e550,'PT_GNU_STACK':0x6474e551,'PT_GNU_RELRO':0x6474e552}
 def ph(h):return struct.pack('<II6Q',types[h['p_type']],h['p_flags'],*[h[k]for k in('p_offset','p_vaddr','p_paddr','p_filesz','p_memsz','p_align')])
 phdrs=b''.join(ph(h)for h in headers)
 phdrs+=struct.pack('<II6Q',1,5,rxfile,RX,RX,0x1000+len(code),0x1000+len(code),0x10000)
 phdrs+=struct.pack('<II6Q',1,6,rwfile,RW,RW,len(data),report['rw_memory_bytes'],0x10000)
 assert len(phdrs)==560
 image[rxfile:rxfile+len(phdrs)]=phdrs
 edit(32,struct.pack('<Q',rxfile),'Relocate PHDR array into the new immutable RX segment')
 edit(56,struct.pack('<H',10),'Append isolated RX and RW PT_LOAD entries')
 assert len({int(p['va'],0) for p in plan['patches']})==len(plan['patches']), 'Overlapping patch contract'
 applied=[]
 for row in plan['patches']:
  va=int(row['va'],0);kind=row['kind'];before=bytes.fromhex(row['before'])
  at=file_at(va,len(before));assert bytes(image[at:at+len(before)])==before,('Native source mismatch',row)
  if kind in('B','BL'):
   assert len(before)==4
   after=branch(va,sy[row['symbol']],kind=='BL')
  elif kind=='BYTES':after=bytes.fromhex(row['after']);assert len(after)==len(before)
  else:raise ValueError(('Unknown patch kind',kind))
  edit(at,after,row['reason']);applied.append(row)
 rel=e.get_section_by_name('.rela.dyn');entries=list(struct.iter_unpack('<QQq',rel.data()))
 index={address:(i,info,addend)for i,(address,info,addend)in enumerate(entries)}
 for row in plan['rela_remaps']:
  va=int(row['va'],0);i,info,addend=index[va]
  assert info==1027 and addend==int(row['before_addend'],0),('RELA source mismatch',row)
  target=sy[row['symbol']]
  edit(rel['sh_offset']+i*24+16,struct.pack('<q',target),row['reason'])
 reverse=bytearray(image[:len(raw)])
 for row in reversed(changes):
  at=row['offset'];before=bytes.fromhex(row['before'])
  if at<len(raw):reverse[at:at+len(before)]=before
 assert bytes(reverse)==raw,'Reverse proof must restore exact455 prefix'
 final=ELFFile(io.BytesIO(image));newheaders=[dict(s.header)for s in final.iter_segments()]
 assert newheaders[:8]==headers and len(newheaders)==10
 loads=[s for s in newheaders if s['p_type']=='PT_LOAD']
 for s in loads:
  assert s['p_filesz']<=s['p_memsz']and(s['p_flags']&3)!=3
  assert s['p_offset']%65536==s['p_vaddr']%65536
 for left,right in zip(loads,loads[1:]):assert align(left['p_vaddr']+left['p_memsz'])<=right['p_vaddr']
 for name in('.dynsym','.dynstr','.init_array','.fini_array','.rela.plt'):
  old,new=e.get_section_by_name(name),final.get_section_by_name(name)
  assert old.header==new.header and old.data()==new.data(),('Must remain exact',name)
 assert e.get_section_by_name('.dynamic').data()==final.get_section_by_name('.dynamic').data()
 out.mkdir(parents=True,exist_ok=False);(out/'appFw-NONINSTALLABLE.so').write_bytes(image)
 result=dict(status='NONINSTALLABLE_AP_COMPONENT',base_sha256=BASE_SHA,sha256=sha(image),bytes=len(image),
  prefix_reverse_exact=True,source_module_sha256=sha((module/'module.json').read_bytes()),contract_sha256=sha(contract.read_bytes()),
  rx=hex(RX),code=hex(CODE),rw=hex(RW),rx_file=rxfile,rw_file=rwfile,rx_bytes=len(code),rw_memory_bytes=report['rw_memory_bytes'],
  patches=changes,menu_contract=plan,ui_hooks=plan['ui_contract']['patches'],
  original_eight_PHDRs_exact=True,dynamic_tags_exact=True,original_init_array_exact=True,
  limitations=['No DAT or device IO','No full native startup, concurrent UI event loop or cancel persistence integration proved by append','Five-page UI is included; offline replay is separate from real LCD/device acceptance','CP/AVCAM crop integration and camera/JPEG pixels not validated here'])
 (out/'ap-append.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:result[k]for k in('status','sha256','bytes','prefix_reverse_exact','rx_bytes','rw_memory_bytes')}))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,default=ROOT/'projects/firmware/releases/4.55-sound-recovery-20261105/appFw.so')
 p.add_argument('--module',type=Path,required=True);p.add_argument('--contract',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();build(a.base,a.module,a.contract,a.output)
if __name__=='__main__':main()
