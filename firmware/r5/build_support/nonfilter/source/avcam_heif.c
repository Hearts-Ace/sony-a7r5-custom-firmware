/* A7R5 4.00 每格式私有 view：HEIF 编码和 RAW JPEG 预览只裁局部 ROI。
 * L 继续原生 plan；M/S 沿原 resize；原始共享 YC 及 Bayer 保持。
 */
#include <stdint.h>
#include "crop_core.h"

extern uint32_t aspect_native_prepare(uint32_t, uint32_t, void *, void *,
    void *, void *, void *, void *, uint32_t *, uint32_t);
extern void aspect_native_headers(void *, uint32_t, void *, void **);
extern void aspect_native_header_size(void *, uint32_t, uint32_t);
extern void aspect_native_makernote_full_size(void *, uint32_t, uint32_t);
extern void aspect_native_raw_headers(void *, void *, void **);
extern void aspect_native_raw_develop(void *, uint32_t, const uint16_t *,
    const uint16_t *, uint16_t *);

static uint32_t word(const uint8_t *p) { return *(const uint32_t *)p; }
static uint32_t le32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8)
        | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* 与已核实 Sony L/M/S 的 crop_core 输出及 AP 精确尺寸识别表一致。 */
static const uint16_t aspect_crop_sizes[4][3][2] = {
    {{9504,5872}, {6240,3856}, {4752,2936}},
    {{9504,3976}, {6240,2608}, {4752,1992}},
    {{7920,6336}, {5200,4160}, {3968,3168}},
    {{9504,5136}, {6240,3376}, {4752,2568}}
};

static uint32_t aspect_match_crop_wh(uint32_t w, uint32_t h)
{
    for (uint32_t r = 0; r < 4; ++r)
        for (uint32_t t = 0; t < 3; ++t)
            if (w == aspect_crop_sizes[r][t][0] && h == aspect_crop_sizes[r][t][1])
                return r + 4;
    return 0;
}

static uint32_t aspect_emb_source_ready(const aspect_geometry *g,
    uint32_t id, uint32_t raw_w, uint32_t raw_h)
{
    uint32_t cw = g->canvas_w, ch = g->canvas_h, sw = g->width, sh = g->height;
    if (!cw || !ch || (cw & 127u) || (g->x & 7u) || sw < raw_w || sh < raw_h
        || (uint32_t)g->x + ((sw + 127u) & ~127u) > cw
        || (uint32_t)g->y + ((sh + 7u) & ~7u) > ch) return 0;
    for (uint32_t t = 0; t < 3; ++t)
        if (sw == aspect_crop_sizes[id - 4][t][0]
            && sh == aspect_crop_sizes[id - 4][t][1]) return 1;
    return 0;
}

static uint32_t aspect_avcam_slot_id(const uint8_t *ctx, uint32_t slot,
    uint32_t allow_jpeg, uint32_t *width, uint32_t *height)
{
    const uint8_t *s = ctx + 0x440;
    const uint8_t *f = s + (slot == 1 ? 0xa4 : 0x224);
    uint32_t fmt = word(f);
    if ((slot != 1 && slot != 16)
        || (fmt != 4 && (!allow_jpeg || fmt != 1))
        || word(f + 8) != 0) return 0;
    const uint16_t *wh = (const uint16_t *)(s + (slot == 1 ? 0x3a4 : 0x3a8));
    uint32_t id = aspect_match_crop_wh(wh[0], wh[1]);
    if (id && width && height) {
        *width = wh[0];
        *height = wh[1];
    }
    return id;
}

uint32_t aspect_avcam_heif_id(const uint8_t *ctx, uint32_t slot)
{
    return aspect_avcam_slot_id(ctx, slot, 0, 0, 0);
}

uint32_t aspect_avcam_heif_prepare(uint32_t slot, uint32_t mode, void *ctx,
    void *owner, aspect_geometry *source, void *input, aspect_geometry *target,
    void *output, uint32_t *unit, uint32_t debug)
{
    uint32_t result = aspect_native_prepare(slot, mode, ctx, owner, source,
        input, target, output, unit, debug);
    if (result || mode != 0) return result;
    uint32_t w, h, id = aspect_avcam_slot_id(ctx, slot, 1, &w, &h);
    if (!id) return 0;
    if (!aspect_emb_source_ready(source, id, w, h)) {
        aspect_geometry cropped;
        if (!aspect_crop_geometry(source, id, 0, &cropped)
            || !aspect_emb_source_ready(&cropped, id, w, h)) return 2;
        *source = cropped;
    }
    if (target->width != w || target->height != h) return 2;
    return 0;
}

/* 无损压缩 RAW M/S 在 0x2044dc 下采样显影后，0x1f2d7c 按显影 3:2 框重写
 * DefaultCrop 与 SonyCrop。将本张冻结比例映射到显影 M/S 框后再交原生居中写入。
 */
void aspect_avcam_raw_develop(void *raw_ctx, uint32_t mode,
    const uint16_t *active, const uint16_t *def_crop, uint16_t *sony_wh)
{
    const uint8_t *extra = *(const uint8_t *const *)((const uint8_t *)raw_ctx + 0x80);
    uint32_t id = extra ? aspect_match_crop_wh(le32(extra + 0x248), le32(extra + 0x24c)) : 0;
    aspect_geometry crop;
    if (id) {
        aspect_geometry source = {(uint16_t)((def_crop[0] + 127u) & ~127u),
            def_crop[1], def_crop[0], def_crop[1], 0, 0};
        if (!aspect_crop_geometry(&source, id, 0, &crop)) return;
        sony_wh[0] = crop.width;
        sony_wh[1] = crop.height;
    }
    aspect_native_raw_develop(raw_ctx, mode, active, def_crop, sony_wh);
    if (id) {
        uint32_t *emb = *(uint32_t *const *)((const uint8_t *)raw_ctx + 0x78);
        if (emb) {
            emb[0] = crop.width;
            emb[1] = crop.height;
        }
    }
}

