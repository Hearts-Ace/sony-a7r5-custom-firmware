#ifndef R5_DEDICATED_WORKER_H
#define R5_DEDICATED_WORKER_H
#include <stdint.h>
#include <stddef.h>

/* Exact observed libosal_utm descriptor; no native addresses are bound here.
 * This OSAL API DOES NOT set stack size. Worker probes its actual pthread
 * stack and refuses import unless >=256KiB. The probe itself must be audited
 * and bound separately; unknown default stack must never be asserted large.
 * Owned object/name/desc/ops/argument live until process shutdown. */
#define R5_WORKER_MIN_STACK_BYTES (256u*1024u)
struct r5_osal_thread_desc {
    const char *name;
    uint32_t policy, reserved;
    void *(*entry)(void *);
    void *argument;
    uint16_t tag, reserved_tag;
    uint32_t priority;
};
struct r5_worker_api {
    /* Original OSAL success is positive Linux TID. Most errors are negative,
     * but attr_init positive errors pass through; child phase is authoritative. */
    int (*create_detached)(const struct r5_osal_thread_desc *);
    int (*current_stack_bytes)(uint64_t *);
    int (*run)(void *);
};
struct r5_worker_stack_api {
    uintptr_t (*self)(void);
    int (*getattr)(uintptr_t,void *);
    int (*getstacksize)(const void *,size_t *);
    int (*destroy)(void *);
};
/* Source R5 libpthread uses 64-byte attr objects. Query current child, then
 * destroy even when getstacksize fails. Output untouched on any error. */
int r5_worker_probe_stack(const struct r5_worker_stack_api *,uint64_t *);
enum r5_worker_launch {R5_WORKER_NEW=0,R5_WORKER_CREATING=1,
    R5_WORKER_POSITIVE_RESULT=2,R5_WORKER_CREATE_FAILED=3};
enum r5_worker_phase {R5_WORKER_WAITING=0,R5_WORKER_PROBING=1,
    R5_WORKER_RUNNING=2,R5_WORKER_DONE=3,R5_WORKER_FAILED=4,
    R5_WORKER_STACK_REFUSED=5};
struct r5_dedicated_worker {
    uint32_t prepared, launch, phase;
    int32_t create_status, run_status;
    uint64_t observed_stack_bytes;
    struct r5_osal_thread_desc descriptor;
    struct r5_worker_api api;
    void *run_argument;
    char name[16];
};
/* Single-owner initialization of a fresh zeroed owned object, before startup
 * hook may call launch. No threads/services/I/O. No native AP task id used. */
int r5_worker_prepare(struct r5_dedicated_worker *,const struct r5_worker_api *,void *);
/* Once-only. Runs create_detached and can block in native startup handshake.
 * MUST be called outside mount/property/model notification locks. No import
 * I/O in creator: run is called by child only, after native OSAL unlocks its
 * startup mutex and actual stack probe passes. Failure never retries/reset. */
/* Returns0 for positive native creation result; this does NOT prove child
 * started. phase is child-owned evidence. create_status retains TID/error.
 * A zero create result is refused as ambiguous/non-native. Once is per owned
 * object/process lifetime, not proven per mechanical power switch or WBI. */
int r5_worker_launch_once(struct r5_dedicated_worker *);
void *r5_worker_entry(void *);
#endif
