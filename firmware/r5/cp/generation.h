#ifndef R5_GENERATION_H
#define R5_GENERATION_H
#include <stdint.h>

/* Three metadata cells, no allocation for an empty cell. A native owner is
 * one aligned atomic ticket and holds one reference until its replacement.
 * Tickets include a serial; a reused cell is never an old generation. */
enum { R5G_CELLS = 3, R5G_TRIES = 8, R5G_SERIAL_MAX = 0x7fffff };
enum { R5G_OK, R5G_BUSY, R5G_EXHAUSTED };
struct r5g_cell { uint32_t state, ticket; void *data; };
struct r5g_pool { struct r5g_cell cells[R5G_CELLS]; uint32_t serial; };
struct r5g_lease { uint32_t ticket; const void *data; };

/* Single serialized control writer. It prepares payload without publishing
 * it, then publishes or aborts once. Zero-initialize the pool before use. */
int r5g_begin(struct r5g_pool *, uint32_t *ticket);
struct r5g_lease r5g_publish(struct r5g_pool *, uint32_t ticket, void *data);
void r5g_abort(struct r5g_pool *, uint32_t ticket);
/* Allocation/free and expensive preparation are control work. Last release
 * marks the cell retired; only this writer may reclaim its payload. */
unsigned r5g_collect(struct r5g_pool *, void (*dispose)(void *));

struct r5g_lease r5g_pin(struct r5g_pool *, uint32_t ticket);
void r5g_drop(struct r5g_pool *, struct r5g_lease *);
/* Transfer an owned reference. A zero lease selects stock. The caller must
 * serialize updates with the native object's normal write/copy/retire rules. */
void r5g_owner_replace(struct r5g_pool *, uint32_t *owner, struct r5g_lease *);
/* BUSY means no consistent snapshot; it is not a stock selection. */
int r5g_owner_read(struct r5g_pool *, const uint32_t *owner, struct r5g_lease *);
#endif
