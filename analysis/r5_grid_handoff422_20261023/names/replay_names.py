"""Exact integrated AP hook/name lookup replay. Native drawing is an ABI boundary.
No camera/filesystem access. Transfer state is controlled; not a SEAL test.
"""
from pathlib import Path
import hashlib,json,struct,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from elf_study import Image
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm64_const import *
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 j=json.loads((OUT.parent/'import/module_audit.json').read_text());sy=j['symbols']
 path=OUT.parent/'ap/appFw.so';im=Image(path);raw=im.data
 entry=0x1885b38;stop=entry+4;name_id=0x16db4f0;name_char=0x16d9370;rx=j['rx'];rw=j['rw'];state=sy['r5_stage413_transfer_state'];lookset=0x9000000;stack=0xa010000
 assert im.read(entry,4)==bytes.fromhex(next(p['after']for p in j['hooks']if p['name']=='native12_name'))
 u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
 for a,n in [(rx,0x10000),(rw,0x10000),(entry&-4096,4096),(0x16d9000,0x4000),(lookset,0x4000),(stack-65536,65536)]:u.mem_map(a,n)
 u.mem_write(rx,im.read(rx,j['rx_bytes']));u.mem_write(entry,im.read(entry,4))
 ids=[0x21c6e0d,0x21c6e10,0x21c6e14,0x21c6e19,0x21c6e0e,0x21c6e0c,0x21c6e0b,0x21c6e0a,0x21c6e11,0x21c6e12,0x21c6e15,0x21c6e13]
 names=['Native'+str(n)for n in range(1,13)];names[6]='胶片二号';names[7]='Filmé';names[8]='🎞Look'
 for i,n in enumerate(names):u.mem_write(lookset+4+i*1172,n.encode()+b'\0')
 immutable=bytes(u.mem_read(lookset,0x4000));observed=[];writes=[]
 def code(cpu,at,size,arg):
  if at in (name_id,name_char):
   observed.append((at,cpu.reg_read(UC_ARM64_REG_X0),cpu.reg_read(UC_ARM64_REG_X1)));cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_LR))
 def write(cpu,kind,at,size,val,arg):
  assert stack-65536<=at<stack,(hex(at),size)
 u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
 regs=[UC_ARM64_REG_X19+i for i in range(10)]+[UC_ARM64_REG_FP]
 def run(resource,mask,matched=1,phase=4,pointer=lookset):
  # host-controlled final publication state; these are not emulated ACKs.
  u.mem_write(state+16,struct.pack('<I',matched));u.mem_write(state+32,struct.pack('<Q',pointer));u.mem_write(state+44,struct.pack('<I',mask));u.mem_write(state+60,struct.pack('<I',phase))
  before=[0x12345600+n for n in range(len(regs))]
  for r,v in zip(regs,before):u.reg_write(r,v)
  u.reg_write(UC_ARM64_REG_X0,0x22228888);u.reg_write(UC_ARM64_REG_X1,resource);u.reg_write(UC_ARM64_REG_SP,stack);u.reg_write(UC_ARM64_REG_LR,0xbad);observed.clear()
  u.emu_start(entry,stop,count=250)
  assert u.reg_read(UC_ARM64_REG_PC)==stop and u.reg_read(UC_ARM64_REG_SP)==stack
  assert [u.reg_read(r)for r in regs]==before
  assert len(observed)==1 and observed[0][1]==0x22228888
  n=ids.index(resource)+1 if resource in ids else 0
  expected=name_char if n and matched and pointer and phase==4 and mask&(1<<(n-1)) else name_id
  assert observed[0][0]==expected
  assert observed[0][2]==(lookset+4+(n-1)*1172 if expected==name_char else resource)
 cases=0
 for mask in range(4096):
  for resource in ids:run(resource,mask);cases+=1
 for resource in [0,1,0xffffffff,0x2000713,0x200093b,0x21c6e09,0x21c6e16,0x21c6e18,0x200a302]:
  run(resource,4095);cases+=1
 for resource in ids:
  for phase in [0,1,2,3,5,6]:run(resource,4095,phase=phase);cases+=1
  run(resource,4095,matched=0);run(resource,4095,pointer=0);cases+=2
 assert bytes(u.mem_read(lookset,0x4000))==immutable
 out=dict(schema='r5-native12-integrated-AP-name-replay/1',passed=True,camera_io=False,AP_path=str(path.relative_to(ROOT)),AP_sha256=sha(raw),module_sha256=sha((OUT.parent/'import/runtime_rx.bin').read_bytes()),cases=cases,all4096Masks=True,real_installed_BL=True,real_name_lookup_and_phase_mask_checks=True,callee_saved_SP_preserved=True,no_nonstack_emulated_writes=True,lookset_immutable=True,UTF8_pointer_identity_verified=True,limits=['Publication state is host prepared; actual transfer/SEAL tested separately.','Native TextSprite overloads are recorded ABI boundaries, not executed drawing code.','Glyph coverage, layout truncation, actual menu navigation and raster icons remain untested.'])
 (OUT/'integrated_replay.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
if __name__=='__main__':main()
