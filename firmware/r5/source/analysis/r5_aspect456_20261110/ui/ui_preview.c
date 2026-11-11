/* Supplied reference's five-page native-mask integration, adapted to exact455
 * and the shared r5_aspect full-epoch API. No file I/O, traces or model pointers
 * retained across unlock; drawing uses scalar snapshots only. */
#include "ui_preview.h"

extern void r5_ui_native_guide_producer(void *, void *, void *, const void *);
extern void r5_ui_native_guide_body(void *, void *, void *, const void *);
extern void r5_ui_original_guide_update(void *);
extern void r5_ui_original_guide_destroy(void *);
extern unsigned r5_ui_original_guide_model_0(void *, unsigned);
extern unsigned r5_ui_original_guide_model_1(void *, unsigned);
extern void r5_ui_native_guide_rect(void *, unsigned, unsigned, const r5_ui_rect *, unsigned);
extern void r5_ui_native_model_lock(void *);
extern void r5_ui_native_model_unlock(void *);
extern const uint32_t *r5_ui_native_model_x(void), *r5_ui_native_model_y(void), *r5_ui_native_model_w(void), *r5_ui_native_model_h(void);
extern const uint32_t *r5_ui_native_model_route(void), *r5_ui_native_model_format(void), *r5_ui_native_model_direction(void), *r5_ui_native_model_mapping(void);
extern const uint32_t *r5_ui_native_model_mode(void), *r5_ui_native_model_aspect(void);
extern unsigned r5_ui_native_sprite_image(const void *);

void *r5_ui_guide_cookie;
static uint32_t get32(const void *p, unsigned off) { return *(const uint32_t *)((const unsigned char *)p + off); }
static void put32(void *p, unsigned off, uint32_t value) { *(uint32_t *)((unsigned char *)p + off) = value; }
static void *getptr(const void *p, unsigned off) { return *(void * const *)((const unsigned char *)p + off); }
static struct r5_ui_guide_slot *guide(void *p) {
    for (unsigned i = 0; i < 12; ++i) if (r5_ui_guides[i].parameter == p) return &r5_ui_guides[i];
    return 0;
}

/* R5 product2 -> internal23 -> feature3 -> column16. Adapt only the static
 * model gate and only the completed private Guide. Original exposure/display/
 * output gates and the second page's subsequent bulk rejection remain live. */
static unsigned guide_model(void *presenter, unsigned row, unsigned page) {
    unsigned allowed = page ? r5_ui_original_guide_model_1(presenter, row) :
                              r5_ui_original_guide_model_0(presenter, row);
    uint32_t selected = r5_aspect_token();
    if (allowed || row != (page ? 3u : 4u) || !r5_ui_selection_id(selected) ||
        get32(presenter, page ? 0x478c0 : 0x4ff14) != 16) return allowed;
    unsigned char *parameters = getptr(presenter, page ? 0x1e0 : 0x270);
    if (!parameters || get32(parameters, row * 16) != 61) return allowed;
    unsigned char *parameter = getptr(parameters, row * 16 + 8);
    struct r5_ui_guide_slot *s = guide(parameter);
    if (!s || s < r5_ui_guides + page * 6 || s >= r5_ui_guides + (page + 1) * 6 ||
        !s->token || s->token != selected || !parameter[0x44]) return allowed;
    return 1;
}
unsigned r5_ui_guide_model_0(void *presenter, unsigned row) { return guide_model(presenter, row, 0); }
unsigned r5_ui_guide_model_1(void *presenter, unsigned row) { return guide_model(presenter, row, 1); }

static unsigned pixels(r5_ui_preview *s, unsigned route, unsigned format) {
    s->pixel_numerator = 1; s->pixel_denominator = 1;
    if (route == 0) return 1;
    if (route != 1) return 0;
    if (format == 1) return 1;
    if (format == 2) { s->pixel_numerator = 4; s->pixel_denominator = 3; return 1; }
    if (format == 3) { s->pixel_numerator = 9; s->pixel_denominator = 8; return 1; }
    return 0;
}

void r5_ui_guide_produce(void *context, void *parameter, void *changed, const void *snapshot) {
    struct r5_ui_guide_slot *s = guide(parameter);
    uint32_t selected = r5_aspect_token(), generation = s ? s->generation : 0;
    if (s) s->token = 0;
    if (!s || !r5_ui_selection_id(selected) || get32(snapshot, 0x24d8) != 2 || get32(snapshot, 0x24b0) != 0) {
        r5_ui_native_guide_producer(context, parameter, changed, snapshot); return;
    }
    void *previous = r5_ui_guide_cookie; r5_ui_guide_cookie = parameter;
    r5_ui_native_guide_body(context, parameter, changed, snapshot);
    r5_ui_guide_cookie = previous;
    if (s->parameter != parameter || s->generation != generation || r5_aspect_token() != selected ||
        !((unsigned char *)parameter)[0x44]) return;
    ((unsigned char *)parameter)[0x2c] = 1;
    put32(parameter, 0x4c, 15); /* Native full-opacity color level. */
    s->route = get32(snapshot, 0x25c0); s->format = get32(snapshot, 0x25e0); s->token = selected;
}

