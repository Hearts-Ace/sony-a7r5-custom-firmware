"""Narrow 4.24 AP repair on the frozen final 4.23 AP. No device I/O.

The secondary menu-ID map omits the private MID. Preserve its identity before
visible-row production; all other IDs replay the original ADRP and lookup.
"""
from pathlib import Path
import hashlib,io,json,os,shutil,struct,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from elftools.elf.elffile import ELFFile
from build_corrected_fl2_fl3 import geometry,digest_file
BASE=ROOT/'analysis/r5_custom_filter423_20261023'
AP_SHA='4017b746b8720b0b3c0b1b8d79b00472548361b335048656b72c71be77202717'
CP_SHA='8b38e753f34b1667d79b69079d911b9e6595f1ce1b873cb8e014437c6b4c494d'
sha=lambda b:hashlib.sha256(b).hexdigest()
def branch(pc,to):
 d=to-pc;assert d%4==0 and -(1<<27)<=d<(1<<27)
 return 0x14000000|((d//4)&0x3ffffff)
def adrp(pc,to,rd):
 d=(to//4096)-(pc//4096);assert -(1<<20)<=d<(1<<20)
 return 0x90000000|((d&3)<<29)|(((d>>2)&0x7ffff)<<5)|rd
def main():
 out=HERE/'ap';out.mkdir(exist_ok=True)
 original=(BASE/'ap/appFw.so').read_bytes();assert sha(original)==AP_SHA
 assert digest_file(BASE/'cp/cp423.NONINSTALLABLE.bin')==CP_SHA
 elf=ELFFile(io.BytesIO(original));raw=bytearray(original);edits=[]
 def offset(va,n):
  found=[s['p_offset']+va-s['p_vaddr'] for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=va and va+n<=s['p_vaddr']+s['p_filesz']]
  assert len(found)==1,(hex(va),n);return found[0]
 def edit(at,data,label,expected):
  assert raw[at:at+len(data)]==expected,label
  assert not any(at<e['offset']+e['bytes'] and e['offset']<at+len(data) for e in edits)
  raw[at:at+len(data)]=data
  edits.append(dict(offset=at,bytes=len(data),before=expected.hex(),after=data.hex(),purpose=label))
 index,rx=next((i,s) for i,s in enumerate(elf.iter_segments()) if s['p_type']=='PT_LOAD' and s['p_vaddr']==0x8e90000)
 assert rx['p_filesz']==rx['p_memsz'] and rx['p_flags']==5
 code_end=(rx['p_filesz']+15)&-16;wrapper=rx['p_vaddr']+code_end
 entry=0x1bd2020
 words=[0x7100003f|(0x635<<10),0x54000061,0x2a0103e0,0xd65f03c0,
        adrp(wrapper+16,0x5959000,0),branch(wrapper+20,entry+4)]
 code=struct.pack('<6I',*words)
 at=rx['p_offset']+code_end;newsize=code_end+len(code)
 assert newsize<=65536 and at+len(code)<=len(raw)
 # This page tail was reserved by the 4.23 image builder. No filesystem growth.
 assert original[rx['p_offset']+rx['p_filesz']:at+len(code)]==bytes(newsize-rx['p_filesz'])
 edit(at,code,'Secondary menu identity only MID635; PC-correct original fallback',bytes(len(code)))
 edit(offset(entry,4),struct.pack('<I',branch(entry,wrapper)),'Secondary resolver detour',bytes.fromhex('20ec01f0'))
 phoff=elf['e_phoff']+index*elf['e_phentsize']+32
 edit(phoff,struct.pack('<QQ',newsize,newsize),'Map appended wrapper RX bytes',struct.pack('<QQ',rx['p_filesz'],rx['p_memsz']))
 reverse=bytearray(raw)
 for e in reversed(edits):reverse[e['offset']:e['offset']+e['bytes']]=bytes.fromhex(e['before'])
 assert reverse==original
 # Every other byte, including complete 4.23 module, names, storage and CP,
 # remains from the exact tested 4.23 delivery. Existing relocations unchanged.
 final=ELFFile(io.BytesIO(raw))
 for name in ('.rela.dyn','.rela.plt','.dynamic','.dynsym','.dynstr'):
  assert final.get_section_by_name(name).data()==elf.get_section_by_name(name).data()
 (out/'appFw.so').write_bytes(raw)
 part=BASE/'ap/nflasha15';baseline=json.loads((BASE/'ap/ap_build.json').read_text())
 assert digest_file(part)==baseline['partition_sha256']
 old,offsets,unit,meta=geometry(part,'appFw.so');assert old==original
 target=out/'nflasha15';shutil.copyfile(part,target)
 with target.open('r+b') as f:
  for i,loc in enumerate(offsets):f.seek(loc);f.write(raw[i*unit:(i+1)*unit])
  f.flush();os.fsync(f.fileno())
 reread,o,u,m=geometry(target,'appFw.so');assert reread==raw and (o,u,m)==(offsets,unit,meta)
 spans=sorted((loc,loc+min(unit,len(raw)-i*unit)) for i,loc in enumerate(offsets))
 with part.open('rb') as a,target.open('rb') as b:
  cursor=0
  for lo,hi in spans:assert a.read(lo-cursor)==b.read(lo-cursor);a.seek(hi);b.seek(hi);cursor=hi
  assert a.read()==b.read()
 fsck=subprocess.run(['/opt/homebrew/opt/e2fsprogs/sbin/e2fsck','-f','-n',str(target)],capture_output=True,text=True)
 (out/'e2fsck.log').write_text(fsck.stdout+fsck.stderr);assert fsck.returncode==0
 report=dict(passed=True,version='4.24',AP_sha256=sha(raw),CP_sha256=CP_SHA,bytes=len(raw),
  base_AP_sha256=AP_SHA,base_partition_sha256=digest_file(part),partition_sha256=digest_file(target),
  patch_only_from_423=True,reverse423_exact=True,changes=edits,
  secondary_resolver=hex(entry),secondary_identity_mid='0x635',secondary_wrapper=hex(wrapper),
  wrapper_hex=code.hex(),rx_file=rx['p_offset'],rx_bytes=newsize,
  original_rx_bytes=rx['p_filesz'],only_AP_payload_changed=True,
  native_readonly_e2fsck_passed=True,relocations_dynamic_symbols_unchanged=True,
  custom_filter423_payload_preserved=True,camera_IO=False)
 (out/'ap_build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
