.syntax unified
.thumb
.arch armv7-a
.section .text.r5_grid420_builder,"ax",%progbits
.global r5_grid420_builder
.thumb_func
r5_grid420_builder:
 push {r4,r5,r6,lr}
 mov r4,r0
 mov r5,r1
 bl r5_grid420_builder_original
 push {r0-r3,r12,lr}
 mov r0,r4
 mov r1,r5
 bl r5_grid420_built
 pop {r0-r3,r12,lr}
 pop {r4,r5,r6,pc}
.global r5_grid420_builder_original
.thumb_func
r5_grid420_builder_original:
 push {r4,r5,r6,r7,lr}
 add r7,sp,#12
 nop
 nop
.section .text.r5_grid420_upload,"ax",%progbits
.global r5_grid420_upload
.thumb_func
r5_grid420_upload:
 push {r4,r5,r6,lr}
 mov r4,r3
 ldrb r5,[r3,#0x18]
 ldr r6,[r3,#0x14]
 ldrb.w r12,[r0,#0x660]
 cmp r12,#0
 ite ne
 ldrne.w r12,[r0,#0x194]
 ldreq.w r12,[r0,#0x184]
 cmp r12,#0
 it eq
 moveq r5,#0

 /* Native uploader has two stack arguments; preserve their positions. */
 sub sp,#8
 ldr r12,[sp,#24]
 str r12,[sp]
 cmp r12,#0
 it ne
 movne r5,#0
 ldr r12,[sp,#28]
 str r12,[sp,#4]
 bl r5_grid420_upload_original
 add sp,#8
 push {r0-r3,r12,lr}
 mov r0,r4
 mov r1,r5
 mov r2,r6
 bl r5_grid420_uploaded
 pop {r0-r3,r12,lr}
 pop {r4,r5,r6,pc}
.global r5_grid420_upload_original
.thumb_func
r5_grid420_upload_original:
 push {r4,r5,r6,r7,lr}
 add r7,sp,#12
 nop
 nop
