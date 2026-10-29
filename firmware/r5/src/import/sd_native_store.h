#ifndef R5_SD_NATIVE_STORE_H
#define R5_SD_NATIVE_STORE_H
#include "sd_native_look.h"

/* Internal userspace files only. This does not write a Backup property or a
 * flash partition. Staging alone never changes the active persisted file. */
#define R5_LOOK_STORE "/usr/data/lut/R5NATIVE.BIN"
#define R5_LOOK_PENDING "/usr/data/lut/R5NATIVE.NEW"

enum r5_stage_result {
    R5_STAGE_READY=0, R5_STAGE_INVALID=1, R5_STAGE_BUSY=2,
    R5_STAGE_IO_ERROR=3, R5_STAGE_CLEANUP_ERROR=4
};

/* Production binding must use exclusive creation (Linux O_WRONLY|O_CREAT|
 * O_EXCL, mode0600), report EEXIST as2, other failures as nonzero. A stale
 * .NEW is preserved for a separate recovery decision, never truncated here.
 * Positive short writes are accumulated; zero/oversize writes are errors.
 * close is called once even on errors (never retry an ambiguous close).
 * Failure cleanup unlinks only a file successfully created by this call.
 * No rename, visible activation, CP message, or directory-fsync claim. */
struct r5_stage_ops {
    void *context;
    int (*create_exclusive)(void *, const char *, uintptr_t *);
    int (*write_file)(void *, uintptr_t, const uint8_t *, size_t, size_t *);
    int (*sync_file)(void *, uintptr_t);
    int (*close_file)(void *, uintptr_t);
    int (*unlink_file)(void *, const char *);
};

int r5_stage_look_store(const struct r5_stage_ops *, const struct r5_look_set *,
    uint8_t *scratch, size_t capacity);
#endif
