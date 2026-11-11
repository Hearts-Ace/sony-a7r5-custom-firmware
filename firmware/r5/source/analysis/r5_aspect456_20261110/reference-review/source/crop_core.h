#ifndef ASPECT_CROP_CORE_H
#define ASPECT_CROP_CORE_H
#include <stdint.h>
typedef struct {
    uint16_t canvas_w, canvas_h, width, height, x, y;
} aspect_geometry;
#define ASPECT_GEOMETRY_AUX 0x100u
uint32_t aspect_crop_geometry(const aspect_geometry *source, uint32_t id,
                              uint32_t physical_base_low, aspect_geometry *out);
#endif
