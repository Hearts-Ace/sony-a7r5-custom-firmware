#ifndef R5_SHUTTER_NATIVE_BACKEND_H
#define R5_SHUTTER_NATIVE_BACKEND_H
#include "r5_shutter.h"
#include "native_loader_contract.h"
#define R5SS_NATIVE_KIND 17u
#define R5SS_NATIVE_CAPACITY 51200u
#define R5SS_NATIVE_GUARD 64u
#define R5SS_NATIVE_MAX_ENCODED 49568u

typedef struct {
 uint32_t session_witness,offered_generation,installed_generation;
 uint32_t encoded_bytes,padded_bytes,registered,cp_owned,ap_owned,mapped,fault;
 uint32_t starts,stops,imports,last_native,abandoned,volume_step;
 uint32_t installed_bytes;
 const uint8_t *encoded;
 r5ss_dmm_extent ap,cp;
 r5ss_mem_map_reply map;
} r5ss_native_backend;

/* First zero-initialize b. This never calls native APIs. A nonzero witness must
 * independently establish that CP has started a fresh session and its old
 * audio registry/leases are gone. An AP epoch/reset alone is insufficient.
 * On a changed witness old numeric handles are forgotten, never released. */
int r5ss_backend_session(r5ss_native_backend *b,uint32_t cp_session_witness);
/* First use only: root has a fresh exact CP snapshot proving kind17 absent,
 * no kind17 pending, actor/MMIO idle. A later successful native CLAIM creates
 * real ownership. This does not assert that the whole CP just rebooted. */
int r5ss_backend_first_authorize(r5ss_native_backend *b,uint32_t authorization_token);
/* Worker-only. Pins root-owned encoded staging through install completion;
 * no second staging copy lives in the backend. bytes+64 must be readable,
 * with every guard byte zero. Expected f0 payload is already converted and
 * scaled with the independent volume step. Caller configures scheduler audible0 and
 * waits for verified retirement before offering a replacement generation. */
int r5ss_backend_stage(r5ss_native_backend *b,uint32_t generation,
                       const uint8_t *encoded,uint32_t bytes,uint32_t padded,
                       uint32_t volume_step);
/* Worker-only callbacks. ops.ctx must be b; use with the shared scheduler.
 * No call is legal from inbound/GUI callbacks. Native RPCs can wait. */
int r5ss_backend_poll(void *);
/* Worker-only: after mute/disable, wait for authenticated retirement, remove
 * our exact registry then release only our acknowledged CP/AP leases.
 * BUSY means retry later; unknown/failure pins resources and sets fault. */
int r5ss_backend_unload(r5ss_native_backend *);
int r5ss_backend_stop(void *);
int r5ss_backend_authorize(void *);
int r5ss_backend_install(void *,uint32_t generation);
int r5ss_backend_start(void *,uint32_t generation,uint32_t serial);
r5ss_ops r5ss_backend_ops(r5ss_native_backend *);
#endif
