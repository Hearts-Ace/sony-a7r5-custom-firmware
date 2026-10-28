#ifndef R5_LIFECYCLE_H
#define R5_LIFECYCLE_H
#include "r5_boot_transfer_adapter.h"
#define R5_LC_CLOSED 0x80000000u
#define R5_LC_EPOCH_MAX 0x1ffffffu
/* Stable gateway. One cold importer and one persistent resume owner; callbacks
 * only revoke/admit integer state. The CP bank is NEVER reset here. */
struct r5_lifecycle {
    uint64_t channel; /* high32 epoch, low32 CLOSED|admitted readers */
    struct r5_boot_transfer_adapter *inbound;
    uint32_t token, wake, handled, busy;
    uint32_t *menu;
    struct r5_boot_transfer_adapter resume;
    struct r5_look_set set;
};
struct r5_lifecycle_api {
    void *context;
    int (*cold_done)(void *);
    int (*load_active_readonly)(void *,struct r5_look_set *);
    int (*clock_ms)(uint64_t *);
    int (*sleep_ms)(unsigned);
    void (*request_current)(void);
    struct r5_transfer_io io;
};
uint32_t r5_lifecycle_event(struct r5_lifecycle *,uint32_t *,uint32_t);
int r5_lifecycle_bind(struct r5_lifecycle *,struct r5_boot_transfer_adapter *,uint32_t,uint32_t);
int r5_lifecycle_offer(struct r5_lifecycle *,uint32_t,const uint8_t *,size_t);
int r5_lifecycle_resume_once(struct r5_lifecycle *,const struct r5_lifecycle_api *);
#endif
