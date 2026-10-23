.syntax unified
.thumb
.arch armv7-a
.section .text.r5_native419_grid_gate,"ax",%progbits
.balign 4
.global r5_native419_grid_gate
.thumb_func
r5_native419_grid_gate:
    push {r0-r3,r12,lr}
    mov r0,r9
    mov r1,r8
    bl r5_native419_grid
    cmp r0,#0
    beq 1f
    str r0,[sp,#8]
    movs r0,#2
    str r0,[sp]
    movs r0,#1
    str r0,[sp,#4]
    /* Preserve native r4: caller uses it to choose active/deferred routes. */
1:
    pop {r0-r3,r12,lr}
    /* Displaced CMP + STR.W; CMP flags feed original IT EQ at 0x230ee6. */
    cmp r2,#0
    str.w r2,[r5,#0x184]
    nop
    nop
