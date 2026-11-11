.syntax unified
.arch armv7-a
.thumb
.section .text.aspect_module_dispatch,"ax",%progbits
.global aspect_module_dispatch
.thumb_func
aspect_module_dispatch:
 sub sp,#8
 push {r0-r3,r12,lr}
 mrs r12,APSR
 uxth r0,lr
 adr r1,table
loop:
 ldrh r2,[r1],#8
 cmp r0,r2
 bne loop
 ldr r0,[r1,#-4]
 str r0,[sp,#24]
 msr APSR_nzcvqg,r12
 pop {r0-r3,r12,lr}
 ldr pc,[sp],#8
.balign 4
table:
 .hword 0xf327,0
 .word aspect_cp_select_hook
 .hword 0xf12d,0
 .word aspect_freeze_copy
 .hword 0xd84b,0
 .word aspect_capture_copy
 .hword 0x3567,0
 .word aspect_jpeg_copy_hook
 .hword 0x2a13,0
 .word aspect_jpeg_copy_hook
 .hword 0xe083,0
 .word aspect_thumbnail_clear_hook
 .hword 0x77dd,0
 .word aspect_notify_primary_hook
 .hword 0x7827,0
 .word aspect_notify_secondary_hook
 .hword 0x7a25,0
 .word aspect_notify_release_hook
 .hword 0x14a9,0
 .word aspect_pool_reset_hook
 .hword 0x088f,0
 .word aspect_pool_release

 .hword 0xa00f,0
 .word aspect_raw_emb_build
