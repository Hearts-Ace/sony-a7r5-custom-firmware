/* Native Sprite primitive ABI, compiled with FP enabled. The outer wrapper
 * preserves native post-update GPR/SIMD/NZCV/FPCR/FPSR state. */
#include "ui_preview.h"
struct vector { float x, y; };
extern void r5_ui_native_widget_position(void *, const struct vector *);
extern void r5_ui_native_widget_mode(void *, unsigned);
extern void r5_ui_native_rect_position(void *, unsigned, const struct vector *);
extern void r5_ui_native_rect_size(void *, unsigned, float, float);
extern void r5_ui_native_rect_color(void *, unsigned, const void *);
extern void r5_ui_native_color_construct(void *, unsigned char, unsigned char, unsigned char, unsigned char);

void r5_ui_draw_sprite(void *widget, const r5_ui_rect *rectangles) {
    void *sprite = (unsigned char *)widget + 0x248;
    uint32_t color[4]; struct vector zero = {0, 0};
    r5_ui_native_widget_position(widget, &zero);
    if (rectangles) r5_ui_native_color_construct(color, 0, 0, 0, 255);
    for (unsigned i = 0; i < 9; ++i) {
        float width = 0, height = 0;
        if (rectangles && i < 2) {
            struct vector position = {(float)rectangles[i].x, (float)rectangles[i].y};
            r5_ui_native_rect_position(sprite, i, &position);
            r5_ui_native_rect_color(sprite, i, color);
            width = (float)rectangles[i].width; height = (float)rectangles[i].height;
        }
        r5_ui_native_rect_size(sprite, i, width, height);
    }
    r5_ui_native_widget_mode(widget, rectangles ? 2 : 3);
}