void r5_ui_guide_update(void *owner) {
    r5_ui_original_guide_update(owner);
    unsigned char *parameter = (unsigned char *)owner + 0x1d8;
    struct r5_ui_guide_slot *s = guide(parameter);
    uint32_t selected = r5_aspect_token();
    if (!s || !s->token || s->token != selected || !r5_ui_selection_id(selected) ||
        !parameter[0x2c] || !parameter[0x44]) return;
    r5_ui_preview snapshot = {.viewport = {get32(parameter, 0x30), get32(parameter, 0x34),
        get32(parameter, 0x38), get32(parameter, 0x3c)}, .plane_width = 640, .plane_height = 480};
    r5_ui_rect bars[2], zero = {0, 0, 0, 0};
    /* Native Guide::setRect performs its own direction/mapping transform. */
    if (!pixels(&snapshot, s->route, s->format) || !r5_ui_preview_bars(&snapshot, r5_ui_selection_id(selected), bars)) return;
    if (r5_aspect_token() != selected || s->token != selected) return;
    for (unsigned i = 0; i < 8; ++i)
        r5_ui_native_guide_rect(owner, i, i < 2, i < 2 ? bars + i : &zero, i < 2 ? 0x02094052u : ~0u);
}
void r5_ui_guide_destroy(void *owner) {
    r5_ui_guide_unregister(owner); r5_ui_original_guide_destroy(owner);
}

void r5_ui_page_draw(void *presenter, unsigned page) {
    static const unsigned view_offsets[3] = {0x80, 0x40, 0x68};
    static const unsigned parameter_offsets[3] = {0x88, 0x48, 0x70};
    static const unsigned counts[3] = {98, 38, 76}, rows[3] = {4, 6, 6};
    static const unsigned directions[3] = {0x7278, 0x1340, 0x1378};
    static const unsigned routes[3] = {0x10e8, 0x3210, 0x5338};
    if (page >= 3 || !presenter) return;
    unsigned char *view = getptr(presenter, view_offsets[page]);
    unsigned char *parameters = getptr(presenter, parameter_offsets[page]);
    if (!view || !parameters || get32(view, 0x3e90) != counts[page] || get32(parameters, rows[page] * 16) != 0) return;
    unsigned char *widget = getptr(view, 0x3ec8 + rows[page] * 8);
    if (!widget || getptr(parameters, rows[page] * 16 + 8) != widget + 0x1d8) return;
    unsigned char *sprite = widget + 0x248;
    /* Actual Image construction leaves parameter+0x30 = 0; test the loaded
     * image and nine-rectangle Sprite, not a synthetic FFFFFFFF parameter. */
    if (get32(widget, 0x214) != ~0u || !getptr(sprite, 0xd0) ||
        get32(sprite, 0xd8) != 0x00090009u || r5_ui_native_sprite_image(sprite) != ~0u) return;
    r5_ui_preview snapshot = {.plane_width = 640, .plane_height = 480};
    r5_ui_rect bars[2]; unsigned id = 0, route = 0, format = 0;
    uint32_t selected = r5_aspect_token();
    if (!page) {
        if (get32(presenter, 0x5830) == R5_ASPECT_LEAF) {
            unsigned alias = get32(presenter, 0x7180);
            if (alias - R5_ASPECT_ALIAS_FIRST < 4) id = alias - R5_ASPECT_ALIAS_FIRST + 4;
        }
        const unsigned char *completed = (const unsigned char *)presenter + 0xf00;
        snapshot.viewport = (r5_ui_rect){get32(completed, 0x128), get32(completed, 0x148),
            get32(completed, 0x168), get32(completed, 0x188)};
        route = get32(completed, 0x1e8); format = get32(completed, 0x208);
        snapshot.direction = get32(completed, 0x6378); snapshot.mapping = get32(completed, 0x5a60);
    } else if ((id = r5_ui_selection_id(selected)) != 0) {
        unsigned char lock[16] = {0}; unsigned mode, aspect;
        r5_ui_native_model_lock(lock);
        snapshot.viewport = (r5_ui_rect){*r5_ui_native_model_x(), *r5_ui_native_model_y(), *r5_ui_native_model_w(), *r5_ui_native_model_h()};
        route = *r5_ui_native_model_route(); format = *r5_ui_native_model_format();
        snapshot.direction = *r5_ui_native_model_direction(); snapshot.mapping = *r5_ui_native_model_mapping();
        mode = *r5_ui_native_model_mode(); aspect = *r5_ui_native_model_aspect();
        r5_ui_native_model_unlock(lock);
        if (mode != 2 || aspect != 0 || r5_aspect_token() != selected) id = 0;
    }
    if (!id || snapshot.direction != get32(presenter, 8) ||
        snapshot.direction != get32(presenter, directions[page]) || route != get32(presenter, routes[page]) ||
        !pixels(&snapshot, route, format) || !r5_ui_preview_bars(&snapshot, id, bars)) {
        r5_ui_draw_sprite(widget, 0); return;
    }
    r5_ui_draw_sprite(widget, bars);
}
