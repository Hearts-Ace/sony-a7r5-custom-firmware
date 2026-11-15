.syntax unified
.arch armv7-a
.thumb
/* Early E7 filter receive: perform validation/preparation outside native lock.
 * On a handled frame, the native message is already consumed and the caller
 * continues at the post-unlock free path. Stock frames resume 0x49604a. */
.section .text.r5_receive_early_gate,"ax",%progbits
.global r5_receive_early_gate
.thumb_func
r5_receive_early_gate:
 ldrb r0,[r6]
 eor.w r0,r0,#0xe7
 cbnz r0,2f
 push {r0-r5,r12,lr}
 mrs r4,APSR
 mov r0,r6
 mov r1,r5
 bl r5_cp_stage413_consume
 cmp r0,#0
 beq 1f
 msr APSR_nzcvqg,r4
 pop {r0-r5,r12,lr}
 ldr pc,=0x49606f
1:
 msr APSR_nzcvqg,r4
 pop {r0-r5,r12,lr}
2:
 movs r0,#0x24
 ldr r12,=0x5b8d6c
 blx r12
 ldr pc,=0x49604b
 .ltorg
/* Native 402f dispatcher runs while stock settings lock 0x24 is held. */
.section .text.r5_receive_dispatch_gate,"ax",%progbits
.global r5_receive_dispatch_gate
.thumb_func
r5_receive_dispatch_gate:
 b.w od_native_dispatch
/* Completion ACK executes after unlock and before native message free. */
.section .text.r5_receive_complete_gate,"ax",%progbits
.global r5_receive_complete_gate
.thumb_func
r5_receive_complete_gate:
 push {r0-r3,r12,lr}
 mrs r12,APSR
 push {r4,r12}
 bl od_receive_complete
 pop {r4,r12}
 msr APSR_nzcvqg,r12
 pop {r0-r3,r12,lr}
 ldr r1,[sp]
 mov r0,r4
 ldr pc,=0x496073
 .ltorg

/* Enter the original optional sound guard only on E6. Native message
 * types and zero type retain the displaced LDRB and CBZ semantics. */
.section .text.r5_receive_sound_gate,"ax",%progbits
.global r5_receive_sound_gate
.thumb_func
r5_receive_sound_gate:
 ldrb r0,[r6]
 eor.w r0,r0,#0xe6
 cbz r0,1f
 eor.w r0,r0,#0xe6
 cbz r0,3f
 ldr pc,=0x49604f
1:
 mov.w r0,#0xe6
 push {r0-r5,r12,lr}
 mrs r4,APSR
 mov r0,r6
 mov r1,r5
 bl r5ss_cp_guard_consume
 cmp r0,#0
 beq 2f
 msr APSR_nzcvqg,r4
 pop {r0-r5,r12,lr}
 ldr pc,=0x496069
2:
 msr APSR_nzcvqg,r4
 pop {r0-r5,r12,lr}
 ldr pc,=0x49604f
3:
 ldr pc,=0x496057
 .ltorg
