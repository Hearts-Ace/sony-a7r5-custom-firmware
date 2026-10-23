"""Actual413 AP bank-capacity probe -> actual CP task, native queues modeled.

No camera or host I/O. Crosscore delivery, clocks, AP OSAL ioctl and CP RTOS
boundaries are fixtures. Separate emulators/stacks model receive scheduling.
"""
from pathlib import Path
import argparse,hashlib,io,json,struct,sys,zlib
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools'),str(Path(__file__).parent)]
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn import arm64_const as R
from cp_bridge import CPBridge
def create_cp_bridge(path):return CPBridge(path).run
RAM=0x20000000;SP=RAM+0x80000;ESP=RAM+0x100000;STOP=RAM+0x1ff000
MSG=RAM+0x10000;ACK=RAM+0x20000;SVC=0x32000000;CLOCK=SVC;SLEEP=SVC+0x1000
GPRS=[getattr(R,'UC_ARM64_REG_X'+str(i))for i in range(29)]+[R.UC_ARM64_REG_FP,R.UC_ARM64_REG_LR]
QREGS=[getattr(R,'UC_ARM64_REG_Q'+str(i))for i in range(32)]
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--cp',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 audit=json.loads((a.candidate/'link_audit.json').read_text());raw=(ROOT/audit['candidate']).read_bytes();assert sha(raw)==audit['candidate_sha256']
 elf=ELFFile(io.BytesIO(raw));cp=create_cp_bridge(a.cp);results=[]
 faults=['alloc_fail','alloc_null','send_fail','send_free_fail','missing_clock','missing_sleep','clock_error','clock_backwards','clock_stuck','sleep_fail','timeout','late_ack','duplicate','bad_crc','bad_token','bad_hash','bad_mask','bad_build','bad_reserved','bank_unavailable','cp_bank_alloc_fail','bad_version','bad_op','short_ack','long_ack','wrong_magic','wrong_source','delayed_ack','late_send','bad_mask_input']
 for bias in (0,0x40000000):
  u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
  for seg in elf.iter_segments():
   if seg['p_type']!='PT_LOAD':continue
   lo=(seg['p_vaddr']+bias)&-4096;hi=(seg['p_vaddr']+bias+seg['p_memsz']+4095)&-4096
   if hi>lo:u.mem_map(lo,hi-lo)
   if seg['p_filesz']:u.mem_write(seg['p_vaddr']+bias,seg.data())
  u.mem_map(RAM,0x200000);u.mem_map(SVC,0x2000)
  sy={k:int(v,16)+bias for k,v in audit['symbols'].items()};diag=sy['r5_stage411_probe_state'];state={};end=[STOP]
  native={sy[n]:n for n in ('r5_osal_alloc','r5_osal_send','r5_osal_free','r5_osal_set_src','r5_osal_msg_size')}
  def ret(v=0):
   lr=u.reg_read(R.UC_ARM64_REG_LR)
   for i in range(1,19):u.reg_write(GPRS[i],0xdead0000+i)
   for q in QREGS[:8]+QREGS[16:]:u.reg_write(q,0xdeadbeef)
   u.reg_write(R.UC_ARM64_REG_NZCV,0x50000000);u.reg_write(R.UC_ARM64_REG_FPCR,0x800000);u.reg_write(R.UC_ARM64_REG_FPSR,0x1f)
   u.reg_write(R.UC_ARM64_REG_X0,v&((1<<64)-1));u.reg_write(R.UC_ARM64_REG_PC,lr)
  def code(cpu,pc,size,arg):
   state['instructions']+=1;state['minsp']=min(state['minsp'],cpu.reg_read(R.UC_ARM64_REG_SP))
   if pc==end[0]:cpu.emu_stop();return
   av=[cpu.reg_read(r)for r in GPRS[:4]];fault=state['fault']
   if pc==sy['r5_stage411_dlsym']:
    name=bytes(cpu.mem_read(av[1],64)).split(b'\0')[0].decode();assert name in ('clock_gettime','nanosleep')and av[0]==0
    ret(0 if fault=='missing_clock'and name=='clock_gettime'or fault=='missing_sleep'and name=='nanosleep'else CLOCK if name=='clock_gettime'else SLEEP);return
   if pc==CLOCK:
    assert av[0]==1;state['clocks']+=1
    if fault=='clock_error':ret(-1);return
    ms=900 if fault=='clock_backwards'and state['clocks']>1 else state['time']
    cpu.mem_write(av[1],struct.pack('<qq',ms//1000,ms%1000*1000000));ret();return
   if pc==SLEEP:
    assert struct.unpack('<qq',bytes(cpu.mem_read(av[0],16)))==(0,100000000)and av[1]==0
    state['sleeps']+=1
    if fault!='clock_stuck':state['time']+=100
    if fault=='delayed_ack'and state['sleeps']==3:state['pause']='sleep';cpu.emu_stop();return
    ret(-1 if fault=='sleep_fail'else 0);return
   if pc not in native:return
   name=native[pc];state['native'].append(name)
   if name=='r5_osal_alloc':
    assert av[0]==0x90030001 and av[2:4]==[32,0];state['alloc']+=1
    if fault=='alloc_fail':ret(7);return
    cpu.mem_write(av[1],struct.pack('<Q',0 if fault=='alloc_null'else MSG));ret();return
   if name=='r5_osal_set_src':assert av[:2]==[MSG,0x80020002];state['source']=av[1];ret();return
   if name=='r5_osal_free':assert av[:2]==[0x90030001,MSG];state['free']+=1;ret(9 if fault=='send_free_fail'else 0);return
   if name=='r5_osal_msg_size':assert av[0]==ACK;ret(len(state['reply']));return
   assert name=='r5_osal_send'and av[:2]==[0x90030001,MSG]and state['source']==0x80020002
   state['send']+=1;packet=bytes(cpu.mem_read(MSG,32));state['packet']=packet
   assert packet[:8]==bytes.fromhex('e801012052355032')and zlib.crc32(packet[:28])==struct.unpack_from('<I',packet,28)[0]
   assert struct.unpack_from('<2I',packet,12)==(state['digest'],state['mask'])and packet[20:28]==bytes(8)
   if fault in ('send_fail','send_free_fail'):ret(8);return
   replies,events,stack,dispatch,statuses=(create_cp_bridge(a.cp)(packet,fail='bank_alloc') if fault=='cp_bank_alloc_fail' else cp(packet))
   assert struct.unpack_from('<I',replies[0],20)[0]==(0 if fault=='cp_bank_alloc_fail'else 28768)
   if fault=='cp_bank_alloc_fail':assert 'bank_alloc6904'in events
   assert len(replies)==1 and not dispatch and events[-1]=='release_request'
   state['cp_stack']=stack;reply=bytearray(replies[0]);state['reply_source']=0x90030001
   if fault=='bank_unavailable':
    struct.pack_into('<I',reply,20,0);struct.pack_into('<I',reply,28,zlib.crc32(reply[:28]))
   fields={'bad_token':8,'bad_hash':12,'bad_mask':16,'bad_build':24,'bad_reserved':20,'bad_version':1,'bad_op':2,'wrong_magic':4}
   if fault in fields:reply[fields[fault]]^=1
   if fault in fields:struct.pack_into('<I',reply,28,zlib.crc32(reply[:28]))
   if fault=='bad_crc':reply[-1]^=1
   if fault=='short_ack':reply=reply[:-1]
   if fault=='long_ack':reply+=b'X'
   if fault=='wrong_source':state['reply_source']=0x90030002
   state['reply']=bytes(reply)
   if fault=='late_send':state['time']+=1000
   if fault in ('timeout','late_ack','clock_stuck','sleep_fail','delayed_ack','late_send'):ret();return
   state['pause']='send';cpu.emu_stop()
  def write(cpu,access,address,size,value,arg):
   assert diag<=address<address+size<=diag+80 or RAM<=address<address+size<=RAM+0x180000,(hex(address),size)
  u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
  def invoke(pc,arg0=0,arg1=0,event=False):
   end[0]=(0x3554ec8 if event and state.get('consume_expected',True)else 0x3554d50)+bias if event else STOP
   for i,r in enumerate(GPRS):u.reg_write(r,0x1234567800000000+i)
   for i,r in enumerate(QREGS):u.reg_write(r,0x123456789abcdef01234000000000000+i)
   u.reg_write(R.UC_ARM64_REG_SP,ESP if event else SP);u.reg_write(R.UC_ARM64_REG_LR,STOP)
   u.reg_write(R.UC_ARM64_REG_NZCV,0xa0000000);u.reg_write(R.UC_ARM64_REG_FPCR,0x400000);u.reg_write(R.UC_ARM64_REG_FPSR,0x8000000)
   u.reg_write(R.UC_ARM64_REG_X0,arg0);u.reg_write(R.UC_ARM64_REG_X1,arg1)
   if event:
    u.mem_write(ACK,state['reply']);u.reg_write(R.UC_ARM64_REG_X19,ACK);u.reg_write(R.UC_ARM64_REG_X20,state['reply_source'])
   before=[u.reg_read(r)for r in GPRS];qs=[u.reg_read(r)for r in QREGS];start=pc
   while True:
    state['pause']=None;u.emu_start(start,end[0],count=2000000)
    if not state['pause']:break
    parent=u.context_save();saved=end[0];deliver();
    if state['fault']=='duplicate':deliver()
    u.context_restore(parent);end[0]=saved;ret();start=u.reg_read(R.UC_ARM64_REG_PC)
   assert u.reg_read(R.UC_ARM64_REG_PC)==end[0]and u.reg_read(R.UC_ARM64_REG_SP)==(ESP if event else SP)
   if event:
    wanted=before if state.get('consume_expected',True)else [1]+before[1:]
    assert [u.reg_read(r)for r in GPRS]==wanted
    assert [u.reg_read(r)for r in QREGS]==qs
    assert u.reg_read(R.UC_ARM64_REG_NZCV)==0xa0000000 and u.reg_read(R.UC_ARM64_REG_FPCR)==0x400000 and u.reg_read(R.UC_ARM64_REG_FPSR)==0x8000000
   else:assert [u.reg_read(r)for r in GPRS[19:30]]==before[19:30]
  def deliver():
   state['consume_expected']=state['fault']not in ('wrong_source','wrong_magic')
   invoke(0x3554d4c+bias,event=True)
  for mask,fault in [(m,'valid')for m in (0,1,2,4,8,16,32,64,128,256,512,1024,2048,33,65,129,257,513,1025,2049,4095,0x555,0xaaa)]+[(33,x)for x in faults]:
   state.clear();state.update(mask=mask,digest=0x12345678 if mask else 0,fault=fault,time=1000,clocks=0,sleeps=0,alloc=0,send=0,free=0,source=None,reply=b'',native=[],instructions=0,minsp=SP)
   u.mem_write(diag,bytes(80));u.mem_write(MSG,bytes(32))
   invoke(sy['r5_stage411_probe_run'],4096 if fault=='bad_mask_input'else mask,state['digest'])
   fields=struct.unpack('<9I',bytes(u.mem_read(diag,36)));once,phase,result,token,crc,gotmask,polls,inbox,sendrc=fields
   if fault=='bad_mask_input':assert bytes(u.mem_read(diag,80))==bytes(80)and state['alloc']==0;continue
   expected=6 if fault in ('bank_unavailable','cp_bank_alloc_fail')else 0 if fault in ('valid','delayed_ack')else 2 if fault in ('alloc_fail','alloc_null','send_fail','send_free_fail')else 1 if fault in ('missing_clock','missing_sleep','clock_error')else 4 if fault in ('duplicate','short_ack','long_ack')else 5 if fault.startswith('bad_')else 3
   if fault=='clock_backwards':expected=3
   assert result==expected,(fault,fields,state)
   assert phase==3 and inbox==5 and polls<=11 and state['alloc']<=1 and state['send']<=1
   assert state['free']==(1 if fault in ('send_fail','send_free_fail')else 0)
   assert struct.unpack('<I',u.mem_read(diag+36,4))[0]==(1 if expected==0 else 0)
   old=bytes(u.mem_read(diag,80));calls=len(state['native']);invoke(sy['r5_stage411_probe_run'],mask,state['digest']);assert bytes(u.mem_read(diag,80))==old and len(state['native'])==calls
   if state['reply']and fault not in ('wrong_source','wrong_magic'):
    deliver();assert bytes(u.mem_read(diag,40))==old[:40]and struct.unpack('<I',u.mem_read(diag+40,4))[0]==1
   results.append(dict(bias=hex(bias),mask=mask,fault=fault,result=result,polls=polls,AP_allocations=state['alloc'],AP_sends=state['send'],failed_sends_freed=state['free'],CP_native_stack_bytes=state.get('cp_stack'),instructions=state['instructions']))
 report=dict(schema='r5-413-actual-AP-CP-bank-capacity-replay/1',passed=True,camera_io=False,candidate_sha256=sha(raw),CP_sha256=sha(a.cp.read_bytes()),cases=len(results),results=results,
  all_masks_0_to4095=False,coverage="zero+12singletons+composites+full",CP_bank_allocation_failure_executed=True,bank_capacity_required_for_matched=True,exact_native_AP_packet_sender=True,actual_CP_receive_task_executed=True,actual_AP_inbound_hook_executed=True,all_GPR_SIMD_flags_preserved=True,terminal_late_reply_consumed=True,
  limits=['AP dlsym/clocks/nanosleep and OSAL PLT ioctl replies modeled; CP RTOS/message pool/locks/final sender modeled; native bank allocator executes on a synthetic heap.',
   'Crosscore delivery scheduling uses separate emulators/stacks; no real kernel/queue/device/WBI proof.',
   'wait0 and finite polls do not bound blocking native calls. ACK confirms metadata and reserved bank capacity only, not parameter values/application.'])
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='results'}))
if __name__=='__main__':main()
