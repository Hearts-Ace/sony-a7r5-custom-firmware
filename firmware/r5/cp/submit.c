#include "submit.h"

static int same(struct r5s_key a, struct r5s_key b)
{
    return a.epoch == b.epoch && a.sequence == b.sequence &&
           a.slot == b.slot && a.digest == b.digest;
}

int r5s_prepare(struct r5s_state *s, struct r5s_key key, const void *value,
                r5s_prepare_fn make, r5s_dispose_fn dispose, uint32_t *cookie)
{
    *cookie = 0;
    if (!key.epoch || !key.sequence || key.slot > 12 || (!key.slot && key.digest))
        return R5S_CONFLICT;
    if (key.epoch < s->key.epoch ||
        (key.epoch == s->key.epoch && key.sequence < s->key.sequence))
        return R5S_STALE;
    if (key.epoch == s->key.epoch && key.sequence == s->key.sequence) {
        if (!same(key,s->key))
            return R5S_CONFLICT;
        if (s->phase == R5S_PREPARED || s->phase == R5S_ACCEPTED) {
            *cookie = s->cookie;
            return s->phase == R5S_ACCEPTED ? R5S_DUPLICATE : R5S_OK;
        }
        if (s->phase != R5S_RETRY)
            return R5S_STALE;
    } else {
        r5g_drop(&s->pool, &s->pending);
        s->key = key;
        s->cookie = 0;
        s->phase = R5S_RETRY;
    }
    r5g_collect(&s->pool,dispose);
    if (s->cursor == R5S_COOKIE_MAX) {
        s->phase = R5S_REJECTED;
        return R5S_EXHAUSTED;
    }
    if (key.slot) {
        uint32_t ticket;
        int status = r5g_begin(&s->pool,&ticket);
        if (status == R5G_BUSY)
            return R5S_BUSY;
        if (status != R5G_OK) {
            s->phase = R5S_REJECTED;
            return R5S_EXHAUSTED;
        }
        void *prepared = make(value);
        if (!prepared) {
            r5g_abort(&s->pool,ticket);
            s->phase = R5S_REJECTED;
            return R5S_FAILED;
        }
        s->pending = r5g_publish(&s->pool,ticket,prepared);
    }
    *cookie = s->cookie = ++s->cursor;
    s->phase = R5S_PREPARED;
    return R5S_OK;
}

int r5s_abort(struct r5s_state *s, struct r5s_key key, r5s_dispose_fn dispose)
{
    if (!key.epoch || !key.sequence || !same(key,s->key))
        return R5S_STALE;
    if (s->phase == R5S_ACCEPTED)
        return R5S_DUPLICATE;
    r5g_drop(&s->pool,&s->pending);
    r5g_collect(&s->pool,dispose);
    s->phase = R5S_REJECTED;
    return R5S_OK;
}

int r5s_accept402f(struct r5s_state *s, const uint8_t *p, unsigned size, uint32_t source)
{
    if (!p || size < 12 || p[0] != 5 || p[2] != 0x2f || p[3] != 0x40 ||
        !(p[11] & 0x80))
        return R5S_STOCK;
    if (size != 12 || p[1] || source != R5S_QUEUE_AP)
        return R5S_STALE;
    uint32_t cookie = p[9] | ((uint32_t)p[10] << 8) | ((uint32_t)(p[11]&0x7f) << 16);
    if (!cookie || cookie != s->cookie)
        return R5S_STALE;
    if (s->phase == R5S_ACCEPTED)
        return R5S_DUPLICATE;
    if (s->phase != R5S_PREPARED)
        return R5S_STALE;
    r5g_owner_replace(&s->pool,&s->current,&s->pending);
    s->phase = R5S_ACCEPTED;
    return R5S_OK;
}
