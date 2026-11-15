#ifndef R5_UI_PREVIEW_CORE_H
#define R5_UI_PREVIEW_CORE_H
#include <stdint.h>

typedef struct { int32_t x, y, width, height; } r5_ui_rect;
typedef struct {
    r5_ui_rect viewport;
    uint32_t plane_width, plane_height;
    uint32_t pixel_numerator, pixel_denominator;
    uint32_t direction, mapping;
} r5_ui_preview;

/* All fields are copied scalars from one eligible snapshot. No firmware access.
 * Invalid/native/empty geometry returns zero without touching output. */
uint32_t r5_ui_preview_bars(const r5_ui_preview *, uint32_t id, r5_ui_rect output[2]);
#endif
