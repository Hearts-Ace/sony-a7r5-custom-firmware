#ifndef R5_SHUTTER_SOUND_NATIVE_H
#define R5_SHUTTER_SOUND_NATIVE_H
#include <stdint.h>
#include <stddef.h>
enum {R5SS_OK=0,R5SS_BUSY=1,R5SS_INVALID=-1,R5SS_STORAGE=-2,R5SS_NATIVE=-3};
/* Backend reports native retirement; it must not infer it from elapsed time.
 * poll: 0 fully idle/retired, 1 accepted/queued/active/stopping, negative unknown/failure.
 * stop: 0 submitted once, positive unsubmitted busy (safe to retry), negative
 * failure. start: 0 accepted, 1 unaccepted
 * busy (safe to retry), negative failure. install: 0 verified, 1 in progress,
 * negative failure. No callback may call back into this scheduler. */
typedef struct {
 void *ctx;int (*poll)(void *);int (*stop)(void *);
 int (*authorize)(void *); /* re-read native mute/shutter permission immediately before Start */
 int (*install)(void *,uint32_t);int (*start)(void *,uint32_t,uint32_t);
} r5ss_ops;
typedef struct {uint32_t seq,member,ordinal;} r5ss_exposure;
typedef struct {
 uint32_t gate,serial,consumed,used,next; r5ss_exposure seen[64];
 uint32_t wanted_generation,installed_generation,audible,fault,stop_sent;
 uint32_t accepted,duplicates,coalesced,starts,stops,failures,contended;
} r5ss_scheduler;
void r5ss_init(r5ss_scheduler *);
/* Event-only: bounded work, no IO/allocation/playback. One pending serial,
 * overwritten by newer exposures. Duplicate original messages are suppressed.
 * Caller first verifies the R5 exposure ABI; a shutter press is not exposure. */
int r5ss_expose(r5ss_scheduler *,r5ss_exposure);
/* Worker-only. enable derives from native shutter permission AND total mute.
 * Updating generation invalidates old triggers; installation waits for idle. */
int r5ss_configure(r5ss_scheduler *,uint32_t generation,uint32_t audible);
int r5ss_tick(r5ss_scheduler *,const r5ss_ops *);
/* Only after an independently verified new CP session. Does not release or
 * reuse a numeric resource handle; backend must acquire fresh ownership. */
int r5ss_session(r5ss_scheduler *);
#endif
