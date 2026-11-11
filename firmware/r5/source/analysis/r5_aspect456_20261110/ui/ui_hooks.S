/* Verified non-PC-relative displaced instructions from exact4.55. */
.macro trampoline name, insn, target
.section .text.\name,"ax",%progbits
.global \name
.type \name,%function
\name:
    \insn
    b \target
.size \name,.-\name
.endm
trampoline r5_ui_original_guide_model_0, "add x0,x0,#0x4f,lsl #12", r5_ui_native_guide_model_0_continue
trampoline r5_ui_original_guide_model_1, "add x0,x0,#0x47,lsl #12", r5_ui_native_guide_model_1_continue
trampoline r5_ui_original_guide_update, "stp x29,x30,[sp,#-0x20]!", r5_ui_native_guide_update_continue
trampoline r5_ui_original_guide_destroy, "stp x29,x30,[sp,#-0x20]!", r5_ui_native_guide_destroy_continue

/* Bypass only the static show test inside the eligible scoped producer.
 * Other parameters retain the original CBNZ, GPRs, NZCV and stack state. */
.section .text.r5_ui_guide_show,"ax",%progbits
.global r5_ui_guide_show
.type r5_ui_guide_show,%function
r5_ui_guide_show:
    stp x9,x10,[sp,#-0x20]!
    str x11,[sp,#0x10]
    mrs x11,nzcv
    adrp x9,r5_ui_guide_cookie
    ldr x9,[x9,:lo12:r5_ui_guide_cookie]
    cmp x9,x20
    b.eq 1f
    msr nzcv,x11
    ldr x11,[sp,#0x10]
    ldp x9,x10,[sp],#0x20
    cbnz w0,2f
    b r5_ui_native_guide_show_yes
2:  b r5_ui_native_guide_show_no
1:  msr nzcv,x11
    ldr x11,[sp,#0x10]
    ldp x9,x10,[sp],#0x20
    b r5_ui_native_guide_show_yes
.size r5_ui_guide_show,.-r5_ui_guide_show
