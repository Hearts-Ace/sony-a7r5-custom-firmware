/* 等价压缩两个原生尺寸 setter，在原 296 字节窗口内增加 JPEG slot 适配。 */
.text
.global aspect_avcam_set_both, aspect_avcam_jpeg, aspect_avcam_set_slot
aspect_avcam_set_both:
    b both
aspect_avcam_jpeg:
    stp x7,x30,[sp,#-0x10]!
    bl aspect_avcam_construct
    ldp x7,x30,[sp],#0x10
    ldr w8,[x20]
    cmp w8,#2
    b.ne done
    ldr w8,[x7]
    cmp w8,#1
    b.ne done
    sub x8,x7,x19
    cmp x8,#0xa4
    add x8,x20,#0x1b6
    add x9,x20,#0x1c2
    csel x8,x8,x9,eq
    b jpeg_tail
.org 64
aspect_avcam_set_slot:
    add x8,x0,#0xa4
    cmp w1,#1
    b.eq slot
    cmp w1,#0x10
    b.ne invalid
    add x8,x0,#0x224
slot:
    ldr w9,[x8]
    sub w9,w9,#1
    cmp w9,#1
    b.ls write_slot
    cmp w9,#3
    b.ne done
write_slot:
    str w2,[x8,#0x20]
    stp w3,wzr,[x8,#0x2c]
    str wzr,[x8,#0x3c]
    str w2,[x8,#0x40]
    str w3,[x8,#0x4c]
    stp w3,w2,[x8,#0x5c]
    stp w3,w2,[x8,#0x6c]
    stp w3,wzr,[x8,#0x7c]
    str w2,[x8,#0x10]
    str w3,[x8,#0x1c]
    str w2,[x8,#0x50]
    stp wzr,w2,[x8,#0x8c]
    str w3,[x8,#0x9c]
    cmp w1,#0x10
    b.ne finish
    ldr w9,[x8,#0x14]
    mov w10,#0xb6b0
    mov w11,#0xb76c
    add w10,w9,w10
    add w9,w9,w11
    str w10,[x8,#0x14]
    str w9,[x8,#0x54]
finish:
    add x0,x8,#0x10
done:
    ret
invalid:
    adrp x0,aspect_avcam_assert_file
    add x0,x0,:lo12:aspect_avcam_assert_file
    adrp x1,aspect_avcam_assert_function
    add x1,x1,:lo12:aspect_avcam_assert_function
    mov w2,#0x471
    b aspect_avcam_assert
jpeg_tail:
    ldrh w2,[x8]
    ldrh w3,[x8,#2]
    mov w9,#0x10
    csinc w1,w9,wzr,ne
    mov x0,x19
    b aspect_avcam_set_slot
both:
    stp x0,x30,[sp,#-0x20]!
    stp w1,w2,[sp,#0x10]
    mov w3,w2
    mov w2,w1
    mov w1,#1
    bl aspect_avcam_set_slot
    ldp w2,w3,[sp,#0x10]
    ldp x0,x30,[sp],#0x20
    mov w1,#0x10
    b aspect_avcam_set_slot
