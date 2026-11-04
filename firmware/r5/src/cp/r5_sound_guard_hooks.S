.syntax unified
.arch armv7-a
.thumb
.section .text.r5ss_guard_dispatch,"ax",%progbits
.global r5ss_cp_guard_original
.thumb_func
r5ss_cp_guard_original:
.Lguard_original:
 push {r4-r7,lr}
 add r7,sp,#12
 .hword 0xbf00,0xbf00

.section .text.r5ss_guard_dispatch,"ax",%progbits
.global r5ss_cp_guard_consume
.global r5ss_cp_guard_cleanup
.thumb_func
r5ss_cp_guard_consume:
 ldr r3,=r5_cp_stage413_consume
 ldrb r2,[r0]
 cmp r2,#0xe6
 bne .Ldispatch
 ldr r2,=r5ss_cp_extended_consume
 b 1f
.thumb_func
r5ss_cp_guard_cleanup:
 ldr r2,=0x10a66e0
 ldrb r2,[r2,#2]
 cmp r2,#17
 bne .Lguard_original
 ldr r2,=r5ss_cp_completion_hook
 ldr r3,=r5ss_cp_guard_original
1:
 push {r0-r4,lr}
 bl r5ss_cp_sound_page_error
 cmp r0,#0
 pop {r0-r4,lr}
 it eq
 moveq r3,r2
 .Ldispatch:
 bx r3
 .ltorg
