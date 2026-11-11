/* Supplied R5 reference's integer mask geometry and latest user-selected ratios.
 * IDs 4..7: 1.618:1, 2.39:1, 5:4, 1.85:1. Pixel aspect precedes orientation. */
#include "preview_core.h"

uint32_t r5_ui_preview_bars(const r5_ui_preview *snapshot, uint32_t id,
                            r5_ui_rect output[2]) {
    static const uint16_t numerators[4] = {809, 239, 5, 37};
    static const uint16_t denominators[4] = {500, 100, 4, 20};
    if (!snapshot || !output || id < 4 || id > 7) return 0;
    r5_ui_preview s = *snapshot;
    r5_ui_rect v = s.viewport;
    if (!s.plane_width || !s.plane_height || s.plane_width > 65535 || s.plane_height > 65535
        || v.x < 0 || v.y < 0 || v.width <= 0 || v.height <= 0
        || (uint64_t)(uint32_t)v.x + (uint32_t)v.width > s.plane_width
        || (uint64_t)(uint32_t)v.y + (uint32_t)v.height > s.plane_height
        || !s.pixel_numerator || !s.pixel_denominator
        || s.pixel_numerator > 16 || s.pixel_denominator > 16
        || s.direction > 2 || s.mapping > 4) return 0;
    uint32_t n = numerators[id - 4] * s.pixel_denominator;
    uint32_t d = denominators[id - 4] * s.pixel_numerator;
    uint32_t a = (uint32_t)v.width * d, b = (uint32_t)v.height * n;
    r5_ui_rect bars[2];
    if (a > b) {
        uint32_t t = (a - b + d) / (2u * d);
        if (!t || 2u * t >= (uint32_t)v.width) return 0;
        bars[0] = (r5_ui_rect){v.x, v.y, (int32_t)t, v.height};
        bars[1] = (r5_ui_rect){v.x + v.width - (int32_t)t, v.y, (int32_t)t, v.height};
    } else {
        uint32_t t = (b - a + n) / (2u * n);
        if (!t || 2u * t >= (uint32_t)v.height) return 0;
        bars[0] = (r5_ui_rect){v.x, v.y, v.width, (int32_t)t};
        bars[1] = (r5_ui_rect){v.x, v.y + v.height - (int32_t)t, v.width, (int32_t)t};
    }
    for (uint32_t i = 0; i < 2; ++i) {
        r5_ui_rect r = bars[i];
        if (!s.direction) continue;
        if ((s.direction == 1) != (s.mapping == 4))
            bars[i] = (r5_ui_rect){(int32_t)s.plane_height - r.y - r.height, r.x, r.height, r.width};
        else
            bars[i] = (r5_ui_rect){r.y, (int32_t)s.plane_width - r.x - r.width, r.height, r.width};
    }
    output[0] = bars[0]; output[1] = bars[1];
    return 1;
}
