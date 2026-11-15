.syntax unified
.arch armv7-a
.thumb
/* Compose owner C snapshots with the unchanged optional aspect routines.
 * Dispatch-by-original-LR cannot be used by a C wrapper: that LR would skip
 * its owner postprocessing. Use the very same validated target table entries
 * and fallback functions, with the real wrapper return LR preserved. */
.macro ASPECT_OWNER name, optional, native
.section .text.\name,"ax",%progbits
.global \name
.thumb_func
\name:
 push {r4-r6,lr}
 push {r0-r3}
 mrs r5,APSR
 bl r5ss_cp_sound_page_error
 cmp r0,#0
 bne 1f
 ldr r4,=\optional
 b 2f
1:
 ldr r0,=0x1a394a0
 movw r1,#504
 ldr r2,=0x5f58b0
 blx r2
 ldr r4,=\native
2:
 pop {r0-r3}
 msr APSR_nzcvqg,r5
 blx r4
 pop {r4-r6,pc}
 .ltorg
.endm
ASPECT_OWNER od_aspect_freeze,od_optional_aspect_freeze,0x5f51bc
ASPECT_OWNER od_aspect_capture,od_optional_aspect_capture,0x4596f5
