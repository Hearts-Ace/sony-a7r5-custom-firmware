#ifndef R5SS_BRIDGE_NATIVE_H
#define R5SS_BRIDGE_NATIVE_H
#include <stdint.h>
#include <stddef.h>
/* Separate private protocol on the existing AP/CP receive hooks. */
int r5ss_snapshot_inbound(const uint8_t *,uint32_t);
int r5ss_native_first_owner17(uint32_t *token);
int r5ss_native_owner_check17(uint64_t,uint32_t);
/* Warm recovery: accept absent kind17 or the exact old descriptor only after
 * complete stable idle, native AP pending0 and any active completion proof. */
int r5ss_native_resume_check17(uint64_t,uint32_t,uint32_t *);
int r5ss_native_start_arm17(void);
int r5ss_native_retirement_poll(uint32_t);
int r5ss_bridge_active(void);
int r5ss_bridge_stop_ready(void);
/* Mark each power event. No IO or resource ownership changes here. */
void r5ss_bridge_power(void);
int r5ss_bridge_bind_epoch(uint32_t);
/* Worker may copy these values after any native call; no filesystem IO here.
 * Values use atomic loads. Counters include all attempted private queries. */
#define R5SS_BRIDGE_DIAG_WORDS 21u
enum { R5SS_Q_OK=0,R5SS_Q_EPOCH=1,R5SS_Q_SYMBOLS=2,R5SS_Q_CLOCK=3,
 R5SS_Q_MAILBOX=4,R5SS_Q_SERIAL=5,R5SS_Q_SEND=6,R5SS_Q_TIMEOUT=7,
 R5SS_Q_CLOCK_CHANGED=8,R5SS_Q_SLEEP=9,R5SS_Q_FIELDS=10,
 R5SS_Q_REGISTRY=11,R5SS_Q_BUSY=12,R5SS_Q_ACTIVE=13 };
/* schema,reason,op,send_rc,queries,replies,malformed,stale,wrong_source,
 * timeouts,exists17,initial_safe,busy_mask,pending_before,pending_after,
 * elapsed_ms,field_count,registry_rejects,phase,serial,tag */
void r5ss_bridge_diagnostics(uint32_t out[R5SS_BRIDGE_DIAG_WORDS]);
#endif
