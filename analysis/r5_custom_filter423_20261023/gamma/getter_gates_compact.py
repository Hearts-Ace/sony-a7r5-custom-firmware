"""The 11 native Gamma references acquire an independent immutable view.

Every entry still replaces one native MOVT via B.W, saves the original LR and
all scratch registers/APSR, and returns to its exact native continuation.
The common helper is private to these entries and preserves r12 (saved APSR).
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT/'vendor/audit-python'), str(ROOT/'tools'),
               str(ROOT/'research/r5_custom_lut/scripts'), str(HERE)]
from build_r5_m4strict_gamma import TABLE_REFS, ROUTE_REFS, BOUNDS, mov16
SHA="8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32"
from replay_gamma_owned_consumers import link
from build_color_consumers import branch


def build(out, rx=0x1195080):
    out.mkdir(exist_ok=False)
    cp=(ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin').read_bytes()
    assert hashlib.sha256(cp).hexdigest()==SHA
    lines=['.syntax unified','.thumb','.arch armv7-a']
    records=[]
    groups=[('table',TABLE_REFS,0x107e968,12),
            ('route',ROUTE_REFS,0x107eefc,16),
            ('normal_route',[(0xaa82d2-0x108000,0xaa82d8-0x108000,2)],0xdcc514,20)]
    for label,refs,original,custom_offset in groups:
        for index,(_,at,r) in enumerate(refs):
            symbol=f'r5_gamma418_{label}_{index}'
            va=at+0x108000
            assert cp[at:at+4]==mov16(r,original>>16,True)
            lines += [f'.section .text.{symbol},"ax",%progbits','.balign 4',
                      f'.global {symbol}','.thumb_func',symbol+':',
                      'push {r0-r3,r12,lr}','mrs r12,APSR',
                      f'ldr r2,=0x{original:x}',f'ldr r3,={custom_offset}',
                      'bl r5_gamma422_lookup']
            lines += [f'str r0,[sp,#{r*4}]'] if r<=3 else [f'mov r{r},r0']
            lines += ['msr APSR_nzcvq,r12','pop {r0-r3,r12,lr}',
                      f'ldr pc,=0x{va+5:x}','.ltorg']
            records.append(dict(symbol=symbol,offset=at,site=hex(va),resume=hex(va+4),
                register=r,original_pointer=hex(original),custom_bank_offset=custom_offset,
                before=cp[at:at+4].hex()))
    # The single acquire pointer carries one table/route/normal-route bundle.
    # Never use r12 here: it holds the caller's APSR until restored.
    lines += ['.section .text.r5_gamma422_lookup,"ax",%progbits','.balign 4',
              '.global r5_gamma422_lookup','.thumb_func','r5_gamma422_lookup:',
              'push {r4,lr}','ldr r0,=0x1a39458','ldr r0,[r0]','dmb sy',
              'cbz r0,.Lnative','ldr r1,[r0]','ldr r4,=0x423f17e1',
              'cmp r1,r4','bne .Lnative','ldr r0,[r0,r3]','pop {r4,pc}',
              '.Lnative:','mov r0,r2','pop {r4,pc}','.ltorg']
    asm=out/'getter_gates.S';asm.write_text('\n'.join(lines)+'\n')
    obj=out/'getter_gates.o'
    cmd=['clang','--target=arm-none-eabi','-mthumb','-march=armv7-a','-c',str(asm),'-o',str(obj)]
    subprocess.run(cmd,check=True)
    raw,sy=link([obj],base=rx)
    for record in records:
        record['after']=branch(int(record['site'],16),sy[record['symbol']]&~1,False).hex()
    patches=[dict(offset=r['offset'],before=r['before'],after=r['after'],
        reason='shared exact acquire-gated native table reference; zero BSS keeps original') for r in records]
    for at in BOUNDS:
        assert cp[at:at+2]==bytes.fromhex('3328')
        patches.append(dict(offset=at,before='3328',after='4b28',reason='native Gamma bound75'))
    (out/'gates.bin').write_bytes(raw)
    report=dict(schema='r5-native-gamma423-view-gates/1',source_CP_sha256=SHA,
        active_view_va='0x1a39458',view_ready_magic='0x423f17e1',
        RX=hex(rx),code_bytes=len(raw),records=records,patches=patches,
        symbols={k:hex(v) for k,v in sy.items()},compile=cmd,camera_io=False,installable=False,
        lookup_unchanged=False,APSR_in_r12_preserved_by_shared_lookup=True,
        maximum_stack_bytes=32,sources={str(Path(__file__).relative_to(ROOT)):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    (out/'gates.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(code_bytes=len(raw),bytes_saved_from968=968-len(raw),RX=hex(rx),end=hex(rx+len(raw)))))
    return report


if __name__=='__main__':
    build(HERE/'getter_build_compact')
