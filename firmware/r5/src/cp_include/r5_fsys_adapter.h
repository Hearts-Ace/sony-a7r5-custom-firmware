#ifndef R5_FSYS_ADAPTER_H
#define R5_FSYS_ADAPTER_H
#include "sd_native_look.h"

/* Source-bound AP wrappers: 0x3691104 / 0x3691138 / 0x3691124 in
 * SHA256 8ee4d5876b7e127df39f8f820b9d21834c300ff895e02ca522636ed4733efc4b.
 * No detour or absolute-address binding is installed by this adapter. */
struct r5_fsys_api {
    int (*open)(const char *, uint32_t, uint64_t *);
    int (*read)(uint64_t, void *, uint64_t, uint64_t *);
    int (*close)(uint64_t);
};

struct r5_fsys_reader {
    struct r5_fsys_api api;
    uint64_t handle;
    size_t remaining;
    unsigned calls_remaining;
    int last_native_status;
    unsigned opened;
    char path[16];
};

/* Must run in a separately scheduled filesystem-capable task. Caller provides
 * an already synchronized media snapshot drive byte from mediaInfo[slot*0x70
 * +0x19], only after its own mounted/ready and capture-idle checks. This code
 * does not acquire the model guard, poll, spawn a worker, or perform camera I/O
 * during initialization. Neither mount lifetime nor wall-time timeout of the
 * underlying synchronous Sony services is established. */
int r5_fsys_reader_init(struct r5_fsys_reader *, const struct r5_fsys_api *, char);

/* r5_look_ops-compatible callbacks. Errors preserve existing configuration.
 * Native wrapper errors are deliberately NEVER relabeled confirmed absence.
 * Reads have independent byte and call budgets; no native retry loop. */
int r5_fsys_open_file(void *, const char *, uintptr_t *);
int r5_fsys_read_file(void *, uintptr_t, uint8_t *, size_t, size_t *);
int r5_fsys_close_file(void *, uintptr_t);
#endif
