#include "generation.h"

#define FREE 0u
#define WRITING 1u
#define RETIRED 0x80000000u
#define FIRST_REF (RETIRED | 1u)
#define LOAD(p) __atomic_load_n((p), __ATOMIC_ACQUIRE)
#define STORE(p,v) __atomic_store_n((p), (v), __ATOMIC_RELEASE)
static struct r5g_cell *cell(struct r5g_pool *p, uint32_t ticket)
{
    return &p->cells[(ticket & 3u) - 1u];
}

int r5g_begin(struct r5g_pool *p, uint32_t *ticket)
{
    *ticket = 0;
    if (p->serial >= R5G_SERIAL_MAX)
        return R5G_EXHAUSTED;
    for (unsigned i = 0; i < R5G_CELLS; ++i) {
        struct r5g_cell *c = &p->cells[i];
        if (LOAD(&c->state) != FREE)
            continue;
        STORE(&c->state, WRITING);
        *ticket = (++p->serial << 2) | (i + 1u);
        c->ticket = *ticket;
        return R5G_OK;
    }
    return R5G_BUSY;
}

struct r5g_lease r5g_publish(struct r5g_pool *p, uint32_t ticket, void *data)
{
    struct r5g_cell *c = cell(p, ticket);
    c->data = data;
    STORE(&c->state, FIRST_REF);
    return (struct r5g_lease){ticket, data};
}

void r5g_abort(struct r5g_pool *p, uint32_t ticket)
{
    STORE(&cell(p, ticket)->state, FREE);
}

unsigned r5g_collect(struct r5g_pool *p, void (*dispose)(void *))
{
    unsigned count = 0;
    for (unsigned i = 0; i < R5G_CELLS; ++i) {
        struct r5g_cell *c = &p->cells[i];
        if (LOAD(&c->state) != RETIRED)
            continue;
        dispose(c->data);
        c->data = 0;
        STORE(&c->state, FREE);
        ++count;
    }
    return count;
}

static void drop_cell(struct r5g_cell *c)
{
    /* The last reference leaves a distinct retired state, not FREE and
     * not eligible for a new pin. The control actor can now reclaim it. */
    (void)__atomic_fetch_sub(&c->state, 1u, __ATOMIC_ACQ_REL);
}

struct r5g_lease r5g_pin(struct r5g_pool *p, uint32_t ticket)
{
    if ((ticket & 3u) != 0 && (ticket >> 2) != 0) {
        struct r5g_cell *c = cell(p, ticket);
        uint32_t state = LOAD(&c->state);
        for (unsigned i = 0; i < R5G_TRIES; ++i) {
            if (state < FIRST_REF || state == UINT32_MAX)
                break;
            if (!__atomic_compare_exchange_n(&c->state, &state, state + 1u, 0,
                                              __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE))
                continue;
            /* Check identity only while pinned: a stale reader may have
             * raced retirement and pinned a different payload in this cell. */
            if (ticket == c->ticket)
                return (struct r5g_lease){ticket, c->data};
            drop_cell(c);
            break;
        }
    }
    return (struct r5g_lease){0, 0};
}

void r5g_drop(struct r5g_pool *p, struct r5g_lease *lease)
{
    uint32_t ticket = lease->ticket;
    *lease = (struct r5g_lease){0, 0};
    if (ticket)
        drop_cell(cell(p, ticket));
}

void r5g_owner_replace(struct r5g_pool *p, uint32_t *owner, struct r5g_lease *lease)
{
    uint32_t old = __atomic_exchange_n(owner, lease->ticket, __ATOMIC_ACQ_REL);
    *lease = (struct r5g_lease){0, 0};
    if (old)
        drop_cell(cell(p, old));
}

int r5g_owner_read(struct r5g_pool *p, const uint32_t *owner,
                   struct r5g_lease *out)
{
    *out = (struct r5g_lease){0, 0};
    for (unsigned i = 0; i < R5G_TRIES; ++i) {
        uint32_t ticket = LOAD(owner);
        if (!ticket)
            return R5G_OK;
        struct r5g_lease lease = r5g_pin(p, ticket);
        if (lease.ticket && ticket == LOAD(owner)) {
            *out = lease;
            return R5G_OK;
        }
        r5g_drop(p, &lease);
    }
    return R5G_BUSY;
}
