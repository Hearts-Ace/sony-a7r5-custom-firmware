.syntax unified
.arch armv7-a
.thumb

.macro GRID_SAVE
 push {r0-r3,r12,lr}
 mrs r12,apsr
 push {r4,r12}
.endm
.macro GRID_RESTORE
 pop {r4,r12}
 msr APSR_nzcvqg,r12
 pop {r0-r3,r12,lr}
.endm

.section .text.od_grid_source_gate,"ax",%progbits
.global od_grid_source_gate
.thumb_func
od_grid_source_gate:
 push {r0-r3,r12,lr}
 mov r0,r9
 mov r1,r8
 bl od_grid_source
 cmp r0,#0
 beq 1f
 subs r0,#1
 str r0,[sp,#8]
 pop {r0-r3,r12,lr}
 ldr.w r0,[r8,#8]
 mov r6,r0
 ldr.w r3,[r8,#0x10]
 ldrb.w r10,[r3,#0xb]
 ldr pc,=0x231069
1:
 pop {r0-r3,r12,lr}
 /* Replay original CMP for adjacent IT. */
 cmp r2,#0
 str.w r2,[r5,#0x184]
 ldr pc,=0x230ee7
 .ltorg

.section .text.od_grid_snapshot_gate,"ax",%progbits
.global od_grid_snapshot_gate
.thumb_func
od_grid_snapshot_gate:
 GRID_SAVE
 adds r0,#0x4c
 bl od_grid_snapshot
 GRID_RESTORE
 ldm.w r1,{r2-r6}
 adds r0,#0x4c
 add.w r0,r0,#0x14
 ldr pc,=0x2310d9
 .ltorg

.section .text.od_grid_packet_gate,"ax",%progbits
.global od_grid_packet_gate
.thumb_func
od_grid_packet_gate:
 GRID_SAVE
 mov r0,r10
 ldr r1,[sp,#24] /* saved native env in r12 */
 bl od_grid_packet
 GRID_RESTORE
 ldrd r0,r1,[r12,#0x44]
 ldr pc,=0x728c13
 .ltorg

.section .text.od_grid_state_clear_gate,"ax",%progbits
.global od_grid_state_clear_gate
.thumb_func
od_grid_state_clear_gate:
 GRID_SAVE
 add.w r0,r2,#0x20
 bl od_grid_field_clear
 GRID_RESTORE
 ldr pc,=0x719f73
 .ltorg

.section .text.od_grid_packet_reset0,"ax",%progbits
.global od_grid_packet_reset0
.thumb_func
od_grid_packet_reset0:
 GRID_SAVE
 add.w r0,r6,#0x350
 bl od_grid_field_clear
 GRID_RESTORE
 ldr pc,=0x71437f
 .ltorg

.section .text.od_grid_packet_reset1,"ax",%progbits
.global od_grid_packet_reset1
.thumb_func
od_grid_packet_reset1:
 GRID_SAVE
 add.w r0,r4,#0x350
 bl od_grid_field_clear
 GRID_RESTORE
 ldr pc,=0x7299d1
 .ltorg

.section .text.od_grid_fixed_reset,"ax",%progbits
.global od_grid_fixed_reset
.thumb_func
od_grid_fixed_reset:
 GRID_SAVE
 ldr r0,=0x18e82ec
 movs r1,#4
 bl od_grid_forget_range
 GRID_RESTORE
 movw r0,#0x7f98
 ldr pc,=0xaacfa5
 .ltorg

/* The only AA entry is wrapped. Original prologue and continuation remain
 * byte-for-byte; the two stacked arguments retain their original ABI. */
.section .text.od_grid_aa_original,"ax",%progbits
.global od_grid_aa_original
.thumb_func
od_grid_aa_original:
 push {r4-r7,lr}
 add r7,sp,#12
 ldr pc,=0x414f49
 .ltorg
