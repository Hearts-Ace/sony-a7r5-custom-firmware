#include <stdint.h>
#include "crop_core.h"
extern uint32_t aspect_task_id(uintptr_t);
static uint32_t little32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8)
        | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void put_little32(uint8_t *p, uint32_t value)
{
    for (uint32_t i = 0; i < 4; ++i) p[i] = (uint8_t)(value >> (i * 8));
}

/* 原生 extra-IFD：DefaultCrop 保留完整有效传感器区域；SonyCrop 表达
 * 菜单选择的可撤销裁切。RAW 原始像素、默认有效区域和共享 YC 均不改。
 * 0x48a00a 唯一调用点传入本张照片冻结的 task，不能读取当前菜单选择。
 * 全幅无损压缩 M（mode=1, size=1）与无损压缩 S（mode=2）经 AVCAM 0x2044dc
 * 显影下采样为 6240×4160 / 4752×3168，此处直接按目标档位写入 SonyCrop 与 EMB。
 */
uint32_t aspect_raw_exif_build(void *packet, uint8_t *header, uintptr_t task)
{
    uint32_t result = ((uint32_t (*)(void *, void *, uintptr_t))0xade83du)(packet, header, task);
    uint32_t id = aspect_task_id(task);
    if (!id) return result;
    const uint16_t *size = (const uint16_t *)(task + 0x234);
    uint32_t raw_mode = ((uint32_t (*)(uintptr_t))0xae96cbu)(task);
    uint32_t raw_size = ((uint32_t (*)(uintptr_t))0xae972fu)(task);
    uint16_t base_w = size[0], base_h = size[1];
    if (raw_mode == 1 && raw_size == 1) {
        base_w = 6240;
        base_h = 4160;
    } else if (raw_mode == 2) {
        base_w = 4752;
        base_h = 3168;
    }
    if (base_w > size[0] || base_h > size[1]) return result;
    aspect_geometry source = {(uint16_t)((base_w + 127u) & ~127u),
        base_h, base_w, base_h, 0, 0};
    aspect_geometry crop;
    if (!aspect_crop_geometry(&source, id, 0, &crop)) return result;
    uint32_t ox = base_w == size[0] ? crop.x : (uint32_t)(size[0] - crop.width) / 2u;
    uint32_t oy = base_h == size[1] ? crop.y : (uint32_t)(size[1] - crop.height) / 2u;
    put_little32(header + 0x1421c, little32(header + 0x1420c) + ox);
    put_little32(header + 0x14220, little32(header + 0x14210) + oy);
    put_little32(header + 0x14224, crop.width);
    put_little32(header + 0x14228, crop.height);
    /* 独立 RAW header 的 EMB 声明；对应 JPEG 预览，不是 Bayer 尺寸。 */
    put_little32(header + 0x14a2c, crop.width);
    put_little32(header + 0x14a30, crop.height);
    return result;
}
