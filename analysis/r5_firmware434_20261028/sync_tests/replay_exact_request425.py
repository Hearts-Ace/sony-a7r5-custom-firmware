"""Execute original current-look facade/factory/ctor/locked enqueue chain.

No original execute method is called in the caller task. Model property
services, allocation/base object construction and container internals remain
explicit fixtures; original guard call placement, snapshot loads, queue lock,
counter and condition wake instructions run unchanged.
"""
from pathlib import Path
import argparse,hashlib,io,json,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from elftools.elf.elffile import ELFFile
from elf_study import Image
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm64_const import *
RAM=0x10000000;MANAGER=RAM+0x10000;COMMAND=RAM+0x20000;REQUEST=RAM+0x21000;PROPERTY=RAM+0x22000;SP=RAM+0xf0000;STOP=RAM+0xff000
def main():
 p=argparse.ArgumentParser();p.add_argument('--bias',type=lambda v:int(v,0),required=True);p.add_argument('--output',required=True,type=Path);a=p.parse_args();bias=a.bias
 im=Image(HERE.parent/'ap/appFw.so');assert hashlib.sha256(im.data).hexdigest()==json.loads((HERE.parent/'ap/ap_build.json').read_text())['AP_sha256'];audit=json.loads((HERE.parent/'import/module_audit.json').read_text());ctor=audit['symbols']['r5_filter_refresh_construct425']
 u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
 for s in im.elf.iter_segments():
  if s['p_type']!='PT_LOAD':continue
  start=(s['p_vaddr']+bias)&-4096;end=(s['p_vaddr']+bias+s['p_memsz']+4095)&-4096;u.mem_map(start,end-start);u.mem_write(s['p_vaddr']+bias,s.data())
 u.mem_map(RAM,0x100000)
 for address in (0x5987648,0x594a2c0):u.mem_write(address+bias,struct.pack('<Q',im.pointer(address)+bias))
 assert int.from_bytes(im.read(im.pointer(0x594a2c0)+0xe4*4,4),'little')==0
 state={};cases=[]
 def ret(v=0):u.reg_write(UC_ARM64_REG_X0,v&((1<<64)-1));u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))
 def hook(cpu,pc,n,_):
  at=pc-bias;args=[cpu.reg_read(r)for r in (UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3)]
  if at==ctor:
   assert args[:2]==[COMMAND,REQUEST+16];state['events'].append('exact_request_pointer_ctor');cpu.reg_write(UC_ARM64_REG_PC,0x318e5c0+bias);return
  if at==0x348292c:raise AssertionError('Executing color command on importer caller task')
  if at==0x31a9d04:state['events'].append('singleton');ret(MANAGER);return
  if at==0x16dc130:assert args[0]==0x38;state['events'].append('allocate_command');ret(COMMAND);return
  if at==0x30c01dc:
   assert args[0]==COMMAND;state['events'].append('base_constructor_fixture');u.mem_write(COMMAND,bytes(0x38));ret();return
  if at==0x3552cfc:ret(2);return
  if at==0x2e7d208:state['events'].append('model_lock');state['model_locked']=True;ret();return
  if at==0x2e7cee4:assert state['model_locked'];state['events'].append('model_unlock');state['model_locked']=False;ret();return
  if at==0x2dc6160:assert state['model_locked'];ret(0);return
  if at in (0x28d6fd0,0x28ae4b0,0x28ada88,0x28b2cb0,0x28bfdcc) or at in range(0x28c54cc,0x28c5671,0x28):
   assert state['model_locked'];value={0x28d6fd0:0,0x28ae4b0:state['style'],0x28ada88:0,0x28b2cb0:71,0x28bfdcc:81}.get(at,19)
   u.mem_write(PROPERTY,struct.pack('<I',value)*16);ret(PROPERTY);return
  if at==0x31fe280:assert args[:2]==[MANAGER,0xe4];ret(7);return
  if at==0x30bed88:assert args==[COMMAND,0xe4,7,MANAGER];state['events'].append('set_sequence_metadata');ret();return
  if at==0x3186f08:ret(0);return # explicit empty dependency table
  if at==0x17fc5d4:
   assert args[0]in(MANAGER+0x46e8,MANAGER+0x338);state['locks'].append(args[0]);state['events'].append('lock_'+hex(args[0]-MANAGER));ret();return
  if at==0x17fc630:
   lock=struct.unpack('<Q',cpu.mem_read(args[0],8))[0];assert state['locks'].pop()==lock
   state['events'].append('unlock_'+hex(lock-MANAGER));ret();return
  if at==0x30bed98:assert args[0]==COMMAND;ret(0xe4);return
  if at==0x30beda4:assert args[0]==COMMAND;ret(7);return
  if at==0x32562d8:assert state['locks']==[MANAGER+0x46e8];state['events'].append('history_insert_fixture');ret();return
  if at in (0x3694134,0x369417c):assert args[:2]==[0xe4,0];ret();return
  if at==0x326d06c:
   assert state['locks']==[MANAGER+0x338]and args[0]==MANAGER+0x320
   assert struct.unpack('<Q',cpu.mem_read(args[1],8))[0]==COMMAND
   state['events'].append('queue_slot_fixture');ret(RAM+0x23000);return
  if at==0x16db260:
   assert state['locks']==[MANAGER+0x338]and args[:2]==[RAM+0x23000,MANAGER+0x320]
   state['events'].append('queue_commit_fixture');ret();return
  if at==0x35bb2b4:assert state['locks']==[MANAGER+0x338];ret();return
  if at==0x16dc530:
   assert args[0]==MANAGER+0x368 and not state['locks'];state['events'].append('notify_original_worker');ret();return
  raise AssertionError('unexpected fixture '+hex(at))
 addresses=[ctor,0x348292c,0x31a9d04,0x16dc130,0x30c01dc,0x3552cfc,0x2e7d208,0x2e7cee4,0x2dc6160,
  0x28d6fd0,0x28ae4b0,0x28ada88,0x28b2cb0,0x28bfdcc,0x31fe280,0x30bed88,0x3186f08,
  0x17fc5d4,0x17fc630,0x30bed98,0x30beda4,0x32562d8,0x3694134,0x369417c,0x326d06c,0x16db260,0x35bb2b4,0x16dc530]
 addresses+=list(range(0x28c54cc,0x28c5671,0x28))
 for at in addresses:u.hook_add(UC_HOOK_CODE,hook,begin=at+bias,end=at+bias)
 for style in [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18]*2:
  state.clear();state.update(style=style,events=[],model_locked=False,locks=[])
  u.mem_write(MANAGER,bytes(0x5000));u.mem_write(REQUEST,struct.pack('<8I',0,1,0,0,0,0,0,0))
  u.reg_write(UC_ARM64_REG_X0,REQUEST);u.reg_write(UC_ARM64_REG_SP,SP);u.reg_write(UC_ARM64_REG_LR,STOP)
  u.emu_start(0x24b0780+bias,STOP,count=100000)
  assert u.reg_read(UC_ARM64_REG_PC)==STOP and u.reg_read(UC_ARM64_REG_SP)==SP and not state['locks']and not state['model_locked']
  assert struct.unpack('<I',u.mem_read(COMMAND+0x18,4))[0]==style
  assert struct.unpack('<I',u.mem_read(COMMAND+0x1c,4))[0]==19
  assert bytes(u.mem_read(COMMAND+0x20,8))==b'\x13'*8
  assert struct.unpack('<Q',u.mem_read(MANAGER+0x330,8))[0]==1
  assert state['events'].index('exact_request_pointer_ctor')<state['events'].index('queue_commit_fixture')
  assert state['events'][-1]=='notify_original_worker' and state['events'].index('model_unlock')<state['events'].index('queue_commit_fixture')
  cases.append(dict(style=style,events=state['events'][:],current_fields_copied=True,original_task_index=0))
 report=dict(passed=True,camera_io=False,bias=hex(bias),cases=cases,total=len(cases),source_sha256=hashlib.sha256(im.data).hexdigest(),AP_sha256=hashlib.sha256(im.data).hexdigest(),
  original_executed=['0x24b0780 facade','0x32885b4 factory','0x318e5c0 current-look snapshot constructor','0x326d098 original locked enqueue'],
  limits=['Native model getters and guard services, base command construction, allocation and container internals are fixtures.',
   'Final425 constructor-call detour reached with exact original private request+16 pointer before queue commit; wrapper body replaced with jump to unchanged native constructor for this specific pointer ABI check. Actual concurrent task and final image not executed.',
   'No native sequence execute method runs on the importer caller in this test.'])
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,total=len(cases),bias=hex(bias))))
if __name__=='__main__':main()
