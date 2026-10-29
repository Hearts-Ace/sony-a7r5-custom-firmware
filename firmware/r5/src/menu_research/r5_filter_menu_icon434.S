/* Redirect only the private menu's image query. Preserve native selection,
 * text, routing and every other MID. The displaced CMP must set the same NZCV
 * immediately before the original conditional branch at 0x1bd63b8. */
.section .text.r5_filter_menu_icon_query434,"ax",@progbits
.p2align 2
.global r5_filter_menu_icon_query434
.type r5_filter_menu_icon_query434,@function
r5_filter_menu_icon_query434:
 cmp w1, #0x635
 b.ne 1f
 mov w1, #0x1e6
1:
 cmp w1, #0xca4
 b r5_native_menu_icon_continue434
.size r5_filter_menu_icon_query434, .-r5_filter_menu_icon_query434
