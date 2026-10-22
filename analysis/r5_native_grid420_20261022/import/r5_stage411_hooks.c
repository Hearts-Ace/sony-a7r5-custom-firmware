/* Exact 4.04 callsites pinned by build_boot_runtime_ap.py. All hooks preserve
 * caller GPR/NZCV, callee-saved state, SIMD and the displaced instruction.
 * Event callees are -mgeneral-regs-only and never do I/O. Branch placeholders
 * are patched only after strict link; they are not executable fallthroughs. */
#define SAVE "sub sp,sp,#704\n" \
 "stp x0,x1,[sp,#0]\nstp x2,x3,[sp,#16]\nstp x4,x5,[sp,#32]\n" \
 "stp x6,x7,[sp,#48]\nstp x8,x9,[sp,#64]\nstp x10,x11,[sp,#80]\n" \
 "stp x12,x13,[sp,#96]\nstp x14,x15,[sp,#112]\nstp x16,x17,[sp,#128]\n" \
 "stp x18,x30,[sp,#144]\nmrs x9,nzcv\nstr x9,[sp,#160]\n" \
 "stp q0,q1,[sp,#176]\nstp q2,q3,[sp,#208]\nstp q4,q5,[sp,#240]\n" \
 "stp q6,q7,[sp,#272]\nstp q8,q9,[sp,#304]\nstp q10,q11,[sp,#336]\n" \
 "stp q12,q13,[sp,#368]\nstp q14,q15,[sp,#400]\nstp q16,q17,[sp,#432]\n" \
 "stp q18,q19,[sp,#464]\nstp q20,q21,[sp,#496]\nstp q22,q23,[sp,#528]\n" \
 "stp q24,q25,[sp,#560]\nstp q26,q27,[sp,#592]\nstp q28,q29,[sp,#624]\n" \
 "stp q30,q31,[sp,#656]\nmrs x9,fpcr\nstr x9,[sp,#688]\n" \
 "mrs x9,fpsr\nstr x9,[sp,#696]\n"
#define RESTORE "ldr x9,[sp,#688]\nmsr fpcr,x9\nldr x9,[sp,#696]\nmsr fpsr,x9\n" \
 "ldr x9,[sp,#160]\nmsr nzcv,x9\n" \
 "ldp x0,x1,[sp,#0]\nldp x2,x3,[sp,#16]\nldp x4,x5,[sp,#32]\n" \
 "ldp x6,x7,[sp,#48]\nldp x8,x9,[sp,#64]\nldp x10,x11,[sp,#80]\n" \
 "ldp x12,x13,[sp,#96]\nldp x14,x15,[sp,#112]\nldp x16,x17,[sp,#128]\n" \
 "ldp x18,x30,[sp,#144]\n" \
 "ldp q0,q1,[sp,#176]\nldp q2,q3,[sp,#208]\nldp q4,q5,[sp,#240]\n" \
 "ldp q6,q7,[sp,#272]\nldp q8,q9,[sp,#304]\nldp q10,q11,[sp,#336]\n" \
 "ldp q12,q13,[sp,#368]\nldp q14,q15,[sp,#400]\nldp q16,q17,[sp,#432]\n" \
 "ldp q18,q19,[sp,#464]\nldp q20,q21,[sp,#496]\nldp q22,q23,[sp,#528]\n" \
 "ldp q24,q25,[sp,#560]\nldp q26,q27,[sp,#592]\nldp q28,q29,[sp,#624]\n" \
 "ldp q30,q31,[sp,#656]\nadd sp,sp,#704\n"
__attribute__((naked)) void r5_stage411_startup_hook(void) {
 __asm__ volatile(SAVE "bl r5_stage411_startup\n" RESTORE
   "ldrb w0,[x19,#0xba8]\n.word 0xd503201f\n");
}
__attribute__((naked)) void r5_stage411_initial_hook(void) {
 __asm__ volatile(SAVE "mov w0,w21\nmov w1,w22\nbl r5_stage411_initial\n" RESTORE
   "add x0,x19,#0x430\n.word 0xd503201f\n");
}
__attribute__((naked)) void r5_stage411_completed_hook(void) {
 __asm__ volatile(SAVE "mov w0,w20\nbl r5_stage411_completed\n" RESTORE
   "add x0,x19,#0x430\n.word 0xd503201f\n");
}
__attribute__((naked)) void r5_stage411_media_hook(void) {
 __asm__ volatile(SAVE "ldr w0,[x28,#0x1c]\nldr w1,[x29,#0x13d0]\n"
   "mov x3,#0x13d4\nldrb w2,[x29,x3]\nbl r5_stage411_media\n" RESTORE
   "add x0,x29,x22\n.word 0xd503201f\n");
}

/* Source getter has already stored w20; original packet remains x19.
 * Full caller context includes SIMD because native size getter may use it. */
__attribute__((naked)) void r5_stage411_inbound_hook(void) {
 __asm__ volatile(SAVE "mov x0,x19\nmov w1,w20\nbl r5_stage411_inbound\n"
   "cbz w0,1f\n" RESTORE ".word 0xd503201f\n"
   "1:\n" RESTORE "mov w0,#1\n.word 0xd503201f\n");
}
