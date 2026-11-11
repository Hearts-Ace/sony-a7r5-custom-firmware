#ifndef R5_LUT_DIRECTORY_H
#define R5_LUT_DIRECTORY_H
#include "r5_lut_mount_guard.h"
#include "sd_native_persist.h"

/* Native POSIX services supplied separately. Linux ARM64 flags, signed read /
 * write ABI. No address or device operation is installed by this module. */
struct r5_lut_directory_api {
    int (*open)(const char *,int,unsigned);
    int (*openat)(int,const char *,int,unsigned);
    intptr_t (*read)(int,void *,size_t);
    intptr_t (*write)(int,const void *,size_t);
    int (*close)(int);
    int (*sync)(int);
    int (*renameat)(int,const char *,int,const char *);
    int (*unlinkat)(int,const char *,int);
    int (*dup)(int);
    int *(*error_number)(void);
};
struct r5_lut_directory {
    struct r5_lut_directory_api api;
    int fd,phase,last_errno;
    uint64_t mount_id;
};
/* A fresh zeroed worker-owned object, never reopened/reused. Retains the same
 * directory open-file description for ALL relative operations. /proc fdinfo
 * must expose a nonzero mnt_id exactly matching the verified mountinfo record.
 * Complete snapshots only, no fallback on old kernels. 65537-byte scratch is
 * caller-owned, not event stack. No mkdir/mount/partition/Backup operation.
 * This protects path anchoring, NOT medium health, fsync semantics, namespace
 * mutation inside the directory or users outside this single-owner protocol. */
int r5_lut_directory_acquire(struct r5_lut_directory *,const struct r5_lut_directory_api *,uint8_t *,size_t);
int r5_lut_directory_release(struct r5_lut_directory *);
/* Worker-only factory for the boot transaction. Outputs remain untouched
 * unless this exact acquired directory is READY. Directory object/address and
 * its retained fd must outlive every transaction callback; release only after
 * the owner stops using these operations. Does not start a thread or import. */
int r5_lut_directory_bind_storage(struct r5_lut_directory *,
    struct r5_persist_ops *,struct r5_stage_ops *);
int r5_lut_directory_read_open(void *,const char *,uintptr_t *);
int r5_lut_directory_create(void *,const char *,uintptr_t *);
int r5_lut_directory_read(void *,uintptr_t,uint8_t *,size_t,size_t *);
int r5_lut_directory_write(void *,uintptr_t,const uint8_t *,size_t,size_t *);
int r5_lut_directory_close(void *,uintptr_t);
int r5_lut_directory_sync(void *,uintptr_t);
int r5_lut_directory_open_parent(void *,const char *,uintptr_t *);
int r5_lut_directory_rename(void *,const char *,const char *);
int r5_lut_directory_unlink(void *,const char *);
#endif
