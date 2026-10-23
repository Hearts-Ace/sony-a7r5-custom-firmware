.syntax unified
.thumb
.arch armv7-a
/* No force of native R4. Preserve all live registers over C admission. */
.macro ADMIT fn=r5_grid421_current
 push {r0-r3,r12,lr}
 mov r0,r9
 mov r1,r8
 bl \fn
 cmp r0,#0
 pop {r0-r3,r12,lr}
.endm
.section .text.r5_grid421_guard,"ax",%progbits
.global r5_grid421_guard
.thumb_func
r5_grid421_guard:
 cmp r4,#0
 bne 1f
 ADMIT
 beq 2f
1: mov r0,r9
 ldr pc,=0x230f11
2: ldr pc,=0x230f3f
.ltorg
.section .text.r5_grid421_validator,"ax",%progbits
.global r5_grid421_validator
.thumb_func
r5_grid421_validator:
 /* At 0x2312f0: validator frame has context in r8, output at sp+0x38.
  * Only bridge native unavailable-consumer path for a valid custom table. */
 push {r0-r3,r12,lr}
 mov r0,r8
 ldr r1,[sp,#80]
 bl r5_grid421_current
 cmp r0,#0
 pop {r0-r3,r12,lr}
 beq 1f
 movs r1,#4
 mov.w lr,#4
 ldr pc,=0x2312f5
1: movs r5,#0
 ldr pc,=0x2315c1
.ltorg
.section .text.r5_grid421_retry,"ax",%progbits
.global r5_grid421_retry
.thumb_func
r5_grid421_retry:
 ADMIT r5_grid421_retry_ready
 beq 1f
 /* Original no-change path: republish built bank0 and upload flag.
  * Native block at f94 writes pointer/flag and bank validity together. */
 ldr pc,=0x230f95
1: movw r0,#0xfd14
 ldr pc,=0x230f67
.ltorg
