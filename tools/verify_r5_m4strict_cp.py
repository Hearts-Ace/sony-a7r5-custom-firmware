#!/usr/bin/env python3
"""Replay the changed R5 CP gates and matrix reader in synthetic Unicorn state.

No USB, flash, camera I/O, or deployment. Writes only requested output validation evidence. Checks final CP from R5 stock.
"""
import argparse
import json
from pathlib import Path
import struct

from build_r5_m4strict_cp import build, ROOT, OUT, BASE, SOURCE_SHA, require, sha
from verify_r5_m4strict_cp_cpu import new_cpu, SCRATCH, SP, STOP, w32
from sony_bk4 import find_banks
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *

REGS=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,
      UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,
      UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12,UC_ARM_REG_SP,UC_ARM_REG_LR]


def reset_regs(u):
    u.reg_write(UC_ARM_REG_CPSR,0x30)
    for i,r in enumerate(REGS):u.reg_write(r,0x110000+i*0x111)
    u.reg_write(UC_ARM_REG_SP,SP)
    u.reg_write(UC_ARM_REG_LR,STOP|1)


def run_gate(u,g,value):
    reset_regs(u)
    u.reg_write(REGS[g['index_register']],value)
    stops={BASE+g['fallback'],BASE+g['old_continue'],BASE+g['new_continue']}
    state={}
    def hook(cpu,at,size,data):
        if at in stops:
            state['pc']=at-BASE
            cpu.emu_stop()
    h=u.hook_add(UC_HOOK_CODE,hook)
    try:u.emu_start((BASE+g['gate'])|1,STOP,count=80)
    finally:u.hook_del(h)
    require('pc' in state,'Gate did not reach a declared native continuation')
    return state['pc'],[u.reg_read(r) for r in REGS],u.reg_read(UC_ARM_REG_CPSR)&0xf0000000


def get_prop(path,key):
    matches=[]
    for bank in find_banks(path.read_bytes()):
        try:matches.append(bank.property(key).data)
        except KeyError:pass
    require(len(matches)==1,'Expected one property')
    return matches[0]


def matrix_cpu(code,prop):
    u=new_cpu(code)
    u.mem_write(0x16b3414,prop)
    w32(u,SCRATCH+0x1000+4,SCRATCH+0x2000)
    return u


def matrix_run(u,profile,slot,calibration):
    reset_regs(u)
    dst=SCRATCH+0x4000
    u.mem_write(dst,b'\xa5'*64)
    u.mem_write(SCRATCH+0x2000+0x1a0,struct.pack('<3H',*calibration))
    for r,value in [(UC_ARM_REG_R0,dst),(UC_ARM_REG_R1,slot),(UC_ARM_REG_R2,SCRATCH+0x1000),(UC_ARM_REG_R3,profile)]:
        u.reg_write(r,value)
    u.emu_start((BASE+0x61641e)|1,STOP,count=1500)
    require(u.reg_read(UC_ARM_REG_PC)==STOP,'Matrix reader failed to return')
    return bytes(u.mem_read(dst,64))


def expected_matrix(block,profile,slot,cal):
    bank=block[0x196+profile]
    if bank>0x37:bank=0
    if slot>15:slot=0
    require(bank<32,'New FL matrix uses regular banks')
    result=[]
    for group in range(3):
        a,b,c,d,e,f=struct.unpack_from('<6H',block,0x1e0+bank*0x300+group*0xc0+slot*12)
        result += [(a+b+cal[0])&65535,(-a)&65535,(-b)&65535,
                   (-c)&65535,(c+d+cal[1])&65535,(-d)&65535,
                   (-e)&65535,(-f)&65535,(e+f+cal[2])&65535]
    return struct.pack('<27H',*result)+b'\xa5'*10


