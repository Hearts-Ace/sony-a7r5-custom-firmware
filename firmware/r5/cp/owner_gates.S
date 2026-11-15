.syntax unified
.arch armv7-a
.thumb

.macro SAVE_VOLATILES
 push {r0-r3,r12,lr}
 mrs r12,apsr
 push {r4,r12}
.endm
.macro RESTORE_VOLATILES
 pop {r4,r12}
 msr APSR_nzcvqg,r12
 pop {r0-r3,r12,lr}
.endm

.section .text.od_live_color_gate,"ax",%progbits
.global od_live_color_gate
.thumb_func
od_live_color_gate:
 SAVE_VOLATILES
 mov r0,r11
 addw r1,r8,#0xa40
 bl od_field_copy
 RESTORE_VOLATILES
 ldr.w lr,[r8,#0xa40]
 ldr pc,=0x24119f
 .ltorg

.section .text.od_photo_color_gate,"ax",%progbits
.global od_photo_color_gate
.thumb_func
od_photo_color_gate:
 SAVE_VOLATILES
 mov r0,lr
 addw r1,r9,#0x104
 bl od_field_copy
 RESTORE_VOLATILES
 ldr.w r12,[r9,#0x104]
 ldr pc,=0x2429ab
 .ltorg

/* Release root/packet/grid state only when their native stack frame ends. */
.macro FRAME_END name, extent, resume, frame_insn
.section .text.\name,"ax",%progbits
.global \name
.thumb_func
\name:
 SAVE_VOLATILES
 add r0,sp,#32
 movw r1,#\extent
 bl od_native_frame_end
 RESTORE_VOLATILES
 add.w sp,sp,#\frame_insn
 ldr pc,=\resume
 .ltorg
.endm
FRAME_END od_live_frame_end,0x584,0x230bf7,0x580
FRAME_END od_photo_end0,0x8e8,0x71771f,0x8e0
FRAME_END od_photo_end1,0x8e4,0x7179bf,0x8e0
FRAME_END od_photo_end2,0x8e8,0x717c45,0x8e0
FRAME_END od_photo_end3,0x8ec,0x717f41,0x8e0
FRAME_END od_photo_end4,0x8ec,0x71823d,0x8e0
FRAME_END od_photo_end5,0x8e8,0x7184d1,0x8e0
FRAME_END od_photo_end6,0x8e8,0x7187c9,0x8e0
FRAME_END od_photo_end7,0x8e4,0x718acb,0x8e0
FRAME_END od_photo_end8,0x8e8,0x718d51,0x8e0
FRAME_END od_photo_end9,0x8e8,0x718fb7,0x8e0
FRAME_END od_photo_end10,0x8e8,0x71921f,0x8e0
FRAME_END od_photo_end11,0x8ec,0x719585,0x8e0

.section .text.od_task_retire_gate,"ax",%progbits
.global od_task_retire_gate
.thumb_func
od_task_retire_gate:
 SAVE_VOLATILES
 mov r0,r4
 mov r1,r5
 bl od_task_retire
 RESTORE_VOLATILES
 ldr r0,[r4]
 str r0,[r5]
 str r5,[r4]
 ldr pc,=0xae09bf
 .ltorg

.section .text.od_pool_reset_gate,"ax",%progbits
.global od_pool_reset_gate
.thumb_func
od_pool_reset_gate:
 SAVE_VOLATILES
 mov r0,r9
 bl od_owners_pool_reset
 RESTORE_VOLATILES
 b.w aspect_resident_dispatch

.section .text.od_tone_owner_gate,"ax",%progbits
.global od_tone_owner_gate
.thumb_func
od_tone_owner_gate:
 SAVE_VOLATILES
 addw r1,r0,#0xa40
 addw r0,r9,#0xcdc
 bl od_field_copy
 RESTORE_VOLATILES
 ldr.w r1,[r0,#0xa40]
 str.w r1,[r9,#0xcdc]
 ldr pc,=0x314ebf
 .ltorg

/* Attach the exact source output's owner for the synchronous native input
 * copy. The stack descriptor can be reused immediately after the call. */
.section .text.od_pending_send_gate,"ax",%progbits
.global od_pending_send_gate
.thumb_func
od_pending_send_gate:
 push {r4-r6,lr}
 mov r4,r0
 addw r0,r4,#0x10
 addw r1,r8,#0xcdc
 bl od_field_copy
 mov r0,r4
 ldr r3,=0xaacb17
 blx r3
 mov r5,r0
 addw r0,r4,#0x10
 bl od_field_clear
 mov r0,r5
 pop {r4-r6,pc}
 .ltorg

.section .text.od_pending_input_gate,"ax",%progbits
.global od_pending_input_gate
.thumb_func
od_pending_input_gate:
 SAVE_VOLATILES
 addw r0,r4,#0xc
 mov r1,r5
 bl od_field_copy
 RESTORE_VOLATILES
 str r3,[r4,#0xc]
 ldrb.w r10,[r5,#4]
 ldr pc,=0xaa8219
 .ltorg

.section .text.od_gamma_stack_end,"ax",%progbits
.global od_gamma_stack_end
.thumb_func
od_gamma_stack_end:
 SAVE_VOLATILES
 sub.w r0,r7,#0x70
 bl od_field_clear
 RESTORE_VOLATILES
 mov r0,r5
 mov r1,r6
 ldr pc,=0xaa7785
 .ltorg
