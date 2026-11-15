#ifndef R5_OD_GRID_H
#define R5_OD_GRID_H
#include <stdint.h>
struct od_context;
void od_grid_prepare(struct od_context *);
unsigned od_grid_source(const uint32_t *, const uint32_t *);
void od_grid_snapshot(uint8_t *, const uint8_t *);
void od_grid_packet(uint8_t *, const uint8_t *);
void od_grid_descriptor(uint8_t *, const uint8_t *);
void od_grid_aa(uint32_t, uint32_t, uint32_t, const uint8_t *, uint32_t, uint32_t);
#endif
