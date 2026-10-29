#ifndef R5_SCAN_GATE_H
#define R5_SCAN_GATE_H
#include <stdint.h>
/* Fresh zeroed AP-owned memory for one cold-init generation. Do not reset
 * concurrently. This is an UNBOUND candidate, not a camera boot barrier.
 * Never retain a native sequence or registry pointer in this structure. */
struct r5_scan_gate {
    uint32_t initial_phase; /* 0 absent, 1 copying, 2 published */
    uint32_t initial_status[2];
    uint32_t completed[2];
};
/* Only call when native still-record initial notification has been accepted,
 * with values copied from original w21/w22 while its own mutex remains held.
 * One weak CAS attempt only. Failure is fail-closed (no finalized decision),
 * not proof an initialization event was already accepted. */
int r5_scan_gate_initial(struct r5_scan_gate *, uint32_t, uint32_t);
/* Only call after the corresponding native slot completion flag store. */
int r5_scan_gate_completed(struct r5_scan_gate *, uint32_t);
/* Same boolean predicate as native 0x34d99b4, over owned event copies.
 * This establishes only native still-session media wait completion. Initial
 * notification coverage of all cold boots/modes remains unproven. No card
 * is assumed absent from a timeout, system mode or missing notification. */
int r5_scan_gate_ready(const struct r5_scan_gate *);
#endif
