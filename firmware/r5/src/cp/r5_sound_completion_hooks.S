.syntax unified
.arch armv7-a
.thumb
.section .text.r5ss_completion_original,"ax",%progbits
.global r5ss_cp_completion_original
.thumb_func
r5ss_cp_completion_original:
 /* Exact overwritten original6549DC..6549DF. */
 push {r4-r7,lr}
 add r7,sp,#12
 /* The reserved sound page is beyond the signed B.W continuation range. */
 ldr pc,1f
 .balign 4
1: .word 0x6549e1
