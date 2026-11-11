// 模型放大门与内部比例域生产共用本张记录的精确资格判定。
// 不改本张元数据、公有比例属性或原厂枚举。
.text
.balign 16
.global aspect_playback_zoom_map
.type aspect_playback_zoom_map,%function
aspect_playback_zoom_map:
    cmp w0, #7
    b.ne .Lnative
    stp x29, x30, [sp, #-0x10]!
    add x0, x19, #0x180
    bl aspect_playback_zoom_eligible
    cmp w0, #0
    mov w0, #7
    b.eq .Lmap_restore
    // 调用者只判结果是否为未知值8；零仅解除该门，不回写aspect。
    mov w0, #0
.Lmap_restore:
    ldp x29, x30, [sp], #0x10
    cbnz w0, .Lnative
    ret
.Lnative:
    b aspect_native_zoom_map
.size aspect_playback_zoom_map,.-aspect_playback_zoom_map

// 内部8cc域增加可跟踪的私有资格态；selector只按固定状态选叶。
// 507a复用原生type4/raw8身份，属于8e0/current_use_mic，并非空闲枚举。
.balign 16
.global aspect_playback_zoom_policy
.type aspect_playback_zoom_policy,%function
aspect_playback_zoom_policy:
    ldr w2, [x0, #0xc]
    cmp w2, #0x8cc
    b.ne .Lpolicy_native
    ldr w3, [x1]
    sub w2, w3, #5, lsl #12
    sub w2, w2, #0x4a
    cmp w2, #0x30
    b.hi .Lpolicy_native
    // 新区间504a..5079均保留invalid叶，不能进入原9项表。
    b.ne .Lpolicy_invalid
    adrp x2, aspect_native_zoom_policy_descriptor
    add x2, x2, :lo12:aspect_native_zoom_policy_descriptor
    cmp x0, x2
    b.ne .Lpolicy_invalid
    ldr w2, [x0, #8]
    cmp w2, #0xffd
    b.ne .Lpolicy_invalid
    mov x0, #0
    ret
.Lpolicy_invalid:
    // 非zoomStart仍使用本descriptor原生invalid叶，保留原有拒绝。
    ldr x0, [x0]
    ldr x0, [x0, #0x40]
    ret
.Lpolicy_native:
    ldrsw x2, [x0, #0xc]
    b aspect_native_zoom_policy_continue
.size aspect_playback_zoom_policy,.-aspect_playback_zoom_policy

// 原生property到内部domain转换已完成，x19=property，[x29+2c]=raw。
.balign 16
.global aspect_playback_zoom_domain
.type aspect_playback_zoom_domain,%function
aspect_playback_zoom_domain:
    cmp w19, #0x152
    b.ne .Ldomain_native
    mov w8, #0x5049
    cmp w0, w8
    b.ne .Ldomain_native
    ldr w8, [x29, #0x2c]
    cmp w8, #8
    b.ne .Ldomain_native
    stp x29, x30, [sp, #-0x10]!
    bl aspect_model_lock
    bl aspect_native_current_content
    bl aspect_playback_zoom_eligible
    mov w19, w0
    bl aspect_model_unlock
    cmp w19, #0
    mov w0, #0x5049
    b.eq .Ldomain_restore
    mov w0, #0x507a
.Ldomain_restore:
    ldp x29, x30, [sp], #0x10
.Ldomain_native:
    ldr x19, [sp, #0x10]
    b aspect_native_zoom_domain_continue
.size aspect_playback_zoom_domain,.-aspect_playback_zoom_domain

// x0为已由调用者保护的本张content record；只读，无锁/缓存/外部调用。
.balign 16
.global aspect_playback_zoom_eligible
.type aspect_playback_zoom_eligible,%function
aspect_playback_zoom_eligible:
    ldr w8, [x0]
    cbnz w8, .Lineligible
    // RAW previews use the native RAW slot; Bayer and crop tags remain untouched.
    ldrb w8, [x0, #0xf3]
    cbnz w8, .Lformat_known
    ldrb w8, [x0, #0xf2]
    ldrb w9, [x0, #0xf4]
    orr w8, w8, w9
    cbz w8, .Lineligible
.Lformat_known:
    ldr w8, [x0, #0x1c]
    cmp w8, #7
    b.ne .Lineligible
    ldrb w8, [x0, #0xb80]
    cbz w8, .Lineligible
    ldr w8, [x0, #0xb84]
    ldr w9, [x0, #0xb88]
    ldrb w10, [x0, #0xf3]
    cbnz w10, .Lraw_dimensions
    ldp w10, w11, [x0, #0xc]
    b .Lcheck_dimensions
.Lraw_dimensions:
    ldp w10, w11, [x0, #0x14]
.Lcheck_dimensions:
    cmp w8, w10
    ccmp w9, w11, #0, eq
    b.ne .Lineligible
    adr x10, .Lpairs
    mov w11, #12
.Lnext:
    ldp w12, w13, [x10], #8
    cmp w8, w12
    ccmp w9, w13, #0, eq
    b.eq .Lrecognized
    subs w11, w11, #1
    b.ne .Lnext
.Lineligible:
    mov w0, #0
    ret
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
.size aspect_playback_zoom_eligible,.-aspect_playback_zoom_eligible
