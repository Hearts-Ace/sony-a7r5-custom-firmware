#include "control.h"
#include "grid_owners.h"

#define BUSY 0x80000000u
#define LOAD(p) __atomic_load_n((p), __ATOMIC_ACQUIRE)
#define STORE(p, v) __atomic_store_n((p), (v), __ATOMIC_RELEASE)

static int tagged(uint32_t word) { return (word & 0xf0000000u) == OD_GRID_MARKER; }

static uint32_t decode(uint32_t word)
{
    uint32_t ticket = (word & 0x0fffffffu) >> 3;
    if (!tagged(word) ||
        !ticket || !(ticket & 3u) || !(ticket >> 2) || ticket > OD_GRID_TICKET_MAX)
        return 0;
    return ticket;
}

static int claim(struct od_grid_field *e, uint32_t before, uint32_t after)
{
    return __atomic_compare_exchange_n(&e->field, &before, after | BUSY, 0,
                                        __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE);
}

static struct od_grid_field *find(uint32_t field)
{
    for (unsigned i = 0; i < OD_GRID_FIELDS; ++i) {
        struct od_grid_field *e = &OD_STATE->grid.fields[i];
        if ((LOAD(&e->field) & ~BUSY) == field)
            return e;
    }
    return 0;
}

/* A pool task already owns its exact immutable generation. A local copy may
 * verify that identity; it must never replace the entire task's owner. */
static int pool_matches(uintptr_t field, uint32_t ticket)
{
    struct r5g_lease pin;
    const struct od_context *c = od_field_pin(field, &pin);
    int ok = c && pin.ticket == ticket;
    od_work_drop(&pin);
    return ok;
}

static int replace(uint32_t *field, uint32_t value, struct r5g_lease *next)
{
    uint32_t addr = (uint32_t)(uintptr_t)field;
    if (!addr || (addr & (BUSY | 3u)))
        return 0;
    if (od_pool_field(addr)) {
        if (next->ticket && !pool_matches(addr, next->ticket))
            return 0;
        STORE(field, value);
        od_work_drop(next);
        return 1;
    }

    struct od_grid_field *e = find(addr);
    if (e) {
        if (!claim(e, addr, addr))
            return 0;
    } else if (next->ticket) {
        for (unsigned i = 0; i < OD_GRID_FIELDS; ++i) {
            struct od_grid_field *candidate = &OD_STATE->grid.fields[i];
            if (claim(candidate, 0, addr)) {
                e = candidate;
                break;
            }
        }
        if (!e)
            return 0;
    } else {
        STORE(field, value);
        return 1;
    }

    struct r5g_lease old = {LOAD(&e->ticket), 0};
    STORE(&e->ticket, next->ticket);
    STORE(field, value);
    STORE(&e->field, next->ticket ? addr : 0);
    *next = (struct r5g_lease){0, 0};
    od_work_drop(&old);
    return 1;
}

/* level=8 means ordinary stock word; level=9 means an encoded word whose
 * ownership is absent/changing. AA disables only a local descriptor for 9. */
static const struct od_context *pin(const uint32_t *field, uint32_t value,
                                    struct r5g_lease *out, unsigned *level)
{
    *out = (struct r5g_lease){0, 0};
    *level = 8;
    if (!tagged(value))
        return 0;
    *level = 9;
    uint32_t ticket = decode(value);
    if (!ticket)
        return 0;
    uint32_t addr = (uint32_t)(uintptr_t)field;
    const struct od_context *ctx;
    if (od_pool_field(addr)) {
        ctx = od_field_pin(addr, out);
        if (ctx && out->ticket == ticket && LOAD(field) == value) {
            *level = value & 7u;
            return ctx;
        }
        od_work_drop(out);
        return 0;
    }
    struct od_grid_field *e = find(addr);
    if (!e || LOAD(&e->field) != addr || LOAD(&e->ticket) != ticket)
        return 0;
    ctx = od_ticket_pin(ticket, out);
    if (ctx && LOAD(field) == value &&
        LOAD(&e->ticket) == ticket && LOAD(&e->field) == addr) {
        *level = value & 7u;
        return ctx;
    }
    od_work_drop(out);
    return 0;
}

int od_grid_state_own(uint8_t *state, struct r5g_lease *owned, unsigned level)
{
    if (!owned->ticket || owned->ticket > OD_GRID_TICKET_MAX || level > 7u)
        return 0;
    return replace((void *)(state + 0x20),
                    OD_GRID_MARKER | (owned->ticket << 3) | level, owned);
}

const struct od_context *od_grid_desc_pin(const uint8_t *desc, struct r5g_lease *out,
                                          unsigned *level)
{
    const uint32_t *field = (const void *)(desc + 0x14);
    return pin(field, LOAD(field), out, level);
}

int od_grid_field_copy(uint32_t *dst, const uint32_t *src)
{
    struct r5g_lease next;
    unsigned level;
    uint32_t value = LOAD(src);
    const struct od_context *ctx = pin(src, value, &next, &level);
    if (!ctx && level != 8u) {
        (void)replace(dst, 0, &next);
        return 0;
    }
    /* A same-field replacement keeps one ref throughout. Pin verifies the
     * encoded ticket before the destination replaces or drops anything. */
    int ok = replace(dst, ctx ? OD_GRID_MARKER | (next.ticket << 3) | level : value, &next);
    od_work_drop(&next);
    if (!ok)
        (void)replace(dst, 0, &next);
    return ok;
}

int od_grid_field_clear(uint32_t *field)
{
    struct r5g_lease none = {0, 0};
    return replace(field, 0, &none);
}

void od_grid_forget_range(uintptr_t base, uint32_t size)
{
    for (unsigned i = 0; i < OD_GRID_FIELDS; ++i) {
        struct od_grid_field *e = &OD_STATE->grid.fields[i];
        uint32_t field = LOAD(&e->field);
        if (field && !(field & BUSY) && field >= base && field - base < size)
            (void)od_grid_field_clear((uint32_t *)(uintptr_t)field);
    }
}

int od_grid_state_stock(uint8_t *state)
{
    uint32_t *field = (void *)(state + 0x20);
    if (!tagged(LOAD(field)))
        return 1;
    if (!od_grid_field_clear(field))
        return 0;
    state[0x24] = 0;
    return 1;
}
