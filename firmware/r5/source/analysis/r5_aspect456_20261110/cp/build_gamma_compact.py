"""Same11 native Gamma MOVT contracts with shared preservation/return path."""
from pathlib import Path
import sys,json,hashlib,subprocess
H=Path(__file__).resolve().parent;ROOT=H.parents[2];LIB=ROOT/'projects/firmware/development/shutter-sound-recovery455/src/lib';sys.path.insert(0,str(LIB))
from thumb_ops import TABLE_REFS,ROUTE_REFS,BOUNDS,mov16,branch
from thumb_link import link
RX=0x1195080;BASE=0x108000;raw=(H/'baseline404.bin').read_bytes()
lines=['.syntax unified','.thumb','.arch armv7-a','.text'];records=[]
for kind,(label,refs,orig,off) in enumerate([('table',TABLE_REFS,0x107e968,12),('route',ROUTE_REFS,0x107eefc,16),('normal_route',[(0xaa82d2-BASE,0xaa82d8-BASE,2)],0xdcc514,20)]):
 for i,(_,at,reg) in enumerate(refs):
  name=f'r5_gamma418_{label}_{i}';va=at+BASE;assert raw[at:at+4]==mov16(reg,orig>>16,True)
  lines+=['.balign 4',f'.global {name}', '.thumb_func',name+':','sub sp,#8','push {r0-r3,r12,lr}','mrs r12,APSR',f'adr r3,{name}_config','b shared', '.balign 4',f'{name}_config:',f'.word {hex(va+5)}',f'.byte {reg},{off},{kind},0']
  records.append({'symbol':name,'offset':at,'site':hex(va),'resume':hex(va+4),'register':reg,'original_pointer':hex(orig),'custom_bank_offset':off,'before':raw[at:at+4].hex()})
lines+='''
.balign 4
.thumb_func
shared:
 str r3,[sp,#24]
 ldr r0,=0x1a39458
 ldr r0,[r0]
 dmb sy
 cbz r0,native
 ldr r1,[r0]
 ldr r2,=0x423f17e1
 cmp r1,r2
 bne native
 ldrb r1,[r3,#5]
 ldr r0,[r0,r1]
 b result
native:
 ldrb r1,[r3,#6]
 adr r2,originals
 ldr r0,[r2,r1,lsl #2]
result:
 ldrb r1,[r3,#4]
 ldr r2,[r3]
 str r2,[sp,#24]
 cmp r1,#10
 bne lower
 mov r10,r0
 b restore
lower:
 str r0,[sp,r1,lsl #2]
restore:
 msr APSR_nzcvq,r12
 pop {r0-r3,r12,lr}
 ldr pc,[sp],#8
.balign 4
originals:
 .word 0x107e968,0x107eefc,0xdcc514
.ltorg
'''.strip().splitlines()
(H/'gamma_compact.S').write_text('\n'.join(lines)+'\n');cmd=['clang','--target=arm-none-eabi','-mthumb','-march=armv7-a','-c',str(H/'gamma_compact.S'),'-o',str(H/'gamma_compact.o')];subprocess.run(cmd,check=True);code,sy=link([H/'gamma_compact.o'],base=RX);(H/'gamma_compact.bin').write_bytes(code)
for rec in records:rec['after']=branch(int(rec['site'],0),sy[rec['symbol']]&~1,False).hex()
r={'schema':'r5-gamma-compact/1','RX':hex(RX),'bytes':len(code),'end':hex(RX+len(code)),'records':records,'symbols':{k:hex(v)for k,v in sy.items()},'contract':'all registers incl LR/APSR unchanged except original MOVT target; same acquire view and native pointers','source_CP_sha256':hashlib.sha256(raw).hexdigest(),'remaining':['native old/new instruction equivalence all11entries valid/null/wrongmagic/reg/APSR fixtures']};(H/'gamma_compact.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'bytes':len(code),'end':hex(RX+len(code)),'freed_before1195260':0x1195260-RX-len(code)}))
