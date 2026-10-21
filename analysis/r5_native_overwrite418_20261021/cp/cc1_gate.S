.syntax unified
.thumb
.arch armv7-a
.section .text.r5_native418_cc1_gate,"ax",%progbits
.balign 4
.global r5_native418_cc1_gate
.type r5_native418_cc1_gate,%function
.thumb_func
r5_native418_cc1_gate:
 cbnz r1,1f
 push.w {r0-r5,r12,lr}
 mrs r4,apsr
 mov r1,r8
 mov r2,r6
 bl r5_native418_cc1
 str r0,[sp]
 msr APSR_nzcvq,r4
 pop.w {r0-r5,r12,lr}
 /* Keep native722 loop-back intact; resolve only at first coefficient. */
1:
 ldrh r3,[r0,r1]
 adds r5,r4,r1
 .hword 0xbf00,0xbf00
.size r5_native418_cc1_gate,.-r5_native418_cc1_gate
