.syntax unified
.thumb
.section .text.aspect_jpeg_copy_hook,"ax",%progbits
.global aspect_jpeg_copy_hook
.type aspect_jpeg_copy_hook,%function
.thumb_func
aspect_jpeg_copy_hook:
    /* The call at 40511A uses only r0-r2; r4 is the native task owner. */
    mov r3,r4
    b aspect_jpeg_request_copy
.size aspect_jpeg_copy_hook,.-aspect_jpeg_copy_hook

.section .text.aspect_thumbnail_clear_hook,"ax",%progbits
.global aspect_thumbnail_clear_hook
.type aspect_thumbnail_clear_hook,%function
.thumb_func
aspect_thumbnail_clear_hook:
    mov r2,r4
    b aspect_thumbnail_request_clear
.size aspect_thumbnail_clear_hook,.-aspect_thumbnail_clear_hook

.section .text.aspect_pool_reset_hook,"ax",%progbits
.global aspect_pool_reset_hook
.type aspect_pool_reset_hook,%function
.thumb_func
aspect_pool_reset_hook:
    push {r0-r3,r12,lr}
    mrs r0,apsr
    push {r0,r4}
    mov r0,r9
    bl aspect_pool_reset
    pop {r0,r4}
    msr apsr_nzcvqg,r0
    pop {r0-r3,r12,lr}
    movs r2,#0
    str r2,[r0]
    bx lr
.size aspect_pool_reset_hook,.-aspect_pool_reset_hook

.macro NOTIFY name,format_offset
.section .text.\name,"ax",%progbits
.global \name
.type \name,%function
.thumb_func
\name:
    push {r0-r3,r12,lr}
    /* Preserve the native fifth argument at the original caller SP. */
    ldr r12,[sp,#24]
    sub sp,#8
    str r12,[sp]
    ldr r12,=0x48b9d9
    blx r12
    add sp,#8
    ldr r0,[sp]
    mov r1,r4
    movw r2,#\format_offset
    ldr r2,[r4,r2]
    bl aspect_notify_dimensions
    pop {r0-r3,r12,pc}
.size \name,.-\name
.endm
NOTIFY aspect_notify_primary_hook,0x5980
NOTIFY aspect_notify_secondary_hook,0x5988

.section .text.aspect_notify_release_hook,"ax",%progbits
.global aspect_notify_release_hook
.type aspect_notify_release_hook,%function
.thumb_func
aspect_notify_release_hook:
    push {r0-r3,r12,lr}
    mov r0,r4
    bl aspect_task_clear
    pop {r0-r3,r12,lr}
    movw r5,#0x5a18
    bx lr
.size aspect_notify_release_hook,.-aspect_notify_release_hook

.syntax unified
.thumb
.section .text.aspect_cp_select_hook,"ax",%progbits
.global aspect_cp_select_hook
.type aspect_cp_select_hook,%function
.thumb_func
aspect_cp_select_hook:
    push {r0-r3, r12, lr}
    mrs r12,apsr
    push {r4,r12}
    ldr r4,=aspect_cp_sequence
    ldr r12,[r4]
    add r12,#1
    str r12,[r4]
    dmb ish
    mov r0, r1
    bl aspect_cp_select
    str.w r0, [r5, #0xcc]
    dmb ish
    ldr r12,[r4]
    add r12,#1
    str r12,[r4]
    dmb ish
    pop {r4,r12}
    msr apsr_nzcvqg,r12
    pop {r0-r3, r12, pc}
.size aspect_cp_select_hook, .-aspect_cp_select_hook

/* Existing reserved sidecar, extended by two reference R5 sequence words. */
.global aspect_cp_sequence
.set aspect_cp_sequence,0x1a39498
.global aspect_cp_selection
.set aspect_cp_selection,0x1a394a0
.global aspect_frozen_sequence
.set aspect_frozen_sequence,0x1a3949c
