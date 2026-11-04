.syntax unified
.arch armv7-a
.thumb
.section .text.r5ss_cp_gain_hook,"ax",%progbits
.global r5ss_cp_gain_hook
.thumb_func
r5ss_cp_gain_hook:
 /* Native199884 frame104B; its three verified callers keep the original
  * lookup descriptor at callerSP+0x60. No native stack layout is changed. */
 push {r0-r12,lr}
 mrs r2,apsr
 push {r2,r3}
 ldrb r0,[r5,#4]
 ldrb r1,[r5,#5]
 add r2,sp,#264
 ldr r3,[sp,#164]
 bl r5ss_cp_gain_scalar
 strb r0,[sp,#68]
 str r0,[sp,#8]
 pop {r2,r3}
 msr apsr_nzcvqg,r2
 pop {r0-r12,lr}
 ldr pc,1f
 .balign 4
1: .word 0x1998bf
