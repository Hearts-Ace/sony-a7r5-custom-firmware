#include "job.h"

int r5j_copy(struct r5j_object *copy, const void *original, uint32_t cookie)
{
    if (!copy || !original || copy == original || !cookie || cookie > R5S_COOKIE_MAX)
        return -1;
    const uint8_t *s = original;
    if (s[0x1d] || s[0x1e] || s[0x1f])
        return -1; /* preserve all original selectors outside the known byte ABI */
    uint8_t *d = (void *)copy;
    for (unsigned i=0;i<sizeof(*copy);++i)
        d[i] = s[i];
    uint32_t word = r5s_color_word(s[0x1c],cookie);
    d[0x1d] = (uint8_t)(word >> 8);
    d[0x1e] = (uint8_t)(word >> 16);
    d[0x1f] = (uint8_t)(word >> 24);
    return 0;
}

void r5j_serialize_color(uint32_t mode, uint32_t look, uint8_t out[4], r5j_leaf leaf)
{
    if (!(look & R5S_TAG)) {
        leaf(mode,look,out);
        return;
    }
    leaf(mode,look & 255u,out);
    out[1] = (uint8_t)(look >> 8);
    out[2] = (uint8_t)(look >> 16);
    out[3] = (uint8_t)(look >> 24);
}
