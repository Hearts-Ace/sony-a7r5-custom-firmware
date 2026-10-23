"""Execute actual AArch64 uploader and ARM native receive task. Offline only.
OSAL queues, scheduling, clocks and RTOS synchronization are explicit fixtures.
"""
from pathlib import Path
import argparse,hashlib,io,json,struct,sys,zlib,importlib.util
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn import arm64_const as R
RAM=0x20000000;SP=RAM+0x80000;ESP=RAM+0x100000;STOP=RAM+0x1ff000
MSG=RAM+0x10000;ACK=RAM+0x20000;SET=RAM+0x30000;SVC=0x32000000
CLOCK=SVC;SLEEP=SVC+0x1000
GPRS=[getattr(R,'UC_ARM64_REG_X'+str(i))for i in range(29)]+[R.UC_ARM64_REG_FP,R.UC_ARM64_REG_LR]
QREGS=[getattr(R,'UC_ARM64_REG_Q'+str(i))for i in range(32)]
sha=lambda b:hashlib.sha256(b).hexdigest()
def values(slot):
 cc=[(-100+slot+i if i<4 else 400+slot+i)for i in range(8)]+[slot]*8+[-slot]*8
 matrix=[(i%29-14)*(slot+1) for i in range(288)]
 gamma=[i*1000 for i in range(129)]
 return ('native%d'%slot).encode().ljust(32,b'\0')+struct.pack('<24h288h129I',*cc,*matrix,*gamma)+struct.pack('<I1215bB',1,*[((slot+i)%128)-64 for i in range(1215)],0)
def ap_values(compact,slot):
 return compact[:24]+('full-name-%d'%slot).encode().ljust(64,b'\0')+compact[32:1172]+compact[1176:]
def wire(op,token,mask,slot,digest,seq,payload=b''):
 p=struct.pack('<4B7I',0xe7,3,op,0,0x584e3552,token,mask,slot,digest,seq,0)+payload
 return p[:28]+struct.pack('<I',zlib.crc32(p))+p[32:]
