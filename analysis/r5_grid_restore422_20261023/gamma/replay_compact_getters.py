"""Compare each compact Gamma MOVT detour with the immutable 968-byte gates.

All 15 GPRs including SP/LR, PC, NZCVQ and GE flags are checked, together with
the exact selected output and both native/capacity/ready fallback decisions.
No device execution; source and candidates remain read-only.
"""
from pathlib import Path
import hashlib,json,random,struct,sys
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from verify_r5_m4strict_cp_cpu import new_cpu,SP,STOP
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
OLD=ROOT/'analysis/r5_native_grid420_20261022/gamma/getter_build_dynamic'
NEW=HERE/'getter_build_compact'
CP=ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin'
REGS=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,
      UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,
      UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,
      UC_ARM_REG_R12,UC_ARM_REG_SP,UC_ARM_REG_LR]
BANK=0x3100000

def main():
    cp=CP.read_bytes();metas=[json.loads((d/'gates.json').read_text()) for d in (OLD,NEW)]
    assert all(m['source_CP_sha256']==sha(CP) for m in metas)
    assert metas[0]['code_bytes']==968 and metas[1]['code_bytes']==496
    machines=[]
    for directory,meta in zip((OLD,NEW),metas):
        u=new_cpu(cp);u.mem_map(BANK,0x10000)
        u.mem_write(int(meta['RX'],16),(directory/'gates.bin').read_bytes())
        for row in meta['records']:u.mem_write(int(row['site'],16),bytes.fromhex(row['after']))
        state=dict(stop=0,low=SP,stores=0)
        def hook(c,at,size,arg):
            arg['low']=min(arg['low'],c.reg_read(UC_ARM_REG_SP))
            if at==arg['stop']:c.emu_stop()
        def guard(c,access,at,size,value,arg):
            assert SP-32<=at<at+size<=SP,(hex(at),size,hex(c.reg_read(UC_ARM_REG_PC)))
            arg['stores']+=1
        u.hook_add(UC_HOOK_CODE,hook,state)
        u.hook_add(UC_HOOK_MEM_WRITE,guard,state)
        machines.append((u,state))
    rng=random.Random(422);checks=[]
    states=[(0,0,0),(1,BANK,0),(28768,0,0),(28768,BANK,0),
            (28768,BANK,0x4186b11),(28768,BANK,0x4186a11),(28768,BANK,0xffffffff)]
    for oldrow,row in zip(metas[0]['records'],metas[1]['records']):
        for field in ('site','resume','register','original_pointer','custom_bank_offset','before'):
            assert row[field]==oldrow[field]
        for capacity,pointer,ready in states:
            for flags in range(32):
                values=[rng.getrandbits(32) for _ in REGS];values[13]=SP;values[14]|=1
                ge=rng.randrange(16);cpsr=(flags<<27)|(ge<<16)|0x1f3
                results=[]
                for index,(u,state) in enumerate(machines):
                    u.mem_write(0x1a39448,struct.pack('<2I',pointer,capacity))
                    u.mem_write(BANK+51780,struct.pack('<I',ready))
                    for r,v in zip(REGS,values):u.reg_write(r,v)
                    u.reg_write(UC_ARM_REG_CPSR,cpsr)
                    state.update(stop=int(row['resume'],16),low=SP,stores=0)
                    u.emu_start(int(row['site'],16)|1,STOP,count=150)
                    expected=values.copy()
                    expected[row['register']]=BANK+row['custom_bank_offset'] if capacity==28768 and pointer and ready==0x4186a11 else int(row['original_pointer'],16)
                    actual=[u.reg_read(r) for r in REGS]
                    assert actual==expected,(index,row['symbol'],capacity,ready,flags)
                    assert u.reg_read(UC_ARM_REG_PC)==state['stop']
                    assert u.reg_read(UC_ARM_REG_CPSR)&0xf80f0000==cpsr&0xf80f0000
                    assert SP-state['low']==(24 if index==0 else 32)
                    results.append((actual,u.reg_read(UC_ARM_REG_PC),u.reg_read(UC_ARM_REG_CPSR)&0xf80f0000))
                assert results[0]==results[1]
                checks.append(dict(site=row['site'],capacity=capacity,pointer=hex(pointer),ready=hex(ready),NZCVQ=flags,GE=ge))
    meta=metas[1]
    assert int(meta['RX'],16)+meta['code_bytes']<=0x1196000
    report=dict(schema='r5-422-compact-gamma-differential/1',passed=True,camera_io=False,
        hooks=11,checks=len(checks),cases=checks,code_bytes=meta['code_bytes'],old_code_bytes=968,
        bytes_saved=968-meta['code_bytes'],maximum_stack_bytes=32,
        all_GPR_SP_LR_PC_NZCVQ_GE_equal=True,all_capacity_pointer_ready_fallbacks_equal=True,
        stack_writes_only=True,native_Gamma_data_routes_bounds_unchanged=True,
        source_CP_sha256=sha(CP),compact_gates_sha256=sha(NEW/'gates.bin'),
        immutable_old_gates_sha256=sha(OLD/'gates.bin'),
        sources={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),HERE/'getter_gates_compact.py',NEW/'getter_gates.S',NEW/'getter_gates.o',NEW/'gates.json']},
        limits=['Synthetic CPU memory; no device, scheduler or ISP execution.',
                'Compares the private acquire-helper factoring with the old exact detours; integrated final CP Gamma route/consumer regressions remain required.'])
    (HERE/'compact_getter_replay.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',len(checks),'11-hook GPR/SP/LR/PC/NZCVQ/GE differential cases;',meta['code_bytes'],'bytes')

if __name__=='__main__':main()
