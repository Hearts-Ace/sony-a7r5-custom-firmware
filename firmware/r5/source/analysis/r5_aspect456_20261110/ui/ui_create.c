/* Five native page families, normal/rotated layouts, real canvas identity.
 * Native disabled rows still allocate parameters. No I/O or diagnostic state. */
#include <stdint.h>
#include "ui_layout.h"
#include "ui_preview.h"

struct r5_ui_guide_slot r5_ui_guides[12];
static uint32_t get32(const void *p, unsigned off) { return *(const uint32_t *)((const unsigned char *)p + off); }
static void *getptr(const void *p, unsigned off) { return *(void * const *)((const unsigned char *)p + off); }

uint32_t r5_ui_before_create(void *view, unsigned scene, const void *descriptors,
                             unsigned count, unsigned direction, unsigned char *flags) {
    (void)scene; /* W1 is a scene ID; canvas is initialized by native 0x182ad30. */
    if (!view || !descriptors || !flags || direction > 2) return 0;
    unsigned layer = get32(view, 8);
    if (layer >= 6) return 0;
    unsigned config = 5;
    for (unsigned i = 0; i < 5; ++i)
        if (count == r5_ui_page_count[i] &&
            (descriptors == r5_ui_page_table(i, 0) || descriptors == r5_ui_page_table(i, 1))) {
            config = i; break;
        }
    if (config == 5) return 0;
    unsigned row = r5_ui_page_row[config];
    if (get32(descriptors, row * 52) != r5_ui_page_kind[config]) return 0;
    uint64_t required = 0;
    for (unsigned i = 0; i < count; ++i) {
        unsigned kind = get32(descriptors, i * 52);
        if (kind >= R5_UI_ALLOCATOR_COUNT) return 0;
        unsigned bytes = i != row && flags[i] ? r5_ui_disabled_bytes[kind] : r5_ui_allocation_bytes[kind];
        if (!bytes) return 0;
        required += bytes;
    }
    /* Match native arena's strict upper bound, not <=. */
    if (!getptr(view, 0x3e98) || required >= get32(view, 0x3ea0)) return 0;
    uint32_t result = 0x80000000u | (config << 24) | (layer << 16) | flags[row];
    flags[row] = 0;
    return result;
}

void r5_ui_after_create(void *view, unsigned char *flags, uint32_t result) {
    if (!(result >> 31) || !view || !flags) return;
    unsigned config = (result >> 24) & 7, layer = (result >> 16) & 7;
    if (config >= 5 || layer >= 6) return;
    unsigned row = r5_ui_page_row[config];
    flags[row] = (unsigned char)result;
    if (config < 3) return;
    struct r5_ui_guide_slot *s = &r5_ui_guides[(config - 3) * 6 + layer];
    ++s->generation; s->token = 0; s->parameter = 0;
    /* Failed construction must not retain the previous generation's pointer. */
    if (get32(view, 0x3e90) != r5_ui_page_count[config]) return;
    unsigned char *widget = getptr(view, 0x3ec8 + row * 8);
    if (widget) s->parameter = widget + 0x1d8;
}

void r5_ui_guide_unregister(void *owner) {
    unsigned char *parameter = (unsigned char *)owner + 0x1d8;
    for (unsigned i = 0; i < 12; ++i)
        if (r5_ui_guides[i].parameter == parameter) {
            r5_ui_guides[i].parameter = 0; r5_ui_guides[i].token = 0; ++r5_ui_guides[i].generation;
        }
}
