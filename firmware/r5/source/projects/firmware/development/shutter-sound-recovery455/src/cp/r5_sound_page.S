/* Always-resident code in the original 4.36 private RX mapping.
 * Zero means the actual coarse PTE and every immutable sound byte match.
 * Nonzero means no sound-page instruction may execute. This leaf uses only
 * caller-saved registers. Carry implements the exact reflected CRC32 step.
 */
.syntax unified
.arch armv7-a
.thumb
#ifndef R5SS_SOUND_BYTES
#define R5SS_SOUND_BYTES 1712
#endif
.section .text.r5ss_cp_sound_page_error,"ax",%progbits
.global r5ss_cp_sound_page_error
.thumb_func
r5ss_cp_sound_page_error:
 /* Native MMU init removes the complete bootstrap range [0,128000).
  * Read the active TTBR0 instead of the obsolete bootstrap global108F1C.
  * The native R5 kernel's master and per-core table pools map PA==VA. */
 mrc p15,0,r0,c2,c0,0
 bfc r0,#0,#14
 ldr r0,[r0,#0x68]
 and r1,r0,#3
 cmp r1,#1
 bne .Lbad
 bfc r0,#0,#10
 ldr r0,[r0,#0xe8]
 ldr r1,=0x1a3a63e
 cmp r0,r1
 bne .Lbad
.Lok:
 mov r0,#-1
 movw r1,#R5SS_SOUND_BYTES
 ldr r3,=0xedb88320
 ldr r12,=0x1a3a000
.Lbyte:
 ldrb r2,[r12],#1
 eors r0,r2
 movs r2,#8
.Lbit:
 lsrs r0,r0,#1
 it cs
 eorcs r0,r3
 subs r2,#1
 bne .Lbit
 subs r1,#1
 bne .Lbyte
 ldr r1,=r5ss_guard_expected_crc_inverse
 subs r0,r0,r1
 bx lr
.Lbad:
 movs r0,#1
 bx lr
 .ltorg