def verify_selectors_and_readers(before,after):
    from verify_r5_m4strict_cp_cpu import full_selector, lookup
    original=get_prop(ROOT/'unpacked/r5/firmware/0110_backup/SYSIPSX-DSLR/GL/CX89201_CN2.bin',0x02a40001)
    donor=get_prop(sorted((ROOT/'unpacked/fx2/firmware/0110_backup').rglob('*ALLLANG.bin'))[0],0x02a40001)
    require(before[0x6169c8:0x616b40]==after[0x6169c8:0x616b40],'Unrequested alternate-reader changes')
    old_runs=new_runs=0
    for mode in ('still','movie'):
        for color in list(range(19))+list(range(21,35))+[255]:
            for scene in (0,5,9,11,17,25,32,37,43):
                for variant in (0,1,2,4,8,9,16,25):
                    a,c0=full_selector(before,color,mode,scene,variant,original)
                    b,c1=full_selector(after,color,mode,scene,variant,original)
                    require(a==b and c0==c1,'Original selector regression')
                    old_runs+=2
        for color,profile in ((19,54 if mode=='still' else 56),(20,55 if mode=='still' else 57)):
            for scene in (0,5,9,11,17,25,32,37,43):
                for variant in (0,1,2,4,8,9,16,25):
                    a,c0=full_selector(before,15,mode,scene,variant,original)
                    b,c1=full_selector(after,color,mode,scene,variant,original)
                    expected=bytearray(a)
                    if a[1]==(41 if mode=='still' else 45):expected[1]=profile
                    require(b==bytes(expected),'New selector does not match R5 native FL contract')
                    require('0xa05e92' not in c1,'New selector reaches invalid-color logger')
                    new_runs+=2
    reader_runs=0
    for entry in (0x616670,0x6169c8):
        for mode in (0,1,2):
            for profile in range(256):
                for adjust in ([0]*8,[-32768,32767]*4):
                    a,c0=lookup(before,entry,profile,mode,adjust,original)
                    b,c1=lookup(after,entry,profile,mode,adjust,original)
                    if entry==0x6169c8 or profile not in range(54,58):
                        require(a==b and c0==c1,'Original CC1 behavior regression')
                    reader_runs+=2
    donor_runs=0
    for profile,bank in ((54,22),(55,24),(56,23),(57,25)):
        row=donor[0x1250+64*bank:0x1290+64*bank]
        for adjust in ([0]*8,[-32768,32767]*4,[32767,-32768]*4):
            got,calls=lookup(after,0x616670,profile,0,adjust,original)
            require(struct.unpack('<24H',got[:48])==tuple((v+adjust[i%8]) & 65535 for i,v in enumerate(struct.unpack('<24h',row[:48]))),'Embedded CC1 differs from FX2 evaluated coefficients')
            donor_runs+=1
    return {'original_selector_instruction_runs':old_runs,'new_selector_native_FL_contract_runs':new_runs,
            'reader_instruction_runs':reader_runs,'new_direct_coefficients_donor_arithmetic_runs':donor_runs,
            'new_coefficients_verified_with_unmodified_R5_settings':True,'alternate_reader_byte_identical_to_stock':True,
            'helper_stubs':['62efd2/62c792 return declared synthetic 0/1','a05e92 invalid-color logger records call then returns','61674e adjustment helper injects declared vector','61a396 diagnostic helper records call then returns']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--without-gamma',action='store_true')
    parser.add_argument('--build',type=Path,default=OUT)
    args=parser.parse_args()
    out=args.build.resolve()
    before,after,patches,manifest=build(not args.without_gamma)
    u0,u1=new_cpu(before),new_cpu(after)
    report={'scope':'Real Thumb instruction replay, changed gates and complete matrix reader only; synthetic memory/calibration; no device or ISP execution',
            'source_sha256':sha(before),'output_sha256':sha(after),'gamma_included':not args.without_gamma,
            'gate_results':[]}
    values=list(range(256))+[0xffffffff,0x100,0x80000000]
    for g in manifest['gates']:
        old_cases=new_cases=0
        for value in values:
            r0=run_gate(u0,g,value)
            r1=run_gate(u1,g,value)
            if value not in g['new_values']:
                require(r0==r1,f'Original gate regression {g["reason"]}/{value}: {r0} vs {r1}')
                old_cases+=1
            else:
                require(r1[0]==g['new_continue'],'New gate wrong continuation')
                index=g['new_values'].index(value)
                if g['names']:
                    addr=r1[1][1]
                    require(bytes(u1.mem_read(addr,4))==b'FL'+bytes([ord('2')+index])+b'\0','Wrong new name')
                    if g['result_register']==6:require(r1[1][0]==r1[1][6],'Slot name destination not preserved')
                else:
                    expected=(54 if g['reason'].startswith('consumer') else 22)+index
                    require(r1[1][g['result_register']]==expected,'Wrong new profile/metadata enum')
                new_cases+=1
        report['gate_results'].append({'name':g['reason'],'original_inputs_equal_registers_flags_destination':old_cases,
                                       'new_inputs_expected':new_cases})
    stockblock=get_prop(ROOT/'unpacked/r5/firmware/0110_backup/SYSIPSX-DSLR/GL/CX89201_CN2.bin',0x02a4000d)
    fxpath=sorted((ROOT/'unpacked/fx2/firmware/0110_backup').rglob('*.bin'))[0]
    fxblock=get_prop(fxpath,0x02a4000d)
    newblock=bytearray(stockblock)
    newblock[0x1cc:0x1d0]=fxblock[0x1cc:0x1d0]
    newblock[0x43e0:0x4fe0]=fxblock[0x43e0:0x4fe0]
    newblock=bytes(newblock)
    m0,m1=matrix_cpu(before,stockblock),matrix_cpu(after,newblock)
    count=0
    for profile in range(256):
        if 0x36<=profile<=0x39:continue
        for slot in (0,1,7,15,16,255):
            for cal in ((0,0,0),(256,256,256),(65535,32768,12345)):
                require(matrix_run(m0,profile,slot,cal)==matrix_run(m1,profile,slot,cal),f'Old matrix regression {profile}/{slot}/{cal}')
                count+=1
    report['matrix_old_cases_equal']=count
    new_count=0
    for profile in range(0x36,0x3a):
        for slot in range(17):
            for cal in ((0,0,0),(256,256,256),(65535,32768,12345)):
                actual=matrix_run(m1,profile,slot,cal)
                require(actual==expected_matrix(newblock,profile,slot,cal),f'New matrix differs from independently expanded donor coefficients {profile}/{slot}/{cal}')
                new_count+=1
    report['matrix_new_cases_match_donor_coefficients']=new_count
    report['matrix_new_block_sha256']=sha(newblock)
    report['matrix_source_block_sha256']=sha(stockblock)
    report['instructions_executed_runs']=2*sum(x['original_inputs_equal_registers_flags_destination']+x['new_inputs_expected'] for x in report['gate_results'])+2*count+new_count
    if not args.without_gamma:
        from build_r5_m4strict_gamma import verify_instruction_paths
        report['gamma_on_final_candidate']=verify_instruction_paths(before,after)
        candidate=out/'patched/cpapp-b.bin'
        require(candidate.read_bytes()==after,'Saved CP differs from the exact candidate just validated')
    report['selectors_and_readers']=verify_selectors_and_readers(before,after)
    report['passed']=True
    report['camera_io']=False
    report['limitations']=['No camera execution, scheduler, complete CP pipeline, hardware image output or live persistence proof.',
                           'All old alternate CC1 reader bytes remain official; its original rejection of new profiles is deliberately retained as in the M4 recipe.',
                           'Gamma must also pass its separately recorded getter/route validation; this script covers other changed CP gates.']
    name='partial_verification.json' if args.without_gamma else 'verification.json'
    (out/'evidence/cp').mkdir(parents=True,exist_ok=True)
    (out/'evidence/cp'/name).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','camera_io','source_sha256','output_sha256','instructions_executed_runs','matrix_old_cases_equal','matrix_new_cases_match_donor_coefficients','selectors_and_readers')},indent=2))


if __name__=='__main__':main()