uint32_t aspect_avcam_heif_encode(uint8_t *ctx, uint32_t mode,
    aspect_geometry *geometry, uint32_t slot)
{
    uint32_t id = aspect_avcam_heif_id(ctx, slot);
    if (!id) return 0;
    const uint16_t *wh = (const uint16_t *)(ctx + 0x440 + (slot == 1 ? 0x3a4 : 0x3a8));
    /* 原生 M/S resize 已物化的单 slot 输出不重复裁切。 */
    if (!(mode == 0 && geometry->width == wh[0] && geometry->height == wh[1]
          && geometry->x == 0 && geometry->y == 0)) {
        if (!aspect_crop_geometry(geometry, id | (mode ? ASPECT_GEOMETRY_AUX : 0),
                                  0, geometry)) return 2;
    }
    if (mode == 0) {
        if (geometry->width != wh[0] || geometry->height != wh[1]) return 2;
        void *headers[6];
        aspect_native_headers(ctx + 0x440, slot, *(void **)(ctx + 0x828), headers);
        aspect_native_header_size(headers[0], wh[0], wh[1]);
        aspect_native_makernote_full_size(headers[1], wh[0], wh[1]);
    }
    return 0;
}

/* 原生 RAW getter 的第 19 项是本张照片 extra-IFD。SonyCrop 由 CP 冻结
 * task 生成；不读取当前菜单，也不依赖另一格式的 L/M/S 或拍摄顺序。
 */
uint32_t aspect_avcam_raw_crop(const uint8_t *ctx, uint32_t *width, uint32_t *height)
{
    const uint8_t *info = ctx + 0x440;
    if (word(info + 0xa4) != 2 && word(info + 0x224) != 2) return 0;
    void *base = *(void **)(ctx + 0x840);
    if (!base) return 0;
    void *headers[19];
    aspect_native_raw_headers((void *)info, base, headers);
    const uint8_t *extra = headers[18];
    uint32_t w = le32(extra + 0x248), h = le32(extra + 0x24c);
    uint32_t id = aspect_match_crop_wh(w, h);
    if (id) {
        *width = w;
        *height = h;
    }
    return id;
}

/* RAW EMB 和 HEIF 10→8bit 辅助图的原生 prepare 返回局部 source/target。
 * 只裁这两个 view；canvas、原有申请和共享 YC 不变。辅助 stage 的 slot
 * 来自 HEIF mask，故用本张 SonyCrop 判定 RAW 裁切，不能把该 slot 当 RAW。
 */
uint32_t aspect_avcam_raw_preview_prepare(uint32_t slot, uint32_t mode, void *ctx,
    void *owner, aspect_geometry *source, void *input, aspect_geometry *target,
    void *output, uint32_t *unit, uint32_t debug)
{
    static const uint16_t scn[4][2] = {{1616,1000},{1616,680},{1344,1080},{1616,872}};
    static const uint16_t thm[4][2] = {{320,200},{320,136},{256,208},{320,176}};
    uint32_t result = aspect_native_prepare(slot, mode, ctx, owner, source,
        input, target, output, unit, debug);
    if (result) return result;
    uint32_t w, h, id;
    const uint8_t *info = (const uint8_t *)ctx + 0x440;
    if (word(info + 0xa4) == 2 || word(info + 0x224) == 2) {
        id = aspect_avcam_raw_crop(ctx, &w, &h);
    } else {
        /* 无 RAW 的 HEIF 拍摄也生成 160×120 JPEG 小缩图；该辅助 stage
         * 使用实际 HEIF slot，因此比例直接来自本张已冻结的 HEIF WH。 */
        id = mode == 3 ? 0 : aspect_avcam_heif_id(ctx, slot);
    }
    if (!id) return 0;
    /* CP 已裁过的同档/高档 JPEG 解码 view 保留；原幅 3:2 view 按自身档位居中裁切后再缩放到 RAW SonyCrop。 */
    if (mode == 3) {
        if (!aspect_emb_source_ready(source, id, w, h)) {
            aspect_geometry cropped;
            if (!aspect_crop_geometry(source, id, 0, &cropped)
                || !aspect_emb_source_ready(&cropped, id, w, h)) return 2;
            *source = cropped;
        }
    } else {
        const uint16_t *size = (mode == 1 ? scn : thm)[id - 4];
        w = size[0]; h = size[1];
        if (source->width != w || source->height != h) {
            aspect_geometry cropped;
            if (!aspect_crop_geometry(source, id | ASPECT_GEOMETRY_AUX, 0, &cropped)
                || cropped.width != w || cropped.height != h) return 2;
            *source = cropped;
        }
    }
    if (mode != 2) {
        if (target->width < w || target->height < h) return 2;
        target->width = w; target->height = h;
        target->x = 0; target->y = 0;
    }
    /* THM 原生 160×120 canvas 保留，由既有 source-WH fit 居中填黑。 */
    return 0;
}

/* 原生 0x10e image 的 validOffset / validWH，不新增协议字段。 */
uint64_t aspect_avcam_heif_origin(const uint8_t *ctx, const aspect_geometry *geometry)
{
    if (!aspect_avcam_heif_id(ctx, 1) && !aspect_avcam_heif_id(ctx, 16)) return 0;
    return (uint64_t)geometry->x | ((uint64_t)geometry->y << 16)
        | ((uint64_t)geometry->width << 32) | ((uint64_t)geometry->height << 48);
}
