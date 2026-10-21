"""Source-bound assembly reconstruction of the native Gamma consumers.

The fifth argument references only 129 custom ordinates (516 bytes); the sixth
references the complete native record for metadata. Both remain immutable
through the synchronous call. Native diagnostic overrides stay native.
This builds objects only; no camera I/O or DAT.
"""
from pathlib import Path
import argparse, hashlib, json, subprocess, sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'vendor/audit-python'))
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
CP=ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin'
EXPECTED='8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32'
RANGES=((0x41363c,0x413d8a,'r5_gamma_native_curve_owned'),
        (0x413df0,0x414120,'r5_gamma_native_wrapper_owned'))
def build(out):
    out.mkdir(parents=True,exist_ok=False)
    data=CP.read_bytes();assert hashlib.sha256(data).hexdigest()==EXPECTED
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); externs={}; lines=['.syntax unified','.thumb','.arch armv7-a','.arch_extension idiv']
    transformations=[]
    for start,end,name in RANGES:
        lines+=['.section .text.'+name+',"ax",%progbits','.balign 4','.global '+name,'.thumb_func',name+':']
        for i in md.disasm(data[start-0x108000:end-0x108000],start):
            lines.append(f'.L{i.address:x}:')
            if i.address in (0x413666,0x413d40):
                reg='r1' if i.address==0x413666 else 'r0'
                lines.append(f'ldr.w {reg}, [r7, #8]')
                transformations.append(dict(site=hex(i.address),reason='fifth argument custom ordinates',original=i.bytes.hex()))
                continue
            if i.address in (0x413922,0x4139cc):
                reg='r5' if i.address==0x413922 else 'r0'
                lines.append(f'ldr.w {reg}, [r7, #12]')
                transformations.append(dict(site=hex(i.address),reason='sixth argument native metadata, independent of custom ordinates',original=i.bytes.hex()))
                continue
            if i.address==0x413e16:
                lines+=['ldr.w r3, [r7, #8]','sub sp, #8','str r3, [sp]',
                        'ldr.w r3, [r7, #12]','str r3, [sp, #4]',
                        'bl r5_gamma_native_curve_owned','add sp, #8']
                transformations.append(dict(site=hex(i.address),reason='forward fifth ordinates and sixth native metadata arguments',original=i.bytes.hex()))
                continue
            op=i.op_str
            if i.mnemonic=='adr' or (i.mnemonic.startswith('add') and ', pc,' in op):
                reg=op.split(',')[0];imm=int(op.rsplit('#',1)[1],0)
                target=((i.address+4)&~3)+imm
                lines.append(f'ldr {reg}, =0x{target:x}')
                transformations.append(dict(site=hex(i.address),reason='preserve original PC-relative data',target=hex(target)))
            elif i.mnemonic.startswith(('b','cb')) and '#0x' in op:
                target=int(op.rsplit('#',1)[1],0)
                if start<=target<end:
                    op=op[:op.rfind('#')]+f'.L{target:x}'
                else:
                    symbol=f'r5_gamma_external_{target:x}';externs[symbol]=(target|(0 if i.mnemonic=='blx' else 1))
                    op=op[:op.rfind('#')]+symbol
                mnemonic='bl' if i.mnemonic=='blx' else i.mnemonic
                lines.append(mnemonic+' '+op)
            else: lines.append(i.mnemonic+' '+op)
        lines+=['.ltorg']
    for symbol,target in externs.items():
        lines+=['.section .text.'+symbol+',"ax",%progbits','.balign 4','.global '+symbol,'.thumb_func',symbol+':',
                'ldr.w pc, [pc, #0]',f'.word 0x{target:x}']
    asm=out/'r5_gamma_owned.S';asm.write_text('\n'.join(lines)+'\n')
    command=['clang','--target=arm-none-eabi','-mthumb','-march=armv7-a','-c',str(asm),'-o',str(out/'r5_gamma_owned.o')]
    subprocess.run(command,check=True)
    record=dict(schema='r5-gamma-owned-reconstruction/2',camera_io=False,installable=False,
                fifth_argument_bytes=516,sixth_argument='complete original native record; metadata only',
                source_sha256=EXPECTED,source_ranges=[dict(start=hex(a),end_exclusive=hex(b),symbol=n)for a,b,n in RANGES],
                transformations=transformations,external_thunks={k:hex(v)for k,v in externs.items()},compile_command=command,
                limitations=['Requires trusted per-request bank identity from integration caller.',
                'Diagnostic override lookup and native metadata remain original; custom pointer is ordinates only.',
                'Reconstruction object alone does not install a firmware hook.'])
    (out/'build.json').write_text(json.dumps(record,indent=2)+'\n');return record
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();print(json.dumps(build(a.output)))
