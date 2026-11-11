.syntax unified
.thumb
.arch armv7-a
.section .text.r5_native418_b13_gate,"ax",%progbits
.balign 4
.global r5_native418_b13_gate
.type r5_native418_b13_gate,%function
.thumb_func
r5_native418_b13_gate:
 /* Replaces cmp r3,#53; bne ordinary. Preserve every live register/APSR;
  * imported BW/SE uses the ordinary native B/A1/A2 matrix consumer, while
  * unimported/special profile53 keeps its native identity-matrix path. */
 push.w {r0-r5,r12,lr}
 mrs r4,apsr
 mov r0,r6
 mov r1,r3
 bl r5_native418_available
 cmp r0,#0
 beq 1f
 msr APSR_nzcvq,r4
 pop.w {r0-r5,r12,lr}
 .hword 0xbf00,0xbf00 /* builder: ordinary71d6f2 */
1:
 msr APSR_nzcvq,r4
 pop.w {r0-r5,r12,lr}
 cmp r3,#53
 beq 2f
 .hword 0xbf00,0xbf00 /* builder: ordinary71d6f2 */
2:
 .hword 0xbf00,0xbf00 /* builder: native53 71d6d0 */
.size r5_native418_b13_gate,.-r5_native418_b13_gate
