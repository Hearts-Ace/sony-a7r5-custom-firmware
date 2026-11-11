#!/usr/bin/env python3
"""Replay descriptor and actual patched wire sites from the FINAL appended ELF.

No module overlay or test-installed hook. ELF relocations are modeled; libc,
native setter/commit, OS mutexes and packet transport are explicit fixtures.
"""
from pathlib import Path
import argparse, hashlib, json, struct, sys
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(HERE.parent/'ap'),str(HERE)]
from replay_ap import Replay, FIX, SERV, STACK, STOP, Q, p32, p64
from inspect_ap import Image
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import *

class FinalAP(Replay):
    def __init__(self, candidate, build, bias):
        self.bias=bias; self.im=Image(candidate)
        self.report=json.loads((build/'module.json').read_text())
        self.sy={n:v+bias for n,v in self.report['symbols'].items()}
        self.u=Uc(UC_ARCH_ARM64,UC_MODE_ARM); self.callbacks={}; self.calls=[]; self.native=0
        for s in self.im.loads:
            lo=(s['p_vaddr']+bias)&-4096; hi=(s['p_vaddr']+bias+s['p_memsz']+4095)&-4096
            if hi>lo:self.u.mem_map(lo,hi-lo)
            data=self.im.raw[s['p_offset']:s['p_offset']+s['p_filesz']]
            if data:self.u.mem_write(s['p_vaddr']+bias,data)
        dynamic=self.im.elf.get_section_by_name('.dynsym')
        self.relocated=0;self.imports=0;self.tls=0
        for name in ('.rela.dyn','.rela.plt'):
            for at,info,addend in struct.iter_unpack('<QQq',self.im.elf.get_section_by_name(name).data()):
                kind=info&0xffffffff;sym=info>>32
                if kind==1027:value=bias+addend
                elif kind in (257,1025,1026):
                    symbol=dynamic.get_symbol(sym)
                    if symbol['st_shndx']=='SHN_UNDEF':self.imports+=1;continue
                    value=symbol['st_value']+addend+(0 if symbol['st_shndx']=='SHN_ABS' else bias)
                elif kind in (1028,1029,1030,1031):self.tls+=1;continue
                else:raise AssertionError(('Unsupported relocation',kind,hex(at)))
                self.u.mem_write(at+bias,p64(value));self.relocated+=1
        for at,n in [(FIX,0x10000),(SERV,0x10000),(STACK,0x20000),(STOP,0x1000)]:self.u.mem_map(at,n)
        self.callbacks[STOP]=lambda:self.u.emu_stop()
        for at in (0x2e7d208,0x2e7cee4):self.callbacks[bias+at]=lambda:self.ret()
        self.callbacks[bias+0x1c61d14]=self.setter
        self.callbacks[bias+0x1c93d88]=self.commit
        self.callbacks[bias+0x16dac90]=self.dlsym
        self.callbacks[bias+0x355882c]=self.send
        self.u.hook_add(UC_HOOK_CODE,self.hook)
        self.u.reg_write(UC_ARM64_REG_CPACR_EL1,3<<20)
        self.files={};self.fds={};self.nextfd=8;self.fail=None;self.chunk=3
    def setter(self):
        self.native=self.x(0);self.calls.append(('native_set',self.native))
        self.u.mem_write(self.bias+0x7f1cc20,p32(self.native));self.ret()
    def u64(self,at):return struct.unpack('<Q',self.u.mem_read(at,8))[0]
    def u32(self,at):return struct.unpack('<I',self.u.mem_read(at,4))[0]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ap',type=Path,default=HERE/'ap-candidate-d/appFw-NONINSTALLABLE.so')
    p.add_argument('--build',type=Path,default=HERE/'compile-guide-d')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert not a.output.exists(),'Never overwrite an earlier receipt'
    checks=[];cases=[]
    def ck(ok,label):
        assert ok,label
        checks.append(label)
    for bias in (0x4000000000,0x6000000000):
        r=FinalAP(a.ap,a.build,bias);desc=bias+0x586b990
        ck(r.u32(desc+0x54)==8,'actual descriptor count8')
        for off,name in [(0x58,'r5_aspect_menu_rows'),(0x78,'r5_aspect_menu_get'),(0x80,'r5_aspect_menu_set'),(0x88,'r5_aspect_menu_commit')]:
            ck(r.u64(desc+off)==r.sy[name],'actual RELA '+name)
        get=r.u64(desc+0x78);setter=r.u64(desc+0x80);commit=r.u64(desc+0x88)
        # Exercise the actual generic broker B and size-alias B in this ELF.
        # Only row lookup/broker endpoint objects are fixture supplied.
        r.call('r5_aspect_menu_init')
        broker=FIX+0x1000;vt=FIX+0x2000;self_=FIX+0x3000;selfvt=FIX+0x4000
        row_get=FIX+0x8000;broker_call=FIX+0x8010;captured=[]
        r.u.mem_write(bias+0x74dc990,p64(broker));r.u.mem_write(broker,p64(vt))
        r.u.mem_write(self_,p64(selfvt));r.u.mem_write(selfvt+0x790,p64(row_get))
        r.u.mem_write(vt+8,p64(broker_call))
        def row_lookup():
            alias=r.x(1)
            addr=bias+0x3f46600+(alias-126)*128 if 126<=alias<=129 else r.sy['r5_aspect_menu_rows']+(alias-0x1660+4)*128
            r.ret(addr)
        def broker_capture():
            captured.append((r.u32(r.x(1)),r.u32(r.x(2))));r.ret()
        r.callbacks[row_get]=row_lookup;r.callbacks[broker_call]=broker_capture
        aliases=list(range(126,130))+list(range(0x1660,0x1664))
        native_size=r.call(bias+0x1bcfd18,126)
        for choice,alias in enumerate(aliases):
            r.call(bias+0x1bc7720,self_,alias)
            ck(captured[-1]==(0x52b,choice if choice<4 else 0),'actual apply hook bounds broker enum')
            ck((r.token()&15)==(0 if choice<4 else choice|8),'actual apply hook retains private token')
            if choice>=4:
                ck(r.call(bias+0x1bcfd18,alias)==native_size,'actual size hook normalizes private alias')
        wires=[]
        for choice in range(8):
            r.call(setter,choice)
            ck(r.native==(choice if choice<4 else 0),'native setter enum bounded')
            ck(r.call(get)==choice,'real getter returns choice'+str(choice))
            alias=126+choice if choice<4 else 0x1660+choice-4
            r.call(commit,alias)
            ck(('native_commit',alias if choice<4 else 126) in r.calls,'native commit alias bounded')
            saved=choice if choice>=4 else 0
            ck(bytes(r.files['custom_aspect_v2.dat'])==struct.pack('<4I',0x32505243,2,saved,~saved&0xffffffff),'descriptor commit record')
            for native in range(4):
                r.call(setter,choice)
                frame=STACK+0x18000;input_=FIX+0x5000
                r.u.mem_write(input_+8,p32(native))
                expected_regs=[(i+1)*0x11223344 for i in range(31)]
                expected_regs[20]=input_;expected_regs[29]=frame;expected_regs[30]=STOP
                for i,v in enumerate(expected_regs):r.putx(i,v)
                for i,q in enumerate(Q):r.u.reg_write(q,((i+1)<<96)|0x8877665544332211)
                simd=[r.u.reg_read(q) for q in Q]
                r.u.reg_write(UC_ARM64_REG_SP,STACK+0x17000)
                r.u.reg_write(UC_ARM64_REG_NZCV,0xa0000000)
                r.u.reg_write(UC_ARM64_REG_FPCR,0x400000);r.u.reg_write(UC_ARM64_REG_FPSR,0x10)
                r.u.emu_start(bias+0x3565f78,bias+0x3565f7c,count=200000)
                ck(r.u.reg_read(UC_ARM64_REG_PC)==bias+0x3565f7c,'final freeze returns native continuation')
                ck(all(r.x(i)==(native if i==1 else v) for i,v in enumerate(expected_regs)),'freeze all GPRs')
                ck([r.u.reg_read(q) for q in Q]==simd,'freeze all SIMD')
                ck(r.u.reg_read(UC_ARM64_REG_NZCV)==0xa0000000 and r.u.reg_read(UC_ARM64_REG_FPCR)==0x400000 and r.u.reg_read(UC_ARM64_REG_FPSR)==0x10,'freeze flags')
                ck(r.u.reg_read(UC_ARM64_REG_SP)==STACK+0x17000,'freeze stack restored')
                frozen=choice if native==0 and choice>=4 else 0
                ck(r.u32(frame+0x74)==frozen,'native eligibility frozen')
                r.call(setter,7 if choice!=7 else 4)
                packet=FIX+0x6000;original=bytes(range(24));r.u.mem_write(packet,original)
                r.putx(0,0x90030001);r.putx(1,packet);r.putx(2,24);r.putx(29,frame)
                r.u.reg_write(UC_ARM64_REG_SP,STACK+0x17000)
                r.u.emu_start(bias+0x3566a44,bias+0x3566a48,count=200000)
                ck(r.u.reg_read(UC_ARM64_REG_PC)==bias+0x3566a48,'final send returns original BL continuation')
                expected=bytearray(original)
                if frozen:expected[8]=frozen+1
                ck(bytes(r.u.mem_read(packet,24))==expected,'final packet only frozen byte8')
                ck(r.calls[-1]==('send',expected.hex()),'original send endpoint observed')
                wires.append(dict(choice=choice,native=native,frozen=frozen,packet=expected.hex()))
        cases.append(dict(bias=hex(bias),relocations=r.relocated,unresolved_external_imports=r.imports,unmodeled_TLS=r.tls,wires=wires))
    result=dict(passed=True,count=len(checks),checks=checks,cases=cases,
        AP_sha256=hashlib.sha256(a.ap.read_bytes()).hexdigest(),module_sha256=hashlib.sha256((a.build/'rx.bin').read_bytes()).hexdigest(),
        actual_sites=['descriptor 0x586b990 RELA','0x3565f78 final B','0x3566a44 final BL'],
        no_runtime_hook_overlay=True,
        fixtures=['ELF relative/defined-symbol relocation model, not complete ld','native setting setter and commit endpoints; actual getter instructions execute','POSIX resolver and in-memory files with short IO','native mutexes','send transport endpoint'],
        limitations=['Does not close native UI cancel event chain','No complete AP startup, IPC, camera filesystem, hardware or encoder','Sound/filter original bytes preserved separately; full runtime integration still gated'])
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),AP_sha256=result['AP_sha256'])))
if __name__=='__main__':main()
