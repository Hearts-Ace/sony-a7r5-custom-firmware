#!/usr/bin/env python3
"""Build AP image/optional n15 from pinned 4.07 prefix and 4.13 partition.
No device IO, signature/DAT work, or installability assertion.
"""
from pathlib import Path
import json,struct,hashlib,io,sys,argparse,subprocess,os,shutil
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from elftools.elf.elffile import ELFFile
from build_corrected_fl2_fl3 import geometry,digest_file
import build_ap_module as module

def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--partition',action='store_true');a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=True)
 module.main();audit=json.loads((HERE/'module_audit.json').read_text());raw=(ROOT/'research/r5_custom_lut/build_r5_4.07_stage1_20261020/patched/appFw.so').read_bytes()
 assert sha(raw)=='a8d5cd444bf08a03a70aedc3cc32bdd857b89b468ac10bf8365d640e8d390d75'
 e=ELFFile(io.BytesIO(raw));assert e['e_phnum']==6
 code=bytearray((HERE/'runtime_rx.bin').read_bytes());memory=audit['bss_bytes'];RX=audit['rx'];RW=audit['rw'];rxfile=module.align(len(raw),65536);rwfile=module.align(rxfile+len(code),65536)
 types={'PT_LOAD':1,'PT_DYNAMIC':2,'PT_GNU_EH_FRAME':0x6474e550,'PT_GNU_STACK':0x6474e551,'PT_GNU_RELRO':0x6474e552}
 def ph(h):return struct.pack('<II6Q',types[h['p_type']],h['p_flags'],*[h[k]for k in ('p_offset','p_vaddr','p_paddr','p_filesz','p_memsz','p_align')])
 headers=b''.join(ph(s.header)for s in e.iter_segments())+struct.pack('<II6Q',1,5,rxfile,RX,RX,len(code),len(code),65536)+struct.pack('<II6Q',1,6,rwfile,RW,RW,0,memory,65536)
 assert len(headers)==448;code[:448]=headers
 image=bytearray(raw);image.extend(bytes(rxfile-len(image)));image.extend(code);image.extend(bytes(rwfile-len(image)))
 changes=[]
 for rec in audit['hooks']:
  at=rec['site'];before=bytes.fromhex(rec['before']);after=bytes.fromhex(rec['after']);assert image[at:at+len(before)]==before;image[at:at+len(after)]=after;changes.append(dict(offset=at,before=before.hex(),after=after.hex()))
 for at,after in [(32,struct.pack('<Q',rxfile)),(56,struct.pack('<H',8))]:
  changes.append(dict(offset=at,before=image[at:at+len(after)].hex(),after=after.hex()));image[at:at+len(after)]=after
 reverse=bytearray(image[:len(raw)])
 for c in changes:reverse[c['offset']:c['offset']+len(bytes.fromhex(c['before']))]=bytes.fromhex(c['before'])
 assert reverse==raw
 new=ELFFile(io.BytesIO(image));assert [dict(s.header)for s in list(new.iter_segments())[:6]]==[dict(s.header)for s in e.iter_segments()]
 loads=[s for s in new.iter_segments()if s['p_type']=='PT_LOAD']
 for s in loads:assert s['p_filesz']<=s['p_memsz']and s['p_offset']%65536==s['p_vaddr']%65536 and s['p_flags']&3!=3
 for x,y in zip(loads,loads[1:]):assert module.align(x['p_vaddr']+x['p_memsz'],65536)<=y['p_vaddr']
 for name in ('.dynamic','.dynsym','.dynstr','.rela.dyn','.rela.plt','.init_array','.fini_array'):
  x,y=e.get_section_by_name(name),new.get_section_by_name(name);assert(x is None and y is None)or(x.header==y.header and x.data()==y.data())
 (out/'appFw.so').write_bytes(image)
 report=dict(passed=True,AP_sha256=sha(image),bytes=len(image),reverse_to407_exact=True,module_audit_sha256=digest_file(HERE/'module_audit.json'),patches=changes,rx_file=rxfile,rw_file=rwfile,rx_bytes=len(code),bss_bytes=memory,device_IO=False)
 if a.partition:
  base=ROOT/'research/r5_custom_lut/build_r5_4.13_stage5c_20261021/patched/nflasha15';old,offsets,unit,meta=geometry(base,'appFw.so');assert sha(old)=='fab5e26de3c3ab7766c3f184dba678e2ccbb9175dbf978516ca1287a49627fba'
  assert len(old)==len(image),'No implicit filesystem growth permitted'
  target=out/'nflasha15';shutil.copyfile(base,target)
  with target.open('r+b')as f:
   for i,at in enumerate(offsets):
    block=image[i*unit:(i+1)*unit];f.seek(at);f.write(block)
   f.flush();os.fsync(f.fileno())
  actual,off2,un2,me2=geometry(target,'appFw.so');assert actual==image and offsets==off2 and unit==un2 and meta==me2
  # Independent native filesystem checker; no repair flag.
  fsck=subprocess.run(['/opt/homebrew/opt/e2fsprogs/sbin/e2fsck','-f','-n',str(target)],capture_output=True,text=True);(out/'e2fsck.log').write_text(fsck.stdout+fsck.stderr);assert fsck.returncode==0
  # Every byte outside AP physical units must remain exactly baseline.
  intervals=sorted((x,x+min(unit,len(image)-i*unit))for i,x in enumerate(offsets))
  with base.open('rb')as x,target.open('rb')as y:
   cursor=0
   for start,end in intervals:
    n=start-cursor;assert x.read(n)==y.read(n);x.seek(end);y.seek(end);cursor=end
   assert x.read()==y.read()
  report.update(partition_sha256=digest_file(target),partition_original_sha256=digest_file(base),only_AP_payload_changed=True,native_readonly_e2fsck_passed=True)
 (out/'ap_build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
