#ifndef R5_ASYNC_IMPORT_H
#define R5_ASYNC_IMPORT_H
#include <stdint.h>

/* New, zero-initialized, AP-owned memory. No native mount pointers retained.
 * Every access to atomic words uses compiler acquire/release builtins.
 * Never reset while producer/consumer can run. Not installed in firmware. */
struct r5_async_import_state {
    uint32_t drive[2];
    uint32_t active_phase;
    uint32_t import_phase;
    uint32_t selected_slot;
    uint32_t selected_drive;
    int32_t active_result;
    int32_t import_result;
};
struct r5_async_import_ops {
    void *context;
    int32_t (*load_active)(void *);
    int32_t (*import_sd)(void *, uint32_t slot, uint32_t drive);
};
/* Producer performs no allocation, I/O, OS call, retry or wait. */
int r5_async_import_observe(struct r5_async_import_state *, uint32_t slot,
                           uint32_t status, uint32_t drive);
/* Call only from a separate worker after releasing its native queue mutex.
 * Active load is attempted once even with no SD. Import is attempted once,
 * from lowest numbered currently observed ready slot; a later arriving card
 * is ignored this boot. Selection is not a both-card completion barrier.
 * load_active must prepare AP pending data only: never begin/seal CP there.
 * No-card active deployment needs a separately proven scan-finalized event.
 * Callbacks own all file validation, failure preservation and CP seal ACK.
 * Their duration is NOT bounded by this module. No AP mask is changed here. */
int r5_async_import_poll(struct r5_async_import_state *,
                         const struct r5_async_import_ops *);
#endif
