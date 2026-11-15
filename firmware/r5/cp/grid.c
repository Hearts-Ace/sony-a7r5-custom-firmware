#include "grid.h"
#include "context.h"
#include "owners.h"
#include "grid_owners.h"

#define PTR(T,x) ((T *)(uintptr_t)(x))
#define ORDER 0xe8c1d8u

void od_grid_prepare(struct od_context *c)
{
    const uint16_t *order = PTR(const uint16_t, ORDER);
    const int8_t *grid = (const void *)c->value.grid;
    for (unsigned level = 0; level < 8; ++level) {
        for (unsigned i = 0; i < 405; ++i) {
            uint32_t p = 0;
            for (unsigned ch = 0; ch < 3; ++ch) {
                int v = grid[ch * 405u + i];
                if (level)
                    v = v * (int)level >> 3;
                p |= ((uint32_t)v & 127u) << (22u - 10u * ch);
            }
            c->packed_grid[level][order[i]] = p;
        }
    }
}

/* 0: displaced stock source classification. 1/2: disabled/enabled custom
 * candidate; enter the common native port/late-disable/snapshot tail. */
unsigned od_grid_source(const uint32_t *work, const uint32_t *out)
{
    const uint8_t *root = PTR(const uint8_t, work[0]);
    const uint8_t *env = PTR(const uint8_t, work[1]);
    uint8_t *state = PTR(uint8_t, out[2]);
    uint32_t *field = (void *)(state + 0x20);
    unsigned index = PTR(const uint8_t, out[4])[0xb];
    struct r5g_lease pin;
    const struct od_context *c = od_work_pin(work, &pin);
    if (!od_match(c, work, env[0x25], 1) || root[0x36]) {
        od_work_drop(&pin);
        (void)od_grid_state_stock(state);
        return 0;
    }

    unsigned level = root[0x2f] <= 7 ? root[0x2f] : 0;
    unsigned selected = c->value.grid_enabled == 1 &&
        ((!root[1] && index == 0 && env[6] <= 1) ||
         (root[1] == 1 && !root[2] && !env[6] && env[0xc] == 6 && index == 3));
    if (!selected || !od_grid_state_own(state, &pin, level)) {
        selected = 0;
        (void)od_grid_field_clear(field);
    }
    od_work_drop(&pin);

    *(uint32_t *)(void *)(state + 0x184) = 0;
    state[0x188] = selected;
    state[0x189] = 2u * selected;
    state[0x19] = state[0x1a] = 0x20;
    state[0x1b] = env[3] == 0;
    state[0x24] = selected;
    if (index <= 2)
        PTR(uint8_t, out[5])[index] = selected;
    if (root[1] && root[3]) {
        uint8_t *snap = PTR(uint8_t, out[1]);
        *(uint32_t *)(void *)(snap + 0x60) = 0;
        snap[0x64] = selected;
        snap[0x65] = 2u * selected;
    }
    return selected + 1u;
}

void od_grid_snapshot(uint8_t *dst, const uint8_t *src)
{
    uint32_t *d = (void *)dst;
    const uint32_t *s = (const void *)src;
    d[0] = s[0];
    d[1] = s[1];
    d[3] = s[3];
    d[4] = s[4];
    if (!od_grid_field_copy(d + 2, s + 2)) {
        dst[0] = 0;
        dst[12] = 0;
    }
}

void od_grid_packet(uint8_t *packet, const uint8_t *env)
{
    uint32_t *dst = (void *)(packet + 0x350);
    const uint32_t *src = (const void *)(env + 0x44);
    dst[1] = src[1];
    if (!od_grid_field_copy(dst, src)) {
        packet[0x33c] = 0;
        packet[0x354] = 0;
    }
}

void od_grid_descriptor(uint8_t *desc, const uint8_t *packet)
{
    if (!desc)
        return;
    for (unsigned i = 0; i < 19; ++i)
        desc[i] = packet[0x33c + i];
    desc[0x18] = packet[0x354];
    if (!od_grid_field_copy((void *)(desc + 0x14), (const void *)(packet + 0x350))) {
        desc[0] = 0;
        desc[0x18] = 0;
    }
}

void od_grid_aa(uint32_t d, uint32_t a, uint32_t flags, const uint8_t *desc,
                uint32_t copy, uint32_t dst)
{
    extern void od_grid_aa_original(uint32_t, uint32_t, uint32_t, const uint8_t *, uint32_t, uint32_t);
    const uint32_t *source = (const void *)(desc + 0x14);
    uint32_t word = __atomic_load_n(source, __ATOMIC_ACQUIRE);
    uint8_t local[28] __attribute__((aligned(4)));
    for (unsigned i = 0; i < 28; ++i)
        local[i] = desc[i];
    uint32_t *packed = (void *)(local + 0x14);
    /* Even a stock read must not send the mutable original descriptor to AA
     * after classification. Its writer could install a token before the
     * original upload branch's pointer load. The local word is stable. */
    if ((word & 0xf0000000u) != OD_GRID_MARKER) {
        *packed = word;
        od_grid_aa_original(d, a, flags, local, copy, dst);
        return;
    }

    struct r5g_lease pin;
    unsigned level;
    const struct od_context *c = od_grid_desc_pin(desc, &pin, &level);
    if (!c || word != (OD_GRID_MARKER | (pin.ticket << 3) | level) ||
              word != __atomic_load_n(source, __ATOMIC_ACQUIRE)) {
        local[0] = 0;
        local[0x18] = 0;
        c = 0;
    }
    *packed = c ? (uint32_t)(uintptr_t)c->packed_grid[level] : 0;
    od_grid_aa_original(d, a, flags, local, copy, dst);
    od_work_drop(&pin);
}

/* The live ping-pong copy starts at native output +0x908. The grid state
 * starts eight bytes into it, so its source word is at block +0x28. */
void *od_grid_live_copy(uint8_t *dst, const uint8_t *src, uint32_t size)
{
    void *(*memcopy)(void *,const void *,uint32_t) = (void *)(uintptr_t)0x5f51bcu;
    void *result = memcopy(dst, src, size);
    if (size == 0x110u && !od_grid_field_copy((void *)(dst + 0x28), (const void *)(src + 0x28))) {
        dst[0x20] = 0; /* state+0x18 */
        dst[0x2c] = 0; /* state+0x24 */
    }
    return result;
}

/* Native live initialization clears both packet/state banks and its
 * independent snapshot. Retire their owners before the original zero. */
void *od_grid_live_reset(void *dst, uint32_t size)
{
    void *(*zero)(void *,uint32_t) = (void *)(uintptr_t)0x5f58b0u;
    od_grid_forget_range((uintptr_t)dst, size);
    return zero(dst, size);
}
