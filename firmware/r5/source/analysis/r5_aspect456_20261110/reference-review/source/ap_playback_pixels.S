// Hook 23dfa30 while X3 is still current content record. Native HLG/meta gates precede site.
.text
.balign 16
.global aspect_playback_pixels
.type aspect_playback_pixels,%function
aspect_playback_pixels:
    // RAW paths must publish the same preview WH in the dedicated RAW slot.
    ldrb w8, [x3, #0xf3]
    cbnz w8, .Lraw_dimensions
    ldrb w8, [x3, #0xf2]
    ldrb w9, [x3, #0xf4]
    orr w8, w8, w9
    cbz w8, .Lnative
    b .Ldimensions_known
.Lraw_dimensions:
    ldp w8, w9, [x3, #0x14]
    cmp w8, w2
    ccmp w9, w0, #0, eq
    b.ne .Lnative
.Ldimensions_known:
    adr x9, .Lpairs
    mov w10, #3
.Lnext:
    ldp w11, w12, [x9], #8
    ldr w13, [x9], #4
    cmp w2, w11
    ccmp w0, w12, #0, eq
    b.eq .Lrecognized
    subs w10, w10, #1
    b.ne .Lnext
.Lnative:
    mov w3, #4320
    b aspect_playback_pixels_continue
.Lrecognized:
    mov w0, w13
    mov w3, #7680
    b aspect_playback_pixels_store
.balign 4
.Lpairs:
    .word 9504, 5872, 0x02001e8d
    .word 4752, 1992, 0x02001e8e
    .word 9504, 5136, 0x02001e8f
.size aspect_playback_pixels,.-aspect_playback_pixels
