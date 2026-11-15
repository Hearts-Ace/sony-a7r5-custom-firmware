#!/usr/bin/env python3
"""Actual final AP native E4/402f/worker protocol at two PIE biases.

Only file, scheduler/enqueue, IPC, timer and eight unrelated E4 leaf endpoints
are fixtures. No replacement of the production wrapper, E4 or 402f serializer.
"""
from pathlib import Path
import argparse,hashlib,json,struct
from replay_final_ap import FinalAP,FIX,SERV,STOP,STACK
from elftools.elf.elffile import ELFFile
from unicorn.arm64_const import UC_ARM64_REG_PC,UC_ARM64_REG_SP

def check(ok,label):
    if not ok:raise AssertionError(label)
def local(machine,build,obj,name):
    with (build/'objects'/obj).open('rb') as f:
        elf=ELFFile(f);symbol=next(s for s in elf.get_section_by_name('.symtab').iter_symbols()if s.name==name)
        row=next(s for s in machine.report['sections']if Path(s['object']).name==obj and s['index']==symbol['st_shndx'])
        return machine.bias+int(row['va'],16)+symbol['st_value']
def crc(p):
    p=bytearray(p);p[28:32]=bytes(4)
    import zlib
    return zlib.crc32(p)
class WorkerAP(FinalAP):
    def call(self,name,*args):
        for i,arg in enumerate(args):self.putx(i,arg)
        self.u.reg_write(UC_ARM64_REG_SP,STACK+126976);self.putx(29,0);self.putx(30,STOP)
        self.u.emu_start(self.sy[name]if isinstance(name,str)else name,STOP,count=5000000)
        check(self.u.reg_read(UC_ARM64_REG_PC)==STOP,(name,hex(self.u.reg_read(UC_ARM64_REG_PC))))
        return self.x(0)&0xffffffff
