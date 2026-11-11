#ifndef R5_AP_TERMINAL_H
#define R5_AP_TERMINAL_H
#include "r5_ap_activation.h"

/* Successor to the first-publication experiment. BOTH entry points must be
 * used together, with the same fresh, immutable-lifetime adapter. State 5 is
 * terminal: no more ACKs are needed after independently verified CP SEAL.
 * Native inbox tasks must not call the older offer function on this object.
 * This closes one ACK/publication race; it neither installs a native hook nor
 * resends the current look, nor proves any render/capture lifetime. */
#define R5_AP_INBOX_CLOSED 5u
int r5_ap_terminal_offer_ack(struct r5_boot_transfer_adapter *,uint32_t,
    const uint8_t *,size_t);
/* Worker only. Validates the completed transaction, then CAS closes the empty
 * inbox BEFORE release-publishing mask. A queued/writing/faulted inbox refuses
 * activation. Recognized late ACKs are consumed without changing closed state.
 * No hot reset/retry/reopen. A failed word CAS leaves the inbox closed. */
int r5_ap_terminal_activate_once(uint32_t *,const struct r5_boot_transaction *,
    struct r5_boot_transfer_adapter *);
#endif
