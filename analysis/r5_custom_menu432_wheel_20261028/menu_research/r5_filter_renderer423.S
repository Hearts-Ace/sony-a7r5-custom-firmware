/* Preserve the exact original function prologues before rejoining stock code. */
.text
.section .text.r5_native_list_update_original,"ax",@progbits
.global r5_native_list_update_original
.type r5_native_list_update_original,%function
r5_native_list_update_original:
 stp x29,x30,[sp,#-0xe0]!
 b r5_native_list_update_continue
.section .text.r5_native_list_destroy_original,"ax",@progbits
.global r5_native_list_destroy_original
.type r5_native_list_destroy_original,%function
r5_native_list_destroy_original:
 stp x29,x30,[sp,#-0x60]!
 b r5_native_list_destroy_continue
