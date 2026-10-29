.syntax unified
.thumb
.section .text.r5_cp_stage413_gate,"ax",%progbits
.global r5_cp_stage413_gate
.type r5_cp_stage413_gate,%function
.thumb_func
r5_cp_stage413_gate:
 push.w {r0-r5,r12,lr}
 mrs r4,apsr
 mov r0,r6
 mov r1,r5
 bl r5_cp_stage413_consume
 cmp r0,#0
 beq 1f
 msr APSR_nzcvq,r4
 pop.w {r0-r5,r12,lr}
 /* Consumed -> original unlock at496068. Fixed relocation by builder. */
 .hword 0xbf00,0xbf00
1:
 msr APSR_nzcvq,r4
 pop.w {r0-r5,r12,lr}
 /* Exact overwritten native instructions, with equivalent destinations. */
 ldrb r0,[r6]
 cbz r0,2f
 .hword 0xbf00,0xbf00 /* nonzero -> original class compare49604e */
2:
 .hword 0xbf00,0xbf00 /* zero -> original dispatcher496056 */
.size r5_cp_stage413_gate,.-r5_cp_stage413_gate
