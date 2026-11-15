#ifndef OD_CONTEXT_H
#define OD_CONTEXT_H
#include "filter_value.h"
struct od_context {struct od_value value; uint32_t packed_grid[8][405];};
_Static_assert(sizeof(struct od_context)==15352,"one prepared CP context");
#include "generation.h"
const uint8_t *od_gamma_acquire(const void *,struct r5g_lease *);
int od_match(const struct od_context *,const uint32_t *,unsigned,unsigned);
void od_cc1(const uint16_t *,const uint16_t *,uint16_t *,const uint32_t *,unsigned);
void od_matrix(uint16_t *,uint32_t,const uint32_t *,uint32_t);
int od_available(const uint32_t *,unsigned);
#endif
