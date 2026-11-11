.text
.balign 4
.global aspect_avcam_heif_entry
aspect_avcam_heif_entry:
    sub sp, sp, #0x50
    stp x0, x1, [sp]
    stp x2, x3, [sp, #0x10]
    stp x4, x5, [sp, #0x20]
    stp x6, x7, [sp, #0x30]
    str x30, [sp, #0x40]
    mov x0, x2
    mov x2, x4
    mov w3, w21
    bl aspect_avcam_heif_encode
    mov w8, w0
    ldp x0, x1, [sp]
    ldp x2, x3, [sp, #0x10]
    ldp x4, x5, [sp, #0x20]
    ldp x6, x7, [sp, #0x30]
    ldr x30, [sp, #0x40]
    add sp, sp, #0x50
    cbz w8, 1f
    mov w0, w8
    ret
1:
    sub sp, sp, #0xc0
    b aspect_native_encode_body

/* 锁定的1f977c唯一原生caller为200a68。
 * 其保存的caller x20=ctx、x24=局部geometry；保留仍存活的x9..14。
 */
.global aspect_avcam_heif_request
aspect_avcam_heif_request:
    sub sp, sp, #0x40
    stp x9, x10, [sp]
    stp x11, x12, [sp, #0x10]
    stp x13, x14, [sp, #0x20]
    str x30, [sp, #0x30]
    ldr x0, [sp, #0xe8]
    ldr x1, [sp, #0xc8]
    bl aspect_avcam_heif_origin
    str x0, [sp, #0x80]
    str wzr, [sp, #0x88]
    ldp x9, x10, [sp]
    ldp x11, x12, [sp, #0x10]
    ldp x13, x14, [sp, #0x20]
    ldr x30, [sp, #0x30]
    add sp, sp, #0x40
    b aspect_native_request_body
