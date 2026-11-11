#ifndef R5_BOOT_RUNTIME_H
#define R5_BOOT_RUNTIME_H
#include "r5_boot_coordinator.h"
#include "r5_direct_pthread.h"
#include "r5_lut_directory.h"
/* One object in fresh loader-zeroed process storage. It is never reset on
 * media changes, suspend, an uncertain publish, or a WBI resume. Native hooks
 * publish integers only; the detached worker owns directory and coordinator.
 * The exact cold/WBI loader lifecycle remains a release prerequisite. */
struct r5_boot_runtime_api {
    struct r5_direct_api thread;
    struct r5_fsys_api fsys;
    struct r5_lut_directory_api directory;
    struct r5_transfer_io transfer;
    int (*clock_ms)(uint64_t *);
    int (*sleep_ms)(unsigned);
    int (*publish_inbound)(struct r5_boot_transfer_adapter *);
    uint32_t *menu_mask;
    /* Native sequence API constructs a locked snapshot and enqueues it to
     * the original owner. A returned call proves a request, not rendering. */
    void (*request_current)(void);
};
enum { R5_RUNTIME_FRESH, R5_RUNTIME_PREPARING, R5_RUNTIME_READY,
       R5_RUNTIME_FAILED };
struct r5_boot_runtime {
    struct r5_boot_coordinator coordinator;
    struct r5_direct_pthread worker;
    struct r5_lut_directory directory;
    struct r5_boot_runtime_api api;
    uint32_t prepare, result, activation, resend_pending, resend_requested;
    int release_status;
    uint8_t directory_scratch[65537];
};
/* startup single winner; callbacks/objects are boot-lifetime owned. No retries
 * on partial preparation, existing context, failed create or failed services. */
int r5_boot_runtime_prepare(struct r5_boot_runtime *,const struct r5_boot_runtime_api *);
int r5_boot_runtime_launch(struct r5_boot_runtime *);
int r5_boot_runtime_run(void *);
/* Worker-only read-only acquisition retries: at most 15s/1501 attempts.
 * Never retries a store transaction or changes the original mount service. */
int r5_boot_directory_wait(struct r5_boot_runtime *,struct r5_lut_directory *,uint32_t);
int r5_boot_runtime_initial(struct r5_boot_runtime *,uint32_t,uint32_t);
int r5_boot_runtime_completed(struct r5_boot_runtime *,uint32_t);
int r5_boot_runtime_media(struct r5_boot_runtime *,uint32_t,uint32_t,uint32_t);
/* Compatibility claim for an established original color-owner context. The
 * worker now invokes request_current() through the original locked enqueue API
 * and clears this flag after requesting; claiming it is not render completion. */
int r5_boot_runtime_take_resend(struct r5_boot_runtime *);
#endif
