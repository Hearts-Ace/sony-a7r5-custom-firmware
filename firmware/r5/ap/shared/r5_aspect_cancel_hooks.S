.text
.p2align 2
.global r5_aspect_original_capture
.type r5_aspect_original_capture,%function
r5_aspect_original_capture:
    stp x29,x30,[sp,#-0x10]!
    b r5_aspect_capture_continue
.global r5_aspect_original_restore
.type r5_aspect_original_restore,%function
r5_aspect_original_restore:
    stp x29,x30,[sp,#-0x20]!
    b r5_aspect_restore_continue
