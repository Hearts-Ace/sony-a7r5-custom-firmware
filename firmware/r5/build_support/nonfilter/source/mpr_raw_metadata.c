/* Sony 4.00 libarw：同步本 record 已构造的私有 TIFF，不回写共享源。 */
#include <stdint.h>
#include <stddef.h>
extern void *aspect_mpr_native_tag(void *, uint32_t);
extern int32_t aspect_mpr_native_jpeg_size(void *);
static uint32_t u32(const void *p) { return *(const uint32_t *)p; }
static void *ptr(const void *p) { return *(void *const *)p; }
/* native tag reference为entry、payload指针。先完整验证再提交。 */
static uint32_t *tag(void *ifd, uint32_t id, uint32_t count,
                     uintptr_t lo, uintptr_t hi)
{
    if (!ifd) return NULL;
    const uint8_t *ref = aspect_mpr_native_tag(ifd, id);
    if (!ref) return NULL;
    const uint8_t *entry = ptr(ref);
    uint32_t *value = ptr(ref + 8);
    uintptr_t e = (uintptr_t)entry, v = (uintptr_t)value;
    if (e < lo || e > hi || hi - e < 12 || v < lo || v > hi
        || hi - v < count * 4u || *(const uint16_t *)(entry + 2) != 4
        || u32(entry + 4) != count) return NULL;
    return value;
}
int32_t aspect_mpr_raw_metadata(void *object, const uint8_t *cnv, int32_t bytes)
{
    static const uint16_t crops[12][2] = {
        {9504,5872},{6240,3856},{4752,2936},
        {9504,3976},{6240,2608},{4752,1992},
        {7920,6336},{5200,4160},{3968,3168},
        {9504,5136},{6240,3376},{4752,2568}
    };
    static const uint16_t scenes[4][2] = {
        {1616,1000},{1616,680},{1344,1080},{1616,872}
    };
    const uint8_t *app = object;
    uintptr_t lo = (uintptr_t)ptr(app + 8);
    uint32_t capacity = u32(cnv + 0xf0);
    if (bytes <= 0 || (uint32_t)bytes > capacity
        || lo != (uintptr_t)ptr(cnv + 0xf8)) return -1;
    uintptr_t hi = lo + (uint32_t)bytes;
    if (hi < lo) return -1;
    /* Recognize this file's actual EMB dimensions; never infer preview from
     * SonyCrop, which intentionally remains the original full sensor area. */
    const uint8_t *geometry = ptr(cnv + 0xd0);
    if (!geometry) return 0;
    uint32_t w = *(const uint16_t *)geometry;
    uint32_t h = *(const uint16_t *)(geometry + 4);
    uint32_t id;
    for (id = 0; id < 12; ++id)
        if (w == crops[id][0] && h == crops[id][1]) break;
    if (id == 12) return 0;
    /* 与此调用点前原生strb写SOI使用同一BufferArea+10指针；
     * 不假设+18另一别名的缓存/同步语义。 */
    const uint8_t *scene = ptr(cnv + 0x1b8);
    uint32_t scene_bytes = u32(cnv + 0x1b0);
    if (!scene || scene_bytes <= 0xa4) return -1;
    struct {
        const uint8_t *data;
        uint32_t bytes, width, height, components, rest[2];
    } jpeg = {scene + 0xa2, scene_bytes - 0xa2, 0, 0, 0, {0,0}};
    if (aspect_mpr_native_jpeg_size(&jpeg) != 0
        || jpeg.width != scenes[id / 3][0]
        || jpeg.height != scenes[id / 3][1]) return -1;
    uint32_t *width = tag(ptr(app + 0x48), 0xa002, 1, lo, hi);
    uint32_t *height = tag(ptr(app + 0x48), 0xa003, 1, lo, hi);
    uint32_t *full = tag(ptr(app + 0x50), 0xb02b, 2, lo, hi);
    uint32_t *preview = tag(ptr(app + 0x50), 0xb02c, 2, lo, hi);
    if (!width || !height || !full || !preview) return -1;
    *width = w; *height = h;
    full[0] = h; full[1] = w;
    preview[0] = jpeg.height; preview[1] = jpeg.width;
    return 0;
}
