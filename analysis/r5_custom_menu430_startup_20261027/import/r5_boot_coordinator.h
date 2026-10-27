#ifndef R5_BOOT_COORDINATOR_H
#define R5_BOOT_COORDINATOR_H
#include "r5_ap_terminal.h"
#include "r5_scan_gate.h"
#include "r5_fsys_adapter.h"

/* Offline boot-only composition. There are NO original addresses, hooks,
 * threads, sleeps, camera accesses or implicit startup assumptions here.
 * A separately proven filesystem-capable worker owns all non-atomic fields.
 * Native notify/mount tasks only publish integer events to their mailboxes.
 * Fresh zeroed object once per cold boot, immutable address until shutdown.
 * The original menu activation word is NOT this object's private mask. */
struct r5_boot_coordinator {
    struct r5_scan_gate scan;
    uint32_t media[2]; /* atomic packed:bit31 observed,bit30 success,low8 drive */
    uint32_t phase, private_activation, selected_slot, selected_drive;
    struct r5_boot_transaction transaction;
    struct r5_boot_transfer_adapter transfer;
    struct r5_tx_ops ops;
    struct r5_fsys_api fsys;
    struct r5_fsys_reader reader;
    uint64_t scan_start_ms, last_ms, scan_deadline_ms, total_deadline_ms;
    uint32_t clock_valid, media_closed;
};
enum r5_coordinator_phase {
    R5_COORD_NEW=0,R5_COORD_SCAN=1,R5_COORD_ACK=2,
    R5_COORD_ACTIVE=3,R5_COORD_ORIGINAL=4,R5_COORD_BLOCKED=5
};
/* persist/stage/CP io and Fsys functions must outlive this boot. No external
 * native pointer may be copied from an SD file. This method only prepares
 * owned data and reads active storage; no CP seal or menu activation. */
int r5_coordinator_start(struct r5_boot_coordinator *,const struct r5_tx_ops *,
    const struct r5_fsys_api *,const struct r5_transfer_io *,uint32_t token,uint32_t timeout_ms);
/* Native mount-result producer only: after native wrapper completes. First
 * result per slot wins; late/duplicate events cannot replace a selected card.
 * Inbound ACK producer MUST use r5_ap_terminal_offer_ack on transfer. */
int r5_coordinator_media(struct r5_boot_coordinator *,uint32_t slot,uint32_t status,uint32_t drive);
/* Publish initial/completed events through r5_scan_gate_*(&coordinator.scan).
 * That predicate proves only the still-session boundary; native binding must
 * FIRST establish correct cold generation/all-mode coverage. No implicit delay
 * finalizes a scan. Worker waits for observed mount result for every initially
 * required slot (states1/2), then chooses lowest successful such slot once.
 * Optional/unproved media states are never guessed to contain a readable card.
 * Scan budget is timeout_ms, total scan+ACK budget is 2*timeout_ms, starting
 * with the first step sample. Missing events at deadline permanently BLOCK
 * with zero mask; elapsed time never fabricates a successful scan/card.
 * Timestamp addition saturates; clock rollback permanently BLOCKS.
 * Filesystem callbacks are synchronous and need separate deadlock/stack proof.
 * now_ms is an explicit real monotonic-clock sample, not a counter of polls.
 */
int r5_coordinator_step(struct r5_boot_coordinator *,uint64_t now_ms);
#endif
