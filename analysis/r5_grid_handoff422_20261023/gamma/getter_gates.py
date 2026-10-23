"""Generate B.W detours replacing MOVT; cold BSS always keeps original tables.

No BL destroys native LR; every shim saves original GPRs/APSR and returns to
one fixed original instruction boundary. Code must be placed in proven RX.
"""
from pathlib import Path
import hashlib,json,subprocess,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools'),str(ROOT/'research/r5_custom_lut/scripts'),str(HERE)]
from patch_native_gamma import TABLE_REFS,ROUTE_REFS,BOUNDS,mov16,SHA
from replay_gamma_owned_consumers import link
from build_color_consumers import branch
def build(out,context_va=None,rx=0x1195080):
 out.mkdir(exist_ok=False)
 cp=(ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin').read_bytes();assert hashlib.sha256(cp).hexdigest()==SHA
 lines=['.syntax unified','.thumb','.arch armv7-a'];records=[]
 for label,refs,original,custom_offset in [('table',TABLE_REFS,0x107e968,28768),('route',ROUTE_REFS,0x107eefc,28768+2100),('normal_route',[(0xaa82d2-0x108000,0xaa82d8-0x108000,2)],0xdcc514,28768+23020)]:
  for index,(_,at,r)in enumerate(refs):
   symbol=f'r5_gamma418_{label}_{index}';va=at+0x108000
   assert cp[at:at+4]==mov16(r,original>>16,True)
   lines += [f'.section .text.{symbol},"ax",%progbits','.balign 4',f'.global {symbol}','.thumb_func',symbol+':','push {r0-r3,r12,lr}','mrs r12,APSR','ldr r0,=0x1a39448','ldr r1,[r0,#4]','dmb sy','ldr r2,=28768','cmp r1,r2',f'bne .L{symbol}_original','ldr r0,[r0]','cmp r0,#0',f'beq .L{symbol}_original','ldr r1,=51780','ldr r1,[r0,r1]','dmb sy','ldr r2,=0x4186a11','cmp r1,r2',f'bne .L{symbol}_original',f'ldr r1,={custom_offset}','add r0,r1',f'b .L{symbol}_selected',f'.L{symbol}_original:',f'ldr r0,=0x{original:x}',f'.L{symbol}_selected:']
   if r<=3:lines += [f'str r0,[sp,#{r*4}]']
   else:lines += [f'mov r{r},r0']
   lines += ['msr APSR_nzcvq,r12','pop {r0-r3,r12,lr}',f'ldr pc,=0x{va+5:x}','.ltorg']
   records.append(dict(symbol=symbol,offset=at,site=hex(va),resume=hex(va+4),register=r,original_pointer=hex(original),custom_bank_offset=custom_offset,before=cp[at:at+4].hex()))
 asm=out/'getter_gates.S';asm.write_text('\n'.join(lines)+'\n');obj=out/'getter_gates.o'
 cmd=['clang','--target=arm-none-eabi','-mthumb','-march=armv7-a','-c',str(asm),'-o',str(obj)];subprocess.run(cmd,check=True)
 raw,sy=link([obj],base=rx)
 for record in records:record['after']=branch(int(record['site'],16),sy[record['symbol']]&~1,False).hex()
 patches=[dict(offset=r['offset'],before=r['before'],after=r['after'],reason='acquire gated native table reference; zero BSS keeps original')for r in records]
 for at in BOUNDS:
  assert cp[at:at+2]==bytes.fromhex('3328');patches.append(dict(offset=at,before='3328',after='4b28',reason='native Gamma bound75'))
 (out/'gates.bin').write_bytes(raw)
 report=dict(schema='r5-native-gamma418-gates/2',source_CP_sha256=SHA,bank_state_va='0x1a39448',context_bank_offset=28768,ready_bank_offset=51780,capacity_word=28768,RX=hex(rx),code_bytes=len(raw),records=records,patches=patches,symbols={k:hex(v)for k,v in sy.items()},compile=cmd,camera_io=False,installable=False)
 (out/'gates.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':build(HERE/('getter_build_'+sys.argv[1]if len(sys.argv)>1 else'getter_build_dynamic'))
