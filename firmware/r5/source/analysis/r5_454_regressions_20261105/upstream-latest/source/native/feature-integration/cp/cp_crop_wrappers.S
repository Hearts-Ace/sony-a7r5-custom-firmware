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

.section .text.aspect_heif_packet_hook,"ax",%progbits
.global aspect_heif_packet_hook
.type aspect_heif_packet_hook,%function
.thumb_func
aspect_heif_packet_hook:
    mov r3,r4
    b aspect_heif_packet_copy
.size aspect_heif_packet_hook,.-aspect_heif_packet_hook

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
    ldr r12,=0x41d62d
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
NOTIFY aspect_notify_primary_hook,0x53e8
NOTIFY aspect_notify_secondary_hook,0x53f0

.section .text.aspect_notify_release_hook,"ax",%progbits
.global aspect_notify_release_hook
.type aspect_notify_release_hook,%function
.thumb_func
aspect_notify_release_hook:
    push {r0-r3,r12,lr}
    mov r0,r4
    bl aspect_task_clear
    pop {r0-r3,r12,lr}
    mov.w r5,#0x5480
    bx lr
.size aspect_notify_release_hook,.-aspect_notify_release_hook
