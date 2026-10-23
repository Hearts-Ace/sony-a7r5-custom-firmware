#ifndef R5_LUT_MOUNT_READER_H
#define R5_LUT_MOUNT_READER_H
#include "r5_lut_mount_guard.h"
struct r5_mount_read_api {
    int (*open)(const char *,int,unsigned);
    intptr_t (*read)(int,void *,size_t);
    int (*close)(int);
};
/* Worker-owned scratch >=65537 bytes, retained through return; never a mount
 * callback stack. Up to128 reads, each<=1024. Requires EOF and successful
 * close before checking the entire snapshot; no partial positive result.
 * Does not execute real services until a separate native binder supplies API.
 * Call/byte bounds do not bound underlying synchronous service wall time. */
int r5_lut_mountinfo_read(const struct r5_mount_read_api *,uint8_t *,size_t);
#endif
