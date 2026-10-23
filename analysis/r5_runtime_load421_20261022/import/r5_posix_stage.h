#ifndef R5_POSIX_STAGE_H
#define R5_POSIX_STAGE_H
#include "sd_native_store.h"

/* Observed AP libc calling conventions. Function pointers are supplied by the
 * address binder, never loaded from an SD config. No runtime hook is installed
 * here. Host tests supply actual POSIX calls through the same narrow ABI. */
struct r5_posix_api {
    int (*open_file)(const char *, int, unsigned);
    intptr_t (*write_file)(int, const void *, size_t);
    int (*sync_file)(int);
    int (*close_file)(int);
    int (*unlink_file)(const char *);
    int *(*error_number)(void);
};
struct r5_posix_stage {
    struct r5_posix_api api;
    int last_errno;
};

int r5_posix_stage_init(struct r5_posix_stage *, const struct r5_posix_api *);
int r5_posix_create_exclusive(void *, const char *, uintptr_t *);
int r5_posix_write_file(void *, uintptr_t, const uint8_t *, size_t, size_t *);
int r5_posix_sync_file(void *, uintptr_t);
int r5_posix_close_file(void *, uintptr_t);
int r5_posix_unlink_file(void *, const char *);
#endif
