#ifndef R5_BOOT_MEDIA_BRIDGE_H
#define R5_BOOT_MEDIA_BRIDGE_H
#include <stdint.h>

/* Analysis-stage handoff only; no native addresses or hooks are installed.
 * Caller must serialize all methods in its established startup task/lock.
 * init is once per AP process; take closes the collection window permanently.
 * Actual join of mount tasks and capture enable is not yet bound. */
struct r5_boot_media_bridge {
    uint32_t collecting;
    uint32_t ready_mask;
    uint8_t drive[2];
};
struct r5_boot_media_snapshot {
    uint32_t ready_mask;
    uint8_t drive[2];
};

void r5_boot_media_init(struct r5_boot_media_bridge *);

/* Exact source: 4.04 appFw.so SHA2568ee4d5876b7e127df39f8f820b9d21834
 * c300ff895e02ca522636ed4733efc4b, mount continuation0x33c3cd4:
 * slot=x28 object+0x1c; result u32=frame+0x13d0; drive=frame+0x13d4.
 * Must receive the new service result, not the constructor mediaInfo snapshot.
 * Any later failure for that slot invalidates a formerly collected result. */
int r5_boot_media_observe(struct r5_boot_media_bridge *, uint32_t slot,
                          uint32_t native_status, uint32_t drive);

/* Nonblocking handoff: no allocation, waits, filesystem or CP operation.
 * Call only after native startup mount tasks have joined and before capture
 * can use imported data. No producer may concurrently enter this function.
 * On success, subsequent takes/observations are refused; even no SD freezes.
 * Result drives are ordered by physical slot index, never mount timing. */
int r5_boot_media_take(struct r5_boot_media_bridge *,
                        struct r5_boot_media_snapshot *);
#endif
