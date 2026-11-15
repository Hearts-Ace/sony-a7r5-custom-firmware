.syntax unified
.thumb
.arch armv7-a
/* Keep one source lease around the native inner builder. The incoming
 * fifth stack word (native [r7,#8]) carries only the ordinate pointer. */
.section .text.od_gamma_inner,"ax",%progbits
.balign 4
.global od_gamma_inner
.thumb_func
od_gamma_inner:
 push {r4,lr}
 sub sp,sp,#16
 push {r0-r3}
 mov r0,r1
 add r1,sp,#24
 bl od_gamma_acquire
 str r0,[sp,#16]
 pop {r0-r3}
 bl .Lgamma_original
 mov r4,r0
 add r0,sp,#8
 bl od_work_drop
 mov r0,r4
 add sp,sp,#16
 pop {r4,pc}
.thumb_func
.Lgamma_original:
 push {r4-r7,lr}
 add r7,sp,#12
 ldr pc,=0x413641
 .ltorg

/* The native normal path has r2=0, or r2=r6=1 when its force
 * request has been vetoed by the descriptor. A real force path
 * has r2=1,r6!=1, including its invalid-record fallback.
 * r0/r1 are both overwritten by native setup before their next use. */
.section .text.od_gamma_ordinate,"ax",%progbits
.global od_gamma_ordinate
.thumb_func
od_gamma_ordinate:
 ldr r0,[r7,#8]
 cbz r0,3f
 mrs r1,APSR
 cmp r2,#1
 bne 1f
 cmp r6,#1
 bne 2f
1:
 mov r3,r0
2:
 msr APSR_nzcvqg,r1
3:
 str r3,[sp,#0x2c]
 add r0,sp,#0x10
 ldr pc,=0x4138f1
 .ltorg

.section .text.od_cc1_gate,"ax",%progbits
.global od_cc1_gate
.thumb_func
od_cc1_gate:
 push {r0-r6,lr}
 sub sp,sp,#8
 str r6,[sp]
 mov r1,r9
 mov r2,r4
 mov r3,r8
 bl od_cc1
 add sp,sp,#8
 pop {r0-r6,lr}
 ldr pc,=0x71e747
 .ltorg
.section .text.od_b13_gate,"ax",%progbits
.global od_b13_gate
.thumb_func
od_b13_gate:
 push {r0-r5,r12,lr}
 mrs r4,apsr
 mov r0,r6
 mov r1,r3
 bl od_available
 cmp r0,#0
 beq 1f
 msr APSR_nzcvq,r4
 pop {r0-r5,r12,lr}
 ldr pc,=0x71d6f3
1: msr APSR_nzcvq,r4
 pop {r0-r5,r12,lr}
 cmp r3,#53
 beq 2f
 ldr pc,=0x71d6f3
2: ldr pc,=0x71d6d1
 .ltorg
