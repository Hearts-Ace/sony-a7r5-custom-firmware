.syntax unified
.arch armv7-a
.thumb
.section .text.aspect_resident_dispatch,"ax",%progbits
.balign 4
.global aspect_resident_dispatch
.thumb_func
aspect_resident_dispatch:
 sub sp,#8
 push {r0-r3,r12,lr}
 mrs r12,APSR
 push {r4,r12}
 bl r5ss_cp_sound_page_error
 cmp r0,#0
 beq good
 // Native BSS page remains mapped even when optional immutable pages fail.
 // Retire all private IDs before exact native fallback; never reuse stale IDs.
 ldr r0,=0x1a394a0
 movw r1,#504
 ldr r2,=0x5f58b0
 blx r2
 ldr r0,[sp,#28]
 uxth r0,r0
 adr r1,table
 mov r2,r1
find:
 ldrh r3,[r2],#4
 cmp r0,r3
 bne find
 ldrh r4,[r2,#-2]
 add r4,r1
 // Local .thumb_func differences already carry bit0; set it, never add it.
 orr r4,r4,#1
 b restore
good:
 ldr r4,=aspect_module_dispatch
restore:
 str r4,[sp,#32]
 pop {r4,r12}
 msr APSR_nzcvqg,r12
 pop {r0-r3,r12,lr}
 ldr pc,[sp],#8
.balign 4
table:
 .hword 0xf327,selector-table
 .hword 0xf12d,memcopy-table
 .hword 0xd84b,capture-table
 .hword 0x3567,memcopy-table
 .hword 0x2a13,memcopy-table
 .hword 0xe083,clear-table
 .hword 0x77dd,dimensions-table
 .hword 0x7827,dimensions-table
 .hword 0x7a25,retire-table
 .hword 0x14a9,pool_reset-table
 .hword 0x088f,pool_release-table
 .hword 0xa00f,raw_emb-table
.thumb_func
selector:
 // A private wire must never enter native enum tables if module validation fails.
 push {r0-r2,lr}
 mrs r2,APSR
 sub.w r0,r1,#5
 cmp r0,#3
 it ls
 movls r1,#2
 str.w r1,[r5,#0xcc]
 msr APSR_nzcvqg,r2
 pop {r0-r2,pc}
.thumb_func
retire:
 movw r5,#0x5a18
 bx lr
.thumb_func
pool_reset:
 movs r2,#0
 str r2,[r0]
 bx lr
.balign 4
memcopy:
 ldr pc,=0x5f51bc
capture:
 b.w native_capture
clear:
 ldr pc,=0x5f58b0
dimensions:
 b.w native_dimensions
pool_release:
 b.w native_pool_release
raw_emb:
 b.w native_raw_exif
.ltorg
