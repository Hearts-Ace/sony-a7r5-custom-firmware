.syntax unified
.thumb
.section .text.aspect_cp_select_hook,"ax",%progbits
.global aspect_cp_select_hook
.type aspect_cp_select_hook,%function
.thumb_func
aspect_cp_select_hook:
    push {r0-r3, r12, lr}
    mov r0, r1
    bl aspect_cp_select
    str.w r0, [r5, #0xa8]
    pop {r0-r3, r12, pc}
.size aspect_cp_select_hook, .-aspect_cp_select_hook
