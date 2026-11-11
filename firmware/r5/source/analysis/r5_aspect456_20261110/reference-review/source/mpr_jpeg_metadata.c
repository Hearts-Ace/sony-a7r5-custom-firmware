/* Sony 4.00 libstill::add 的本张 JPEG 元数据；共享 GEN 始终只读。
 * 274320 前已把 ExifSrcArea 的 0xbc 字节复制到 object+13c0。
 * 先同步私有源，再让 273bbc 生成本张缓存，原 JPEG writer 保持。 */
#include <stdint.h>
#include <stddef.h>
extern const uint8_t aspect_mpr_native_jpeg_vtable[];
extern void aspect_mpr_native_cammeta(void *, const void *, void *);
static uint32_t word(const void *p) { return *(const uint32_t *)p; }
static void *pointer(const void *p) { return *(void *const *)p; }
static uint32_t be16(const uint8_t *p) { return (uint32_t)p[0] * 256u + p[1]; }
/* BufferArea 从 SOI 或 DQT 开始。只读 min(length,0x800) 内完整的
 * 8-bit、三分量 SOF0，不读熵数据或声明长度之外的字节。 */
static uint32_t jpeg_dimensions(const uint8_t *p, uint32_t bytes,
                                uint32_t *width, uint32_t *height)
{
    if (!p || bytes < 21) return 0;
    uint32_t limit = bytes < 0x800u ? bytes : 0x800u;
    if (p[0] != 0xff || (p[1] != 0xd8 && p[1] != 0xdb)) return 0;
    uint32_t at = p[1] == 0xd8 ? 2u : 0u;
    if (at + 4u > limit) return 0;
    while (at + 4u <= limit) {
        if (p[at] != 0xff) return 0;
        uint32_t marker = p[at + 1], length = be16(p + at + 2);
        if (length < 2u || length > limit - at - 2u) return 0;
        if (marker == 0xc0) {
            if (length != 17u || p[at + 4] != 8 || p[at + 9] != 3) return 0;
            *height = be16(p + at + 5);
            *width = be16(p + at + 7);
            return *width && *height;
        }
        if (marker == 0xda || marker == 0xd9) return 0;
        at += length + 2u;
    }
    return 0;
}
/* 分类为真实 Exif getter 278800 对这些精确 WH 的输出；generic
 * 273bbc 的旧区间不同。正式门逐项以完整原生 Exif getter 对照。 */
static const uint16_t crops[12][4] = {
    {9504,5872,0,0},{6240,3856,0,0},{4752,2936,0,0},
    {9504,3976,1,9},{6240,2608,1,9},{4752,1992,1,9},
    {7920,6336,1,5},{5200,4160,1,5},{3968,3168,1,5},
    {9504,5136,0,0},{6240,3376,0,0},{4752,2568,0,0}
};
void aspect_mpr_jpeg_metadata(void *object, const uint8_t *add, uint8_t *meta)
{
    uint8_t *owned = object;
    uint32_t id = 12, w = 0, h = 0;
    if (pointer(object) == (const void *)aspect_mpr_native_jpeg_vtable
        && pointer(add) && jpeg_dimensions(pointer(add + 0x158),
                                            word(add + 0x150), &w, &h)) {
        for (id = 0; id < 12; ++id)
            if (w == crops[id][0] && h == crops[id][1]) break;
        if (id < 12) {
            uint8_t *source = owned + 0x13c0;
            *(uint32_t *)(source + 0x5c) = w;
            *(uint32_t *)(source + 0x60) = h;
            *(void **)(owned + 8) = source;
            add = owned + 8;
        }
    }
    aspect_mpr_native_cammeta(object, add, meta);
    if (id < 12) {
        meta[0] = 1;
        *(uint32_t *)(meta + 4) = w;
        *(uint32_t *)(meta + 8) = h;
        meta[0xc] = (uint8_t)crops[id][2];
        *(uint32_t *)(meta + 0x10) = crops[id][3];
    }
}
