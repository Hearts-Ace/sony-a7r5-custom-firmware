#ifndef R5_OWNER_SUBMIT_H
#define R5_OWNER_SUBMIT_H
#include "generation.h"
#include "wire.h"

/* This state machine must be driven by one serialized CP control actor.
 * The native consumer-facing current field is the only shared owner here. */
enum r5s_result {
    R5S_OK, R5S_BUSY, R5S_STALE, R5S_CONFLICT, R5S_FAILED,
    R5S_EXHAUSTED, R5S_DUPLICATE, R5S_STOCK
};
struct r5s_key { uint32_t epoch, sequence, slot, digest; };
struct r5s_state {
    struct r5g_pool pool;
    struct r5g_lease pending;
    struct r5s_key key;
    uint32_t current;
    uint32_t cookie, cursor;
    enum { R5S_IDLE, R5S_RETRY, R5S_REJECTED, R5S_PREPARED, R5S_ACCEPTED } phase;
};
typedef void *(*r5s_prepare_fn)(const void *);
typedef void (*r5s_dispose_fn)(void *);

/* One request, copied/validated by make. An Off request never calls make.
 * slot and digest describe the payload; the wire decoder must authenticate
 * message shape, sender, checksum and selected content before calling. */
int r5s_prepare(struct r5s_state *, struct r5s_key, const void *value,
                r5s_prepare_fn make, r5s_dispose_fn dispose, uint32_t *cookie);
int r5s_abort(struct r5s_state *, struct r5s_key, r5s_dispose_fn dispose);

/* 0x402f: original native color remains in byte +8. The reserved upper
 * three bytes carry a control-actor cookie only on a tagged job. */
/* Called at the actual native acceptance boundary, with the original
 * sender and raw message. Only OK changes the owner. A rejected tag may
 * not be substituted with the latest prepared request. */
int r5s_accept402f(struct r5s_state *, const uint8_t *, unsigned size, uint32_t source);
#endif
