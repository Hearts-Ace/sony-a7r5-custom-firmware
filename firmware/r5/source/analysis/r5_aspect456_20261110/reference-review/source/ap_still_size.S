// 当前四个比例的精确尺寸；17个原生参数和全部栈参数原样续接。
.text
.balign 16
.global aspect_native_still_size
.type aspect_native_still_size,%function
aspect_native_still_size:
    ldr w8, [x0]
    cbnz w8, .Lnative
    // RAW uses its dedicated published preview WH, never the inactive main slot.
    ldrb w8, [x0, #0xf3]
    cbnz w8, .Lformat_known
    ldrb w8, [x0, #0xf2]
    ldrb w9, [x0, #0xf4]
    orr w8, w8, w9
    cbz w8, .Lnative
.Lformat_known:
    ldrb w8, [x0, #0xb80]
    cbz w8, .Lnative
    ldr w8, [x0, #0xb84]
    ldr w9, [x0, #0xb88]
    ldrb w10, [x0, #0xf3]
    cbz w10, .Ldimensions_known
    ldp w10, w11, [x0, #0x14]
    cmp w8, w10
    ccmp w9, w11, #0, eq
    b.ne .Lnative
.Ldimensions_known:
    adr x10, .Lpairs
    mov w11, #12
.Lnext:
    ldp w12, w13, [x10], #8
    cmp w8, w12
    ccmp w9, w13, #0, eq
    b.eq .Lrecognized
    subs w11, w11, #1
    b.ne .Lnext
.Lnative:
    stp x29, x30, [sp, #-16]!
    b aspect_native_still_size_body
.Lrecognized:
    mov w0, #1
    ret
.balign 8
.Lpairs:
    .word 9504, 5872
    .word 6240, 3856
    .word 4752, 2936
    .word 9504, 3976
    .word 6240, 2608
    .word 4752, 1992
    .word 7920, 6336
    .word 5200, 4160
    .word 3968, 3168
    .word 9504, 5136
    .word 6240, 3376
    .word 4752, 2568
.size aspect_native_still_size,.-aspect_native_still_size
