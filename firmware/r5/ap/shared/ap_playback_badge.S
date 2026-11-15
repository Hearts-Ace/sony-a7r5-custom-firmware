// 回放 badge 只读本张 content info；精确WH与已证原生分类配对，其他声明保留。
.text
.balign 16
.global aspect_playback_badge
.type aspect_playback_badge,%function
aspect_playback_badge:
    ldr w8, [x3]
    cbnz w8, .Lnative
    // RAW preview dimensions must agree with the native dedicated RAW slot.
    ldrb w8, [x3, #0xf3]
    cbnz w8, .Lformat_known
    ldrb w8, [x3, #0xf2]
    ldrb w9, [x3, #0xf4]
    orr w8, w8, w9
    cbz w8, .Lnative
.Lformat_known:
    ldrb w8, [x3, #0xb80]
    cbz w8, .Lnative
    ldr w16, [x3, #0x1c]
    ldr w8, [x3, #0xb84]
    ldr w9, [x3, #0xb88]
    ldrb w10, [x3, #0xf3]
    cbz w10, .Ldimensions_known
    ldp w10, w11, [x3, #0x14]
    cmp w8, w10
    ccmp w9, w11, #0, eq
    b.ne .Lnative
.Ldimensions_known:
    adr x10, .Lpairs
    mov w11, #12
.Lnext:
    ldp w12, w13, [x10], #8
    ldp w14, w15, [x10], #8
    cmp w8, w12
    ccmp w9, w13, #0, eq
    ccmp w16, w14, #0, eq
    b.eq .Lrecognized
    subs w11, w11, #1
    b.ne .Lnext
.Lnative:
    mov w0, #-1
    b aspect_playback_badge_continue
.Lrecognized:
    mov w0, w15
    str w0, [x1, #0x3c]
    ret
.balign 4
.Lpairs:
    .word 9504, 5872, 7, 0x02001e9c
    .word 6240, 3856, 7, 0x02001e9c
    .word 4752, 2936, 7, 0x02001e9c
    // 原生MPR把floor(100W/H)=230..239近似为2.35，AP class6。
    .word 9504, 3976, 6, 0x02001e9d
    .word 6240, 2608, 6, 0x02001e9d
    .word 4752, 1992, 6, 0x02001e9d
    .word 9504, 3976, 7, 0x02001e9d
    .word 6240, 2608, 7, 0x02001e9d
    .word 4752, 1992, 7, 0x02001e9d
    .word 9504, 5136, 7, 0x02001e9e
    .word 6240, 3376, 7, 0x02001e9e
    .word 4752, 2568, 7, 0x02001e9e
.size aspect_playback_badge,.-aspect_playback_badge
