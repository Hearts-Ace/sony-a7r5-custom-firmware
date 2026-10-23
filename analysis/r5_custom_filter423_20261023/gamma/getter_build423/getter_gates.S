.syntax unified
.thumb
.arch armv7-a
.section .text.r5_gamma418_table_0,"ax",%progbits
.balign 4
.global r5_gamma418_table_0
.thumb_func
r5_gamma418_table_0:
push {r0-r3,r12,lr}
mrs r12,APSR
ldr r2,=0x107e968
ldr r3,=12
bl r5_gamma422_lookup
mov r10,r0
msr APSR_nzcvq,r12
pop {r0-r3,r12,lr}
ldr pc,=0x41365b
.ltorg
.section .text.r5_gamma418_table_1,"ax",%progbits
.balign 4
.global r5_gamma418_table_1
.thumb_func
r5_gamma418_table_1:
push {r0-r3,r12,lr}
mrs r12,APSR
ldr r2,=0x107e968
ldr r3,=12
bl r5_gamma422_lookup
mov r10,r0
msr APSR_nzcvq,r12
pop {r0-r3,r12,lr}
ldr pc,=0x413d33
.ltorg
.section .text.r5_gamma418_table_2,"ax",%progbits
.balign 4
.global r5_gamma418_table_2
.thumb_func
r5_gamma418_table_2:
push {r0-r3,r12,lr}
mrs r12,APSR
ldr r2,=0x107e968
ldr r3,=12
bl r5_gamma422_lookup
str r0,[sp,#12]
msr APSR_nzcvq,r12
pop {r0-r3,r12,lr}
ldr pc,=0x413f47
.ltorg
.section .text.r5_gamma418_table_3,"ax",%progbits
.balign 4
.global r5_gamma418_table_3
.thumb_func
r5_gamma418_table_3:
push {r0-r3,r12,lr}
mrs r12,APSR
ldr r2,=0x107e968
ldr r3,=12
bl r5_gamma422_lookup
str r0,[sp,#12]
msr APSR_nzcvq,r12
pop {r0-r3,r12,lr}
ldr pc,=0x413f95
.ltorg
.section .text.r5_gamma418_table_4,"ax",%progbits
.balign 4
.global r5_gamma418_table_4
.thumb_func
r5_gamma418_table_4:
push {r0-r3,r12,lr}
mrs r12,APSR
ldr r2,=0x107e968
ldr r3,=12
bl r5_gamma422_lookup
str r0,[sp,#8]
msr APSR_nzcvq,r12
pop {r0-r3,r12,lr}
ldr pc,=0x41406b
.ltorg
.section .text.r5_gamma418_table_5,"ax",%progbits
.balign 4
.global r5_gamma418_table_5
.thumb_func
r5_gamma418_table_5:
push {r0-r3,r12,lr}
mrs r12,APSR
ldr r2,=0x107e968
ldr r3,=12
bl r5_gamma422_lookup
str r0,[sp,#4]
msr APSR_nzcvq,r12
pop {r0-r3,r12,lr}
ldr pc,=0xaa8aa7
.ltorg
.section .text.r5_gamma418_route_0,"ax",%progbits
.balign 4
.global r5_gamma418_route_0
.thumb_func
r5_gamma418_route_0:
push {r0-r3,r12,lr}
mrs r12,APSR
ldr r2,=0x107eefc
ldr r3,=16
bl r5_gamma422_lookup
str r0,[sp,#8]
msr APSR_nzcvq,r12
pop {r0-r3,r12,lr}
ldr pc,=0xaa830d
.ltorg
.section .text.r5_gamma418_route_1,"ax",%progbits
.balign 4
.global r5_gamma418_route_1
.thumb_func
r5_gamma418_route_1:
push {r0-r3,r12,lr}
mrs r12,APSR
ldr r2,=0x107eefc
ldr r3,=16
bl r5_gamma422_lookup
str r0,[sp,#4]
msr APSR_nzcvq,r12
pop {r0-r3,r12,lr}
ldr pc,=0xaa83a7
.ltorg
.section .text.r5_gamma418_route_2,"ax",%progbits
.balign 4
.global r5_gamma418_route_2
.thumb_func
r5_gamma418_route_2:
push {r0-r3,r12,lr}
mrs r12,APSR
ldr r2,=0x107eefc
ldr r3,=16
bl r5_gamma422_lookup
str r0,[sp,#0]
msr APSR_nzcvq,r12
pop {r0-r3,r12,lr}
ldr pc,=0xaa85bd
.ltorg
.section .text.r5_gamma418_route_3,"ax",%progbits
.balign 4
.global r5_gamma418_route_3
.thumb_func
r5_gamma418_route_3:
push {r0-r3,r12,lr}
mrs r12,APSR
ldr r2,=0x107eefc
ldr r3,=16
bl r5_gamma422_lookup
str r0,[sp,#8]
msr APSR_nzcvq,r12
pop {r0-r3,r12,lr}
ldr pc,=0xaa86b1
.ltorg
.section .text.r5_gamma418_normal_route_0,"ax",%progbits
.balign 4
.global r5_gamma418_normal_route_0
.thumb_func
r5_gamma418_normal_route_0:
push {r0-r3,r12,lr}
mrs r12,APSR
ldr r2,=0xdcc514
ldr r3,=20
bl r5_gamma422_lookup
str r0,[sp,#8]
msr APSR_nzcvq,r12
pop {r0-r3,r12,lr}
ldr pc,=0xaa82dd
.ltorg
.section .text.r5_gamma422_lookup,"ax",%progbits
.balign 4
.global r5_gamma422_lookup
.thumb_func
r5_gamma422_lookup:
push {r4,lr}
ldr r0,=0x1a39458
ldr r0,[r0]
dmb sy
cbz r0,.Lnative
ldr r1,[r0]
ldr r4,=0x423f17e1
cmp r1,r4
bne .Lnative
ldr r0,[r0,r3]
pop {r4,pc}
.Lnative:
mov r0,r2
pop {r4,pc}
.ltorg
