#ifndef R5_BOOT_TRANSACTION_H
#define R5_BOOT_TRANSACTION_H
#include "sd_native_persist.h"

/* Offline startup coordinator. SINGLE owner; never reset within a boot.
 * Not a firmware binding and not r5_look_ops.commit: file publication and CP
 * application are deliberately separate, observable operations. */
enum r5_tx_phase {
    R5_TX_NEW=0, R5_TX_COLLECTING=1, R5_TX_WAIT_CP=2,
    R5_TX_ACTIVE=3, R5_TX_ORIGINAL=4, R5_TX_BLOCKED=5, R5_TX_BUSY=6
};
struct r5_cp_ack { uint32_t token, mask, payload_crc; };
struct r5_tx_ops {
    struct r5_persist_ops persist;
    struct r5_stage_ops stage;
    void *cp_context;
    /* Must be bounded/nonblocking. Submit only ONCE, never retry a bank.
     * Return 0 for accepted, nonzero for failure; accepted is NOT an ACK.
     * Set storage remains immutable until next cold initialization. */
    int (*submit)(void *, uint32_t token, const struct r5_look_set *, uint32_t crc);
    /* 0=pending, 1=CP SEALED acknowledgment, other=transport error.
     * ACK requires CP independently checking complete bank contents/digest.
     * A local send completion cannot satisfy this callback contract. */
    int (*poll)(void *, struct r5_cp_ack *);
};
struct r5_boot_transaction {
    uint32_t phase, token, expected_crc, activation_mask;
    uint64_t submitted_ms, last_ms;
    uint32_t timeout_ms;
    int32_t active_result, sd_result, stage_result, publish_result;
    struct r5_look_set active, candidate;
    uint8_t scratch[R5_LOOK_MAX+1];
};
/* CRC32 IEEE over mask LE32, then each present slot number LE32 (1..6),
 * CC1 48/B13 576/Gamma 516 little-endian bytes. Names excluded. This is
 * transport integrity, not authentication. Caller first validates the set. */
uint32_t r5_boot_payload_crc(const struct r5_look_set *);
/* Caller supplies zero-initialized, disjoint state/ops. token!=0;
 * timeout 1..60000 ms; now_ms comes from a monotonic clock. No clock binding
 * or wall-clock bound for synchronous file callbacks is implied. */
int r5_tx_load(struct r5_boot_transaction *, const struct r5_tx_ops *,
               uint32_t token, uint32_t timeout_ms);
/* Invalid/unreadable active storage blocks this boot, preserving that file
 * and all unknown omitted slots. Confirmed absence starts an empty set. */
/* Exactly one chosen, ready SD volume, before finish. File callbacks only;
 * commit is unused and may be NULL. Missing/bad/failed SD preserves active.
 * read/open/close must be synchronous bounded services on an allowed worker.
 * Directory initialization is a separate, not-yet-bound prerequisite. */
int r5_tx_collect_sd(struct r5_boot_transaction *, const struct r5_look_ops *,
                     const char *path);
/* Caller explicitly closes the boot scan window (even for no card). Do NOT
 * infer completion from the first idle poll, a guessed delay, or system_mode.
 * Publishes changed candidate before submitting CP once; uncertain rename/
 * dirsync disables activation this boot and requires separate recovery.
 * If CP fails after durable publication, the new file remains for next boot,
 * mask remains zero; no false atomic rollback or success is reported. */
int r5_tx_finish(struct r5_boot_transaction *, const struct r5_tx_ops *, uint64_t now_ms);
/* Nonblocking ACK polling with explicit monotonic deadline; >=deadline,
 * backward time, malformed ACK, or error permanently fails this boot.
 * Only ACTIVE sets activation_mask; an AP writer needs its own release store.
 * This module itself does not change AP menus or render consumers. */
int r5_tx_poll(struct r5_boot_transaction *, const struct r5_tx_ops *, uint64_t now_ms);
#endif
