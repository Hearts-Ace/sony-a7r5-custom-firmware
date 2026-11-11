#ifndef R5_BOOT_TRANSFER_ADAPTER_H
#define R5_BOOT_TRANSFER_ADAPTER_H
#include "r5_boot_transaction.h"
#include "r5_look_transfer.h"

/* Offline worker<->inbound bridge, no native addresses. One worker owns ap,
 * packet, timestamps and transaction calls. One native inbound task only
 * publishes to inbox. Neither task accesses the other's mutable AP state.
 * Fresh zero-init once per cold boot. Never reset an in-flight transaction. */
struct r5_boot_transfer_adapter {
    struct r5_transfer_ap ap;
    struct r5_transfer_io io;
    uint64_t now_ms;
    uint32_t timeout_ms, clock_valid, started, failed;
    uint32_t inbox_state; /* atomic:0 empty,1 writing,2 full,3 reading,4 fault */
    uint8_t inbox[R5_TRANSFER_ACK];
    uint8_t packet[R5_TRANSFER_MAX];
};
/* Worker sets monotonic time before finish/each transaction poll. */
int r5_boot_transfer_time(struct r5_boot_transfer_adapter *, uint64_t now_ms);
/* Native inbound adapter must pass actual osal_msg_size and source queue.
 * 0 means not ours (original dispatch), 1 consumed. Recognized malformed
 * ACKs or duplicate/overflow inbox fail closed. No allocation/wait/retry.
 * Queue 0x90030001 is pinned to original CP task evidence, not SD data. */
int r5_boot_transfer_offer_ack(struct r5_boot_transfer_adapter *, uint32_t source,
                              const uint8_t *, size_t);
/* Direct r5_tx_ops submit/poll-compatible callbacks. timeout1..60000 and
 * bounded native io.send must already be configured; no clock API guessed. */
int r5_boot_transfer_submit(void *,uint32_t,const struct r5_look_set *,uint32_t);
int r5_boot_transfer_poll(void *,struct r5_cp_ack *);
#endif
