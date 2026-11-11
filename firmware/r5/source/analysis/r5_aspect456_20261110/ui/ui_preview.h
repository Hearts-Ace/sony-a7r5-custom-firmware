#ifndef R5_UI_PREVIEW_H
#define R5_UI_PREVIEW_H
#include "preview_core.h"
#include "r5_aspect_state.h"

/* Two native shooting-page families, six canvases each. These are owned
 * widget parameters, never retained model accessor pointers. */
struct r5_ui_guide_slot {
    unsigned char *parameter;
    uint32_t generation, token, route, format;
};
extern struct r5_ui_guide_slot r5_ui_guides[12];
static inline unsigned r5_ui_selection_id(uint32_t token) {
    unsigned id = token & 7u;
    return (token & 8u) && id >= 4u ? id : 0;
}
void r5_ui_guide_unregister(void *owner);
void r5_ui_draw_sprite(void *widget, const r5_ui_rect *rectangles);
#endif
