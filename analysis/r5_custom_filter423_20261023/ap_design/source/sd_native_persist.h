#ifndef R5_SD_NATIVE_PERSIST_H
#define R5_SD_NATIVE_PERSIST_H
#include "sd_native_store.h"

#define R5_LOOK_DIRECTORY "/usr/data/lut"

enum r5_publish_result {
    R5_PUBLISHED=0, R5_PUBLISH_INVALID=1, R5_PUBLISH_IO_ERROR=2,
    R5_PUBLISH_MISMATCH=3, R5_PUBLISH_UNCERTAIN=4,
    R5_PUBLISHED_CLOSE_ERROR=5
};

/* Independent internal-file layer, NOT r5_look_ops.commit. The caller must own
 * the staged file and serialize all imports/recovery for the entire call;
 * the trusted parent directory must not be replaced concurrently. NEW must
 * have been file-fsynced by r5_stage_look_store. It is reread and compared with
 * the expected complete set before rename. No stale NEW is auto-promoted.
 *
 * open_read: 0=open, 1=confirmed absent, other=I/O error. open_directory returns
 * a directory descriptor. A rename error is conservatively UNCERTAIN: no
 * rollback or blind retry, inspect the active file first. After rename succeeds
 * a directory-fsync error is also UNCERTAIN; the new file is already visible.
 * PUBLISHED_CLOSE_ERROR means directory fsync succeeded but close failed.
 * No callback is retried, and no file is removed by this layer.
 *
 * Call-count/byte bounds do not establish a wall-clock timeout of blocking
 * native filesystem services. These callbacks are not bound to firmware. */
struct r5_persist_ops {
    void *context;
    int (*open_read)(void *, const char *, uintptr_t *);
    int (*read_file)(void *, uintptr_t, uint8_t *, size_t, size_t *);
    int (*close_file)(void *, uintptr_t);
    int (*open_directory)(void *, const char *, uintptr_t *);
    int (*rename_file)(void *, const char *, const char *);
    int (*sync_directory)(void *, uintptr_t);
};

int r5_publish_staged_look(const struct r5_persist_ops *,
    const struct r5_look_set *, uint8_t *, size_t);

/* Read the complete active snapshot on startup/recovery. Missing/invalid/I/O
 * errors leave output untouched. Unlike SD import, omitted slots are cleared:
 * the internal active file represents the ENTIRE merged configuration.
 * NEW is never read by this function. No CP or visible camera state changes. */
int r5_load_persisted_look(const struct r5_persist_ops *,
    struct r5_look_set *, uint8_t *, size_t);
#endif
