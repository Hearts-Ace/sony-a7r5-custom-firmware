#ifndef R5_POSIX_PERSIST_H
#define R5_POSIX_PERSIST_H
#include "sd_native_persist.h"

/* Binder-supplied AP libc ABI; no firmware address is installed here. */
struct r5_posix_persist_api {
    int (*open_file)(const char *, int, unsigned);
    intptr_t (*read_file)(int, void *, size_t);
    int (*close_file)(int);
    int (*rename_file)(const char *, const char *);
    int (*sync_file)(int);
    int *(*error_number)(void);
};
struct r5_posix_persist {
    struct r5_posix_persist_api api;
    int last_errno;
};
int r5_posix_persist_init(struct r5_posix_persist *, const struct r5_posix_persist_api *);
int r5_posix_persist_open(void *, const char *, uintptr_t *);
int r5_posix_persist_read(void *, uintptr_t, uint8_t *, size_t, size_t *);
int r5_posix_persist_close(void *, uintptr_t);
int r5_posix_persist_directory(void *, const char *, uintptr_t *);
int r5_posix_persist_rename(void *, const char *, const char *);
int r5_posix_persist_sync(void *, uintptr_t);
#endif
