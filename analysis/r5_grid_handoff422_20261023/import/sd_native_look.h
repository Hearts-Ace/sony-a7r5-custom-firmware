#ifndef R5_SD_NATIVE_LOOK_H
#define R5_SD_NATIVE_LOOK_H
#include <stddef.h>
#include <stdint.h>

/* Development ABI, not an installed camera interface. No firmware addresses,
 * arbitrary writes, extra correction matrix or grid are accepted from SD. */
#define R5_LOOK_SLOTS 12u
#define R5_LOOK_HEADER 128u
#define R5_LOOK_RECORD 2400u
#define R5_LOOK_MAX (R5_LOOK_HEADER + R5_LOOK_SLOTS * R5_LOOK_RECORD)
#define R5_LOOK_SD_FILE "R5NATIVE.BIN"

enum r5_result {
    R5_IMPORTED = 0, R5_ABSENT = 1, R5_INVALID = 2,
    R5_IO_ERROR = 3, R5_BUSY = 4, R5_COMMIT_ERROR = 5, R5_UNCHANGED = 6
};

struct r5_native_look {
    char name[32];
    int16_t cc1[3][8];       /* R5: B, A1-B, A2-B; NOT RAW ordering */
    int16_t block13[3][16][6]; /* B/A1/A2, native slot-major ordering */
    uint32_t gamma[129];    /* Native ordinates only; no pointers/tail fields */
    uint32_t grid_enabled;
    int8_t grid[3][405]; /* plane-major, signed 7-bit [-64,63] */
    uint8_t grid_padding;
};

struct r5_look_set {
    uint32_t valid_mask;
    struct r5_native_look look[R5_LOOK_SLOTS];
};

/* Caller owns locking, allocation and buffers. No filesystem/RTOS ABI guessed.
 * read_file must supply bounded reads and return 0 at EOF through actual.
 * open_file: 0=opened, 1=confirmed absence, anything else=I/O error.
 * commit MUST either persist the entire set and enqueue native reload for BOTH
 * preview and JPEG, or return failure without changing visible/persistent state.
 * The production adapter and its atomicity/lifetime need separate validation.
 * Caller serializes import and keeps committed data alive for both consumers.
 * None of these callbacks is currently bound to camera firmware. */
struct r5_look_ops {
    void *context;
    int (*open_file)(void *, const char *, uintptr_t *);
    int (*read_file)(void *, uintptr_t, uint8_t *, size_t, size_t *);
    int (*close_file)(void *, uintptr_t);
    int (*commit)(void *, const struct r5_look_set *);
};

int r5_decode_look_file(const uint8_t *, size_t, struct r5_look_set *);
/* Serialize the entire merged set for persistence/transport. Returns byte
 * count, or zero without touching output for invalid set/capacity/overlap.
 * Output must not overlap the source set; no native tail/pointer is saved. */
size_t r5_encode_look_file(const struct r5_look_set *, uint8_t *, size_t);
int r5_import_look_file(const struct r5_look_ops *, const char *,
    const struct r5_look_set *current, struct r5_look_set *staging,
    uint8_t *scratch, size_t capacity);
/* Consumers must hold a snapshot through render completion. Returns NULL for
 * an unpopulated slot so the adapter can preserve the original native path. */
const struct r5_native_look *r5_select_look(const struct r5_look_set *, unsigned);
/* Apply to adapter-owned copies of native records; preserve every ancillary
 * byte (including Gamma RAM references). Never pass shared live buffers. */
void r5_materialize_look(const struct r5_native_look *, uint8_t cc1[64],
    uint8_t block13[768], uint8_t gamma[576]);
#endif
