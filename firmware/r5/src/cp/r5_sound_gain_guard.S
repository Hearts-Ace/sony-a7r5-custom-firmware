/* Always-resident guard; no optional-page instruction runs before PTE+CRC.
 * Original gain/function state, every register and APSR are restored before
 * either exact native fallback or the gain wrapper. */
.syntax unified
.arch armv7-a
.thumb
.section .text.r5ss_cp_guard_gain,"ax",%progbits
.global r5ss_cp_guard_gain
.thumb_func
r5ss_cp_guard_gain:
 sub sp,#8
 push {r0-r3,r12,lr}
 mrs r3,apsr
 push {r3,r4}
 bl r5ss_cp_sound_page_error
 cmp r0,#0
 ite eq
 ldreq r0,=r5ss_cp_gain_hook
 ldrne r0,=.Loriginal_gain+1
 str r0,[sp,#32]
 pop {r3,r4}
 msr apsr_nzcvqg,r3
 pop {r0-r3,r12,lr}
 ldr pc,[sp],#8
.Loriginal_gain:
 ldrb r0,[r5,#4]
 strb r0,[sp,#4]
 ldr pc,1f
 .balign 4
1: .word 0x1998bf
 .ltorg
