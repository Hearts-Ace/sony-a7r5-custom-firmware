/* Offline candidate core. Firmware hooks and camera use are not enabled here.
 * Packed 4:2:2 JPEG input contract recovered from stock 0x499190.
 */
#include "crop_core.h"

/* The bounded inputs make every multiplication below fit uint32_t. */
__attribute__((noinline))
uint32_t aspect_divide(uint32_t n, uint32_t d)
{
    uint32_t q = 0, r = 0;
    for (uint32_t bit = 32; bit; --bit) {
        r = (r << 1) | ((n >> (bit - 1)) & 1u);
        if (r >= d) { r -= d; q |= 1u << (bit - 1); }
    }
    return q;
}

/* IDs are AP menu-domain IDs, 4..7. Source remains full 3:2.
 * Private ASPECT_GEOMETRY_AUX permits the small original SCN/THM 3:2
 * approximation (1616x1080 and320x212); main-image validation stays exact.
 * Success writes a new ROI only, without touching the canvas or pixels.
 * Failure leaves *out unchanged, including when out == source.
 * Input base must be 16-byte aligned; the native memory-input canvas is 128
 * pixels wide per block. Native target dimensions require width%16==0 and
 * height%8==0 (498790). Labels denote nominal ratios, with pixel rounding.
 */
uint32_t aspect_crop_geometry(const aspect_geometry *source, uint32_t id,
                              uint32_t physical_base_low, aspect_geometry *out)
{
    static const uint8_t numerators[4] = {17, 65, 5, 7};
    static const uint8_t denominators[4] = {6, 24, 4, 6};
    uint32_t auxiliary=id & ASPECT_GEOMETRY_AUX;
    id &= ~ASPECT_GEOMETRY_AUX;
    if (!source || !out || id < 4 || id > 7) return 0;
    aspect_geometry s = *source;
    uint32_t cw = s.canvas_w, ch = s.canvas_h, sw = s.width, sh = s.height;
    if (!cw || !ch || !sw || !sh || (physical_base_low & 15u) || (cw & 127u)
        || (sw & 1u) || (sh & 1u)
        || (auxiliary ? sw*2u+16u<sh*3u || sh*3u+16u<sw*2u : sw*2u!=sh*3u)
        || (uint32_t)s.x + sw > cw || (uint32_t)s.y + sh > ch) return 0;
    uint32_t p = numerators[id - 4], q = denominators[id - 4];
    uint32_t w, h;
    if (sw * q >= sh * p) {
        h = sh & ~7u;
        w = aspect_divide(h * p + q * 8u, q * 16u) * 16u;
        if (w > sw) w = sw & ~15u;
    } else {
        w = sw & ~15u;
        h = aspect_divide(w * q + p * 4u, p * 8u) * 8u;
        if (h > sh) h = sh & ~7u;
    }
    if (w < 16u || h < 8u) return 0;
    {
        uint32_t pw = (w + 127u) & ~127u, ph = (h + 7u) & ~7u;
        uint32_t xmin = ((uint32_t)s.x + 7u) & ~7u;
        if (pw > cw || ph > ch || xmin > cw - pw) return 0;
        uint32_t xmax = (uint32_t)s.x + sw - w;
        if (cw - pw < xmax) xmax = cw - pw;
        if (xmin > xmax) return 0;
        uint32_t x = ((uint32_t)s.x + (sw - w) / 2u) & ~7u;
        if (x < xmin) x = xmin;
        if (x > xmax) x = xmax & ~7u;
        if (x < xmin) return 0;
        uint32_t ymax = (uint32_t)s.y + sh - h;
        if (ch - ph < ymax) ymax = ch - ph;
        if ((uint32_t)s.y > ymax) return 0;
        uint32_t y = (uint32_t)s.y + (sh - h) / 2u;
        if (y > ymax) y = ymax;
        aspect_geometry result = {(uint16_t)cw, (uint16_t)ch,
            (uint16_t)w, (uint16_t)h, (uint16_t)x, (uint16_t)y};
        *out = result;
        return 1;
    }
}
