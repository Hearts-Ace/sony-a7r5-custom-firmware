/* The private menu always uses the native C.Look image, independently of the
 * current Creative Look. Preserve selection, text and every other MID. The
 * displaced CMP must set the original NZCV before the branch at 0x1bd63b8. */
.section .text.r5_filter_menu_icon_query434,"ax",@progbits
.p2align 2
.global r5_filter_menu_icon_query434
.type r5_filter_menu_icon_query434,@function
r5_filter_menu_icon_query434:
 cmp w1, #0x635
 b.ne 1f
 movz w0, #0x2290
 movk w0, #0x0200, lsl #16
 ret
1:
 cmp w1, #0xca4
 b r5_native_menu_icon_continue434
.size r5_filter_menu_icon_query434, .-r5_filter_menu_icon_query434
