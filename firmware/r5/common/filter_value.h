#ifndef FILTER_VALUE_H
#define FILTER_VALUE_H
#include <stdint.h>
struct od_value {
 char name[32];
 uint8_t cc1[48], block13[576], gamma[516];
 uint32_t grid_enabled;
 int8_t grid[3][405];
 uint8_t padding;
};
_Static_assert(sizeof(struct od_value)==2392,"single filter wire size");
#endif
