"""Offline CP page-layout experiment; never emits an installation candidate.

The new loader trampoline uses a candidate region after known globals, whose
whole-program ownership is NOT proven. Synthetic replay does not establish
platform initial image-copy bounds or runtime validity. Original proofs stay.
"""
from pathlib import Path
import hashlib,json,struct,sys
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM
BASE=0x108000
TRAMP=0x108f40
RX=0x1196000
STOP=0x1086d4


def branch(at,target,link=False):
    delta=target-at-8
    assert not delta%4 and -(1<<25)<=delta<(1<<25)
    return struct.pack('<I',(0xeb000000 if link else 0xea000000)|((delta>>2)&0xffffff))


def mov16(reg,value,top=False):
    return struct.pack('<I',(0xe3400000 if top else 0xe3000000)|((value&0xf000)<<4)|(reg<<12)|(value&0xfff))


def trampoline():
    result=bytearray(struct.pack('<I',0xe92d4010)) # push{r4,lr}, preserve8bytealignment
    result+=branch(TRAMP+len(result),0x108768,True) # original final native map
    result+=struct.pack('<II',0xe92d500f,0xe10f4000) # save originalmapr0-r3,r12,LR;MRSr4,CPSR
    result+=mov16(0,RX&65535)+mov16(0,RX>>16,True)
    result+=struct.pack('<III',0xe1a02000,0xe3a01a01,0xe3a0300f) # r2=r0;r1=4096;r3=15
    result+=branch(TRAMP+len(result),0x108768,True)
    result+=struct.pack('<III',0xe8bd500f,0xe128f004,0xe8bd8010) # restoreargs/flags/r4;returnPCfromoutercall
    assert len(result)==52
    return bytes(result)


def replay(code,extra=False):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
    u.mem_map(0x100000,0x1f00000);u.mem_write(BASE,code)
    u.reg_write(UC_ARM_REG_SP,0x1f00000)
    calls=[]
    def hook(cpu,at,size,_):
        args=[cpu.reg_read(x) for x in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]]
        if at==0x108768:
            calls.append(args);return
        if at==0x108a04:cpu.mem_write(args[0],bytes(cpu.mem_read(args[1],args[2])))
        elif at in (0x108974,0x1089e4,0x108c54):pass
        elif at==STOP:cpu.emu_stop();return
        else:return
        cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    u.emu_start(0x108398,STOP,count=600000)
    assert u.reg_read(UC_ARM_REG_PC)==STOP
    def pte(va):
        first=struct.unpack('<I',u.mem_read(0x1a3c000+(va>>20)*4,4))[0]
        assert first&3==1
        return struct.unpack('<I',u.mem_read((first&0xfffffc00)+((va>>12)&255)*4,4))[0]
    pages={hex(va):pte(va) for va in [0x108000,0x128000,0x1194000,0x1195000,0x1196000,0x1197000]}
    state={str(r):u.reg_read(r) for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,
        UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,
        UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_CPSR]}
    return calls,pages,state


def main():
    cp=(ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin').read_bytes()
    assert hashlib.sha256(cp).hexdigest()=='8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32'
    assert cp[0xf20:0x1000]==bytes(0xe0)
    assert cp[0x108d070:0x108f000]==bytes(0x1f90)
    assert cp[0x6d0:0x6d4]==branch(0x1086d0,0x108768,True)
    code=trampoline();candidate=bytearray(cp)
    candidate[0xf40:0xf40+len(code)]=code
    candidate[0x6d0:0x6d4]=branch(0x1086d0,TRAMP,True)
    struct.pack_into('<I',candidate,0x20140,0x118000)
    before,old_pages,old_state=replay(cp)
    after,new_pages,new_state=replay(bytes(candidate),True)
    assert old_state==new_state,(old_state,new_state)
    assert len(after)==len(before)+1
    assert after[-1]==[RX,4096,RX,15]
    assert all(after[i]==before[i] for i in range(len(before)) if i!=3)
    assert after[3]==[0x107f000,0x118000,0x107f000,12]
    assert new_pages['0x1196000']==0x119663e
    assert new_pages['0x1195000']==old_pages['0x1195000']==0x119541f
    assert new_pages['0x1197000']==old_pages['0x1197000']==0x119741f
    # NativeARMsmallpagedescriptors: XNbit0; AP[2]=bit9,AP[1:0]=bits5:4.
    def permissions(desc):
        return {'XN':bool(desc&1),'AP':((desc>>7)&4)|((desc>>4)&3)}
    assert permissions(new_pages['0x1196000'])=={'XN':False,'AP':7}
    assert permissions(new_pages['0x1195000'])=={'XN':True,'AP':1}
    asm='\n'.join(f'{i.address:#x} {i.bytes.hex()} {i.mnemonic} {i.op_str}' for i in Cs(CS_ARCH_ARM,CS_MODE_ARM).disasm(code,TRAMP))+'\n'
    (OUT/'rx_page_trampoline_v2.asm').write_text(asm)
    (OUT/'rx_page_trampoline_v2.bin').write_bytes(code)
    report=dict(schema='r5-405-cp-single-RX-page-evaluation/1',status='UNBOUND_LAYOUT_EXPERIMENT',
        camera_io=False,full_candidate_written=False,DAT_generated=False,
        execution_source=dict(path=Path(__file__).name,sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        trampoline_sha256=hashlib.sha256(code).hexdigest(),
        source_sha256=hashlib.sha256(cp).hexdigest(),
        loader=dict(detour_file='0x6d0',original_call='0x108768',candidate_trampoline_va=hex(TRAMP),bytes=len(code),
            scope='Original finalmap replayed, one native map appended before0x1086d4.',
            header_copy_end='0x108f1c',native_global_pointer_end='0x108f20',candidate_region_end='0x109000',
            region_ownership_proven=False,reason='Zero tail beyond known globals is bounded and native-mapped, but no whole-platform ownership proof.'),
        layout=dict(initialized_data_end='0x1197000',data_RW_NX_range=['0x107f000','0x1196000'],
            new_RX_page=['0x1196000','0x1197000'],BSS_start='0x1197000',
            single_bank_candidate=dict(coefficients=['0x1195080','0x1195140'],Gamma6=['0x1195140','0x1195ec0'],
                metadata=['0x1195ec0','0x1195f00'],spare=['0x1195f00','0x1196000']),
            former_dual_bank_layout_incompatible=True,old_layout_candidate_unchanged=True),
        actual_loader_and_native_mapper_replay=dict(original_mapping_calls=before,candidate_mapping_calls=after,
            original_page_descriptors={k:hex(v) for k,v in old_pages.items()},
            candidate_page_descriptors={k:hex(v) for k,v in new_pages.items()},
            permissions={k:permissions(v) for k,v in new_pages.items()},
            all_r0_r12_SP_LR_CPSR_equal_at_original_continuation=True,
            RX_small_page_AP7_readonly=True,data_remains_privileged_RW_XN=True,BSS_unchanged=True),
        unresolved=['Platform firststage initial CP image copy/source bound not established.',
            'Candidate bootstrap52byte region wholeplatform ownership unproven.',
            'SingleGamma bank requires rendering/update mutualexclusion; no lease/lock implemented.',
            'NewRX payload dispatch/initialization, code cache lifecycle and actual CP runtime acceptance not proven.'])
    (OUT/'rx_page_evaluation_v2.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'native_mapper_replay':True,'RX_page':hex(RX),'RX_PTE':hex(new_pages[hex(RX)]),
        'loader_trampoline_bytes':len(code),'full_candidate_written':False,'ownership_proven':False}))


if __name__=='__main__':main()
