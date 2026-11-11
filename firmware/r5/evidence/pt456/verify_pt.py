#!/usr/bin/env python3
"""Replay the new private BL and native PT getter/setter to model publication.

No camera, network, USB or SD access. Sony transaction/OS services and observer
delivery are explicit endpoints; the new branch, helper, getter, setter, model
and optional mirrored-value writes execute from the supplied final AP.
"""
from pathlib import Path
import argparse, hashlib, io, json, struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as A

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ap',type=Path,required=True)
    p.add_argument('--build',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();assert not a.output.exists()
    report=json.loads((a.build/'build.json').read_text())
    assert report['passed'] and sha(a.ap)==report['sha256']
    raw=a.ap.read_bytes();e=ELFFile(io.BytesIO(raw));results=[]
    for bias in (0,0x4000000000):
        for selected,kind,state,look,mirror in [
            (1,1,1,0,False),(12,1,1,5,True),(5,1,1,1,True),
            (0,1,1,3,True),(13,1,1,3,False),(1,2,1,3,True),
            (1,1,2,3,True),(1,1,3,3,True),(1,0,0,3,False)]:
            u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
            for s in e.iter_segments():
                if s['p_type']=='PT_LOAD' and s['p_memsz']:
                    lo=(bias+s['p_vaddr'])&-4096
                    hi=(bias+s['p_vaddr']+s['p_memsz']+4095)&-4096
                    u.mem_map(lo,hi-lo)
                    if s['p_filesz']:u.mem_write(bias+s['p_vaddr'],s.data())
            stack=0x20000000;u.mem_map(stack,0x20000)
            def write(at,v,fmt='<I'):u.mem_write(at,struct.pack(fmt,v))
            def read(at,fmt='<I'):return struct.unpack(fmt,u.mem_read(at,struct.calcsize(fmt)))[0]
            def x(i):return u.reg_read(getattr(A,'UC_ARM64_REG_X'+str(i)))
            def ret(v=0):u.reg_write(A.UC_ARM64_REG_X0,v);u.reg_write(A.UC_ARM64_REG_PC,x(30))
            native=report['native_bindings'];target=bias+0x7eff000+0xa98+0x20000+0xd50
            mirror_slot=stack+0x100;params=stack+0x200
            write(target,look);write(target+0x10,mirror_slot if mirror else 0,'<Q')
            write(mirror_slot,look)
            write(bias+native['r5_filter_pt_desired'],(17<<32)|selected,'<Q')
            write(bias+native['r5_filter_pt_command_state'],state)
            write(bias+native['r5_filter_pt_command_kind'],kind)
            events=[];counts={'total':0,'helper':0,'getter':0,'setter':0}
            start=bias+report['private_refresh_call'];stop=start+4
            helper=bias+report['symbols']['r5_filter_pt_sequence_request']
            def hook(uc,at,size,data):
                va=at-bias;counts['total']+=1
                if helper<=at<helper+report['rx_bytes']:counts['helper']+=1
                if va==0x1c05f18:counts['getter']+=1
                if va==0x1c6f208:counts['setter']+=1
                if va in (0x2e7d208,0x2e7cee4,0x17f7d68):return ret()
                if va==0x17f7d44:
                    write(x(0)+8,stack+0x400,'<Q');return ret()
                if va==0x3694f64:
                    events.append(('transaction',x(1),read(x(3)),x(4)));return ret()
                if va==0x252d80c:
                    events.append(('commit',x(0),read(target)));return ret()
                if va==0x252ca34:
                    events.append(('notify',x(0),read(target)));return ret()
                if va==0x24b0780:
                    events.append(('existing_E4_request',x(0),read(target)));return ret()
            u.hook_add(UC_HOOK_CODE,hook)
            u.reg_write(A.UC_ARM64_REG_SP,stack+0x1f000)
            u.reg_write(A.UC_ARM64_REG_X0,params)
            # Callee-saved registers and exact argument pointer must survive BL.
            saved={i:0x1122334455660000+i for i in range(19,30)}
            for i,v in saved.items():u.reg_write(getattr(A,'UC_ARM64_REG_X'+str(i)),v)
            u.emu_start(start,stop,count=10000)
            assert u.reg_read(A.UC_ARM64_REG_PC)==stop
            assert all(x(i)==v for i,v in saved.items())
            change=1<=selected<=12 and kind==1 and state==1 and look!=1
            expected=1 if change else look
            assert read(target)==expected,(bias,selected,kind,state,look,read(target),events,counts,hex(target))
            assert read(mirror_slot)==(expected if mirror else look)
            assert counts['setter']==int(change)
            assert counts['getter']==int(1<=selected<=12 and kind==1 and state==1)
            assert events==([('transaction',0x690,1,4),('commit',0x690,1),('notify',0x690,1)] if change else [])+[
                ('existing_E4_request',params,expected)]
            results.append(dict(bias=bias,selected=selected,kind=kind,state=state,initial_look=look,
                                mirrored_model=mirror,final_look=expected,events=events,instructions=counts))
    result=dict(passed=True,AP_sha256=sha(a.ap),build_sha256=sha(a.build/'build.json'),cases=results,
                actual=['Final AP private refresh425 BL','112-byte PT helper, no new BSS',
                        'Native 1c05f18 getter and 28ae4b0/28ae4c4 model accessors',
                        'Native 1c6f208 setter writes model and optional mirror; native destructor path',
                        'Original E4 request receives identical parameter pointer and native BL continuation'],
                fixtures=['Native locks and transaction-context creation','3694f64 transaction service records PID/value',
                          '252d80c commit observer and 252ca34 Notify delivery boundaries',
                          '24b0780 E4 queue endpoint; no actual IPC/hardware completion'],
                limits=['CPU instruction count is not camera timing','Native notification scheduling and LCD/ISP completion not emulated',
                        'Existing worker selection ACK/wait/rollback source and byte identity bound separately',
                        'PT remains selected if the existing filter transaction later fails after this refresh'],
                camera_io=False,device_tested=False)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(results),AP_sha256=result['AP_sha256'],
                         PT_fast_case=results[2]['instructions'],PT_first_case=results[0]['instructions'])))

if __name__=='__main__':main()
