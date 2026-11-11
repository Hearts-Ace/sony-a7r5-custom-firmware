#ifndef R5_AP_ACTIVATION_H
#define R5_AP_ACTIVATION_H
#include "r5_boot_transfer_adapter.h"
/* Offline AP helper, not installed. Sole boot worker calls this only after
 * r5_tx_poll. tx and adapter.ap are worker-owned, immutable after ACTIVE.
 * inbox_state is the inbound task's only concurrent field.
 * activation is a separate aligned, zero-initialized AP-owned word; no address
 * or mutable alias into tx, adapter or candidate storage is admitted.
 * 1=first release publication, 0=already nonzero (untouched), -1=not eligible.
 * This only checks initial activation. A fault arriving after the final inbox
 * acquire check needs a separate revocation/monitoring policy; none is supplied.
 * Menus acquire-load this word. No preview/JPEG safety is implied here. */
int r5_ap_activate_once(uint32_t *activation,
    const struct r5_boot_transaction *, const struct r5_boot_transfer_adapter *);
#endif