def run(candidate,build,bias):
    m=WorkerAP(candidate,build,bias);tick=0;enqueued=[];chain=[];ipc=[];other=[];active=0;phase=0;cookie=0;key=None;requests=0;reads=[];saves=[];suppress=False;drop_accept=False;collects=0
    native=json.loads((Path(__file__).resolve().parents[2]/'contracts/native.json').read_text())
    request=local(m,build,'r5_filter_runtime.o','job_request');object_=FIX+0x6000;foreign=FIX+0x6100;data=FIX+0x6300;message=FIX+0x7000
    m.u.mem_write(bias+0x5983198,struct.pack('<Q',data));m.u.mem_write(data,bytes(range(12)))
    def clock():m.u.mem_write(m.x(1),struct.pack('<qq',tick//1000,(tick%1000)*1000000));m.ret()
    def sleep():
        nonlocal tick
        sec,ns=struct.unpack('<qq',m.u.mem_read(m.x(0),16));tick+=sec*1000+ns//1000000
        if enqueued:
            task=enqueued.pop(0);chain.append(m.x(30));m.putx(0,task);m.putx(30,SERV+0x410);m.u.reg_write(UC_ARM64_REG_PC,m.sy['r5_filter_refresh_execute425'])
        else:m.ret()
    def resolver():m.ret({'clock_gettime':SERV+0x200,'nanosleep':SERV+0x210}.get(m.cstr(m.x(1)),0))
    def forbidden():raise AssertionError('Look get/set forbidden')
    def original_construct():
        p=bytearray(range(56));struct.pack_into('<III',p,0x14,0x1234,0,8);m.u.mem_write(m.x(0),bytes(p));m.ret()
    def sequence():
        nonlocal requests
        check(m.x(0)==request,'worker request address');requests+=1;chain.append(m.x(30))
        m.putx(0,object_);m.putx(1,request+16);m.putx(30,SERV+0x400);m.u.reg_write(UC_ARM64_REG_PC,m.sy['r5_filter_refresh_construct425'])
    def queued():
        if not suppress:enqueued.append(object_)
        m.putx(30,chain.pop());m.ret()
    def done():m.putx(30,chain.pop());m.ret()
    def native_402f():
        nonlocal active,phase
        check(m.x(0)==0x90030001 and m.x(2)==12,'native402f real send length/destination')
        p=bytes(m.u.mem_read(m.x(1),12));ipc.append(p.hex());tag=int.from_bytes(p[9:12],'little')
        check(p[8]==expected_color,'native color byte unchanged')
        if tag&0x800000:
            check((tag&0x7fffff)==cookie and phase==1,'native task cookie bound to prepared owner');active=key[2];phase=2
        m.ret()
    def leaf():other.append((m.x(0),bytes(m.u.mem_read(m.x(0),12)).hex()));m.ret()
    def ack(op,status,detail):
        a=bytearray(struct.pack('<4B9I',0xe7,1,op|128,0,0x46303536,*key,8,0,status,detail));struct.pack_into('<I',a,28,crc(a));return bytes(a)
    def cp():
        nonlocal phase,cookie,key,collects
        p=bytes(m.u.mem_read(m.x(1),m.x(2)));check(p[0]==0xe7 and struct.unpack_from('<I',p,4)[0]==0x46303536 and crc(p)==struct.unpack_from('<I',p,28)[0],'new production wire')
        op=p[2];k=struct.unpack_from('<4I',p,8)
        if op==1:
            if k!=key:key=k;cookie+=1;phase=1
            status=6 if phase==2 else 0;detail=cookie
        elif op==2:
            check(k==key,'ABORT keyed');status=6 if phase==2 else 0;detail=cookie if status else 0
            if not status:phase=0
        elif op==3:
            collects+=1;oldkey=key;key=k;a=ack(op,0,0);key=oldkey;status=None
        else:raise AssertionError(op)
        if status is not None:a=ack(op,status,detail)
        m.u.mem_write(message,a);chain.append(m.x(30));m.putx(0,message);m.putx(1,0x90030001);m.putx(30,SERV+0x440);m.u.reg_write(UC_ARM64_REG_PC,m.sy['r5_filter_inbound'])
    def transport_return():m.putx(30,chain.pop());m.ret()
    def record_read():
        reads.append(m.x(1));m.u.mem_write(m.x(2),bytes((i+reads[-1])%256 for i in range(2392)));m.ret()
    def save():saves.append(m.u32(m.x(0)));m.ret()
    m.callbacks.update({bias+native['r5_stage411_dlsym']:resolver,SERV+0x200:clock,SERV+0x210:sleep,bias+0x1c05f18:forbidden,bias+0x1c6f208:forbidden,bias+0x24b0780:sequence,SERV+0x400:queued,SERV+0x410:done,SERV+0x440:transport_return,bias+0x318e5c0:original_construct,bias+native['r5_osal_msg_size']:lambda:m.ret(40),m.sy['r5_native_ap_send']:cp,m.sy['r5_filter_store_read']:record_read,m.sy['r5_filter_store_selection']:save,bias+0x355882c:native_402f})
    # Leave real E4 and serializer in place, intercept native leaf calls2..9.
    for at in range(0x35092bc,0x350947d,0x40):m.callbacks[bias+at]=leaf
    for at in (0x36951e0,0x36952a0,0x369448c):m.callbacks[bias+at]=lambda:m.ret()
    # Final RET has already restored original E4 LR; inline callback delivers
    # accept then returns to that same saved continuation.
    tailstack=[]
    def e4_tail():
        if phase==2 and not drop_accept:
            a=ack(4,0,cookie);m.u.mem_write(message,a);tailstack.append(m.x(30));m.putx(0,message);m.putx(1,0x90030001);m.putx(30,SERV+0x450);m.u.reg_write(UC_ARM64_REG_PC,m.sy['r5_filter_inbound'])
        else:m.u.reg_write(UC_ARM64_REG_PC,m.x(30))
    def native_return():m.putx(30,tailstack.pop());m.u.reg_write(UC_ARM64_REG_PC,m.x(30))
    m.callbacks[bias+0x3482a88]=e4_tail;m.callbacks[SERV+0x450]=native_return
    m.call(bias+0x3550354,0,8,FIX+0x6800);expected_color=m.u32(FIX+0x6800)&255
    m.call('r5_session_cold');check(m.call('r5_session_prepare')==1,'session')
    index=bytearray(1284);struct.pack_into('<I',index,128,4095)
    for i in range(12):index[132+i*96+8:132+i*96+10]=bytes([65+i,0]);index[132+i*96+32:132+i*96+34]=bytes([97+i,0])
    m.u.mem_write(FIX,bytes(index));check(m.call('r5_filter_catalog_ready',FIX,0,1)==0,'catalog')
    m.call('r5_filter_service');check(active==0 and m.call('r5_filter_selected')==0 and not m.call('r5_filter_pending'),'boot Off native acceptance')
    original=bytes(m.u.mem_read(object_,56));check(struct.unpack_from('<I',original,0x1c)[0]==8,'original E4 selector not tagged')
    m.call('r5_filter_request',1);m.call('r5_filter_service');check(active==1 and m.call('r5_filter_selected')==1 and m.call('r5_filter_command_state')==2,'activate1')
    check(reads==[1] and requests==2 and len(ipc)==2,'single selected record and exact two native jobs')
    drop_accept=True;m.call('r5_filter_request',2);m.call('r5_filter_service');check(active==2 and m.call('r5_filter_selected')==2 and m.call('r5_filter_command_state')==2,'lost ACCEPT recovered by exact ABORT accepted result');drop_accept=False
    suppress=True;m.call('r5_filter_request',3);m.call('r5_filter_service');check(active==2 and m.call('r5_filter_selected')==2 and m.call('r5_filter_command_state')==3,'queued native task abort preserves prior owner');suppress=False
    prev=len(ipc);m.call('r5_filter_refresh_execute425',object_);check(len(ipc)==prev+1 and int.from_bytes(bytes.fromhex(ipc[-1])[9:12],'little')==0,'late object executes untagged stock')
    m.call('r5_filter_request',0);m.call('r5_filter_service');check(active==0 and m.call('r5_filter_selected')==0 and reads==[1,2,3],'Off no parameter read')
    tick+=1000;m.call('r5_filter_service');check(collects==1,'Off collect task with no extra file reads')
    check(bytes(m.u.mem_read(object_,56))==original,'task bytes unchanged')
    return dict(bias=hex(bias),passed=True,ipc=ipc,reads=reads,saves=saves,requests=requests,collects=collects,other_E4_leaf_calls=len(other),exact_native_E4_and_serializer=True,private_owner_pointers_published=False)
def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();check(not a.output.exists(),'new evidence path')
    r=dict(passed=True,AP_sha256=hashlib.sha256(a.candidate.read_bytes()).hexdigest(),cases=[run(a.candidate,a.build,b)for b in [0x4000000000,0x6000000000]],limits=['Native E4 original402f serializer and patched BL execute from final ELF; native enqueue/constructor fields/timing,IPC,read/store,CP actor are fixtures.','Eight native E4 callback bodies and IPC shared transport helpers are return endpoints; assertions include exact first wire payload.','No actual CP message task, physical camera or hardware consumer completion.'])
    a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(r['cases']))))
if __name__=='__main__':main()