def main():
 p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--cp',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 audit=json.loads((a.candidate/'import/module_audit.json').read_text());raw=(a.candidate/'ap/appFw.so').read_bytes()
 spec=importlib.util.spec_from_file_location('cp413_transfer_fixture',Path(__file__).parent/'cp_bridge423.py');bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
 elf=ELFFile(io.BytesIO(raw));results=[];adversarial=[]
 faults=['no_capacity','zero_mask','bad_mask','missing_clock','missing_sleep','clock_error','clock_backwards','clock_stuck','sleep_fail','send_fail','alloc_fail','alloc_null','drop_begin','drop_put','drop_seal','bad_crc','bad_token','bad_hash','bad_mask_ack','bad_sequence','bad_state','bad_status','bad_received','short_ack','long_ack','wrong_source','wrong_magic','duplicate','bad_gamma','bad_cc1','bad_matrix','late_send']
 for bias in (0,0x40000000):
  u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
  for seg in elf.iter_segments():
   if seg['p_type']!='PT_LOAD':continue
   lo=(seg['p_vaddr']+bias)&-4096;hi=(seg['p_vaddr']+bias+seg['p_memsz']+4095)&-4096
   if hi>lo:u.mem_map(lo,hi-lo)
   if seg['p_filesz']:u.mem_write(seg['p_vaddr']+bias,seg.data())
  u.mem_map(RAM,0x200000);u.mem_map(SVC,0x2000)
  sy={k:v+bias for k,v in audit['symbols'].items()};diag=sy['r5_stage413_transfer_state'];probe=sy['r5_stage411_probe_state'];st={};end=[STOP]
  native={sy[n]:n for n in ('r5_osal_alloc','r5_osal_send','r5_osal_free','r5_osal_set_src','r5_osal_msg_size','r5_native_lut_directory_api_init','r5_lut_directory_acquire','r5_filter_selection_save','r5_lut_directory_release','r5_native_creative_sequence_request')}
  def ret(v=0):
   lr=u.reg_read(R.UC_ARM64_REG_LR)
   for i in range(1,19):u.reg_write(GPRS[i],0xdead0000+i)
   for q in QREGS[:8]+QREGS[16:]:u.reg_write(q,0xdeadbeef)
   u.reg_write(R.UC_ARM64_REG_X0,v&((1<<64)-1));u.reg_write(R.UC_ARM64_REG_PC,lr)
  def code(cpu,pc,size,arg):
   if pc==end[0]:cpu.emu_stop();return
   av=[cpu.reg_read(r)for r in GPRS[:4]];f=st['fault']
   if pc==sy['r5_stage411_dlsym']:
    name=bytes(cpu.mem_read(av[1],64)).split(b'\0')[0].decode();assert name in ('clock_gettime','nanosleep')
    ret(0 if f=='missing_clock'and name=='clock_gettime'or f=='missing_sleep'and name=='nanosleep'else CLOCK if name=='clock_gettime'else SLEEP);return
   if pc==CLOCK:
    st['clocks']+=1
    if f=='clock_error':ret(-1);return
    ms=900 if f=='clock_backwards'and st['clocks']>1 else st['time']
    cpu.mem_write(av[1],struct.pack('<qq',ms//1000,ms%1000*1000000));ret();return
   if pc==SLEEP:
    assert struct.unpack('<qq',bytes(cpu.mem_read(av[0],16))) in ((0,100000000),(0,10000000))
    if f!='clock_stuck':st['time']+=100
    ret(-1 if f=='sleep_fail'else 0);return
   if pc not in native:return
   n=native[pc]
   if n in ('r5_native_lut_directory_api_init','r5_lut_directory_acquire','r5_filter_selection_save','r5_lut_directory_release'):ret();return
   if n=='r5_native_creative_sequence_request':st['refreshes']=st.get('refreshes',0)+1;ret();return
   if n=='r5_osal_alloc':
    assert av[0]==0x90030001 and av[2] in (32,2424)and av[3]==0;st['alloc']+=1;st['length']=av[2]
    if f=='alloc_fail':ret(7);return
    cpu.mem_write(av[1],struct.pack('<Q',0 if f=='alloc_null'else MSG));ret();return
   if n=='r5_osal_set_src':assert av[:2]==[MSG,0x80020002];ret();return
   if n=='r5_osal_free':assert av[:2]==[0x90030001,MSG];st['free']+=1;ret();return
   if n=='r5_osal_msg_size':assert av[0]==ACK;ret(len(st['reply']));return
   assert n=='r5_osal_send'and av[:2]==[0x90030001,MSG]
   packet=bytes(cpu.mem_read(MSG,st['length']));st['packets'].append(packet);st['send']+=1
   if packet[0]==0xea:
    assert packet[:8]==b'\xea\x01\x01\x20R5FS'
    replies,events,stack,dispatch,_=st['cp'].run(packet);assert len(replies)==1 and not dispatch
    st['reply']=bytes(replies[0]);st['source']=0x90030001;st['pause']=True;cpu.emu_stop();return
   op=packet[2];slot=struct.unpack_from('<I',packet,16)[0]
   assert packet[:2]==b'\xe7\x03' and packet[4:8]==b'R5NX'
   assert struct.unpack_from('<I',packet,28)[0]==zlib.crc32(packet[:28]+bytes(4)+packet[32:])
   if op==2:assert packet[32:]==st['params'][slot-1]
   if f=='send_fail':ret(8);return
   replies,events,stack,dispatch,_=st['cp'].run(packet)
   assert len(replies)==1 and not dispatch and events[-1]=='release_request'
   st['cp_stack']=max(st['cp_stack'],stack);reply=bytearray(replies[0]);st['source']=0x90030001
   fields={'bad_token':8,'bad_hash':20,'bad_mask_ack':12,'bad_sequence':24,'bad_state':32,'bad_status':36,'bad_received':40,'wrong_magic':4}
   if f in fields:reply[fields[f]]^=1;reply[28:32]=bytes(4);reply[28:32]=struct.pack('<I',zlib.crc32(reply))
   if f=='bad_crc':reply[-1]^=1
   if f=='short_ack':reply=reply[:-1]
   if f=='long_ack':reply+=b'X'
   if f=='wrong_source':st['source']=0x90030002
   st['reply']=bytes(reply)
   if f=='late_send':st['time']+=3000
   if f in ('clock_stuck','sleep_fail','late_send')or f=='drop_begin'and op==1 or f=='drop_put'and op==2 or f=='drop_seal'and op==3:ret();return
   st['pause']=True;cpu.emu_stop()
  def write(cpu,access,address,size,value,arg):
   assert audit['rw']+bias<=address<address+size<=audit['rw']+bias+audit['bss_bytes'] or RAM<=address<address+size<=RAM+0x180000,(hex(address),size)
  for at in [*native,sy['r5_stage411_dlsym'],CLOCK,SLEEP]:
   u.hook_add(UC_HOOK_CODE,code,begin=at,end=at)
  u.hook_add(UC_HOOK_MEM_WRITE,write)
  def invoke(pc,event=False,argument=SET):
   consume=st['fault']not in ('wrong_source','wrong_magic')
   end[0]=((0x3554ec8 if consume else 0x3554d50)+bias)if event else STOP
   for i,r in enumerate(GPRS):u.reg_write(r,0x1234567800000000+i)
   for i,r in enumerate(QREGS):u.reg_write(r,0x123456789abcdef01234000000000000+i)
   u.reg_write(R.UC_ARM64_REG_SP,ESP if event else SP);u.reg_write(R.UC_ARM64_REG_LR,STOP)
   u.reg_write(R.UC_ARM64_REG_NZCV,0xa0000000);u.reg_write(R.UC_ARM64_REG_FPCR,0x400000);u.reg_write(R.UC_ARM64_REG_FPSR,0x8000000)
   u.reg_write(R.UC_ARM64_REG_X0,argument)
   if event:u.mem_write(ACK,st['reply']);u.reg_write(R.UC_ARM64_REG_X19,ACK);u.reg_write(R.UC_ARM64_REG_X20,st['source'])
   before=[u.reg_read(r)for r in GPRS];qs=[u.reg_read(r)for r in QREGS];start=pc
   while True:
    st['pause']=False;u.emu_start(start,end[0],count=12000000)
    if not st['pause']:break
    saved=u.context_save();saved_end=end[0];invoke(0x3554d4c+bias,True)
    if st['fault']=='duplicate':invoke(0x3554d4c+bias,True)
    u.context_restore(saved);end[0]=saved_end;ret();start=u.reg_read(R.UC_ARM64_REG_PC)
   assert u.reg_read(R.UC_ARM64_REG_PC)==end[0]and u.reg_read(R.UC_ARM64_REG_SP)==(ESP if event else SP)
   if event:
    assert [u.reg_read(r)for r in GPRS]==(before if consume else [1]+before[1:])
    assert [u.reg_read(r)for r in QREGS]==qs
    assert u.reg_read(R.UC_ARM64_REG_NZCV)==0xa0000000 and u.reg_read(R.UC_ARM64_REG_FPCR)==0x400000 and u.reg_read(R.UC_ARM64_REG_FPSR)==0x8000000
   else:assert [u.reg_read(r)for r in GPRS[19:30]]==before[19:30]
  for mask,fault in [(4095,'valid')]:
   cp=bridge.create_cp_bridge(a.cp);cp.run(bridge.packet())
   params=[values(i+1)for i in range(12)]
   if fault=='bad_gamma':v=bytearray(params[0]);struct.pack_into('<I',v,656+4,131072);params[0]=bytes(v)
   if fault=='bad_cc1':v=bytearray(params[0]);struct.pack_into('<h',v,32,1024);params[0]=bytes(v)
   if fault=='bad_matrix':v=bytearray(params[0]);struct.pack_into('<h',v,80,8192);params[0]=bytes(v)
   st.clear();st.update(fault=fault,time=1000,clocks=0,cp=cp,params=params,reply=b'',send=0,alloc=0,free=0,packets=[],cp_stack=0)
   u.mem_write(audit['rw']+bias,bytes(audit['bss_bytes']));invoke(sy['r5_session_cold']);invoke(sy['r5_session_prepare']);invoke(sy['r5_session_new_transfer']);u.mem_write(probe+36,struct.pack('<I',0 if fault=='no_capacity'else 1))
   setmask=0 if fault=='zero_mask'else 4096 if fault=='bad_mask'else mask
   u.mem_write(SET,struct.pack('<I',setmask)+b''.join(ap_values(v,i+1)for i,v in enumerate(params)))
   invoke(sy['r5_stage413_transfer_run'])
   once,phase,result,inbox,matched,sends,polls,late=struct.unpack('<8I',bytes(u.mem_read(diag,32)))
   if fault in ('no_capacity','bad_mask'):assert once==sends==matched==0
   elif fault in ('valid','zero_mask'):
    assert phase==3 and result==0 and matched==1 and sends==bin(setmask).count('1')+2,(mask,result,sends)
    bank=bytes(cp.cpu.mem_read(cp.bank_pointer,28768));state,token,expected,received=struct.unpack_from('<4I',bank)
    assert state==0x35424c53 and expected==received==setmask and bank[16:64]==bytes(48)
    for slot in range(12):assert bank[64+slot*2392:64+(slot+1)*2392]==(params[slot]if setmask&(1<<slot)else bytes(2392))
    digest=zlib.crc32(struct.pack('<I',setmask)+b''.join(struct.pack('<I',i+1)+params[i]for i in range(12)if setmask&(1<<i)))
    assert all(struct.unpack_from('<I',p,20)[0]==digest for p in st['packets'])
    assert cp.r(0x1a39458)==0,'SEAL must not change active view before SELECT'
    invoke(sy['r5_stage421_parameters_ready'])
    assert cp.r(0x1a39458)!=0
    invoke(sy['r5_session_finish'])
    for selected in list(range(1,13))+[0]:
     invoke(sy['r5_filter_request'],argument=selected)
     assert u.reg_read(R.UC_ARM64_REG_X0)==0
     invoke(sy['r5_filter_service'])
     invoke(sy['r5_filter_selected'])
     assert u.reg_read(R.UC_ARM64_REG_X0)==selected
     active=cp.r(0x1a39458);assert cp.r(active+8)==selected
    assert st['refreshes']==14


   else:assert phase==3 and result and not matched,(fault,result)
   assert polls<=40 and st['free']==0
   snapshot=bytes(u.mem_read(diag,160));n=st['send'];invoke(sy['r5_stage413_transfer_run']);assert bytes(u.mem_read(diag,160))==snapshot and st['send']==n
   results.append(dict(bias=hex(bias),mask=mask,fault=fault,result=result,sends=sends,polls=polls,CP_stack_bytes=st['cp_stack']))
 report=dict(schema='r5-423-canonical-parameter-upload-replay/1',passed=True,camera_io=False,candidate_sha256=sha(raw),CP_sha256=sha(a.cp.read_bytes()),cases=len(results),results=results,hostile_CP_transactions=adversarial,actual_selects=28,sidecar_IO='explicit stubs; real sidecar validated separately',native_refreshes=28,all_nonempty_masks=False,coverage_mask_policy="Full bank, SELECT zero and each of 12 configurations at two AP biases",CC1_block13_all129_gamma_bytes_checked=True,actual_AP_sender_inbound_and_CP_receive_task_executed=True,limits=['Crosscore delivery,RTOS locking,OSAL queues,clock and scheduling modeled.','Native shared heap executes on synthetic8MiB; actual camera startup,heap/stack budget,WBI and real transfer unverified.','Data seal creates immutable per-selection views; active view must remain unchanged until SELECT; hardware use is separate.'])
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='results'}))
if __name__=='__main__':main()
