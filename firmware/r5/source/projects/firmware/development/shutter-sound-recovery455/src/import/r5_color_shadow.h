#ifndef R5_COLOR_SHADOW_H
#define R5_COLOR_SHADOW_H
#include "r5_color_consumer.h"
/* Owned scratch only. No pointer into a caller stack survives capture. */
struct r5_color_shadow {
 uint32_t claimed,component;
 struct r5_color_carrier carrier;
 uint32_t descriptor[10],scalar[2];
 uint8_t state[0x384],component_copy[0x7a0],arena[0xb000];
 uint8_t packed[0x400],matrix[192],cc1[16],cc1_hardware[16];
};
struct r5_color_shadow *r5_color_shadow_acquire(void);
/* Preallocate before acknowledging SEALED, so allocation failure cannot leave
 * a visible custom slot whose consumers can never acquire their scratch. */
int r5_color_shadow_ready(void);
void r5_color_shadow_release(struct r5_color_shadow *);
/* Leaves global/real component bytes native. Caller proves route, source and
 * lifetime both before and after; each helper still passes the common gate. */
int r5_color_shadow_prepare(struct r5_color_shadow *,const struct r5_color_carrier *,const uint32_t *selected_descriptor);
/* Internal preview stamp: cache must be its owned 0x400-byte snapshot. */
int r5_color_shadow_prepare_owned(struct r5_color_shadow *,const struct r5_color_carrier *,const uint32_t *,const uint8_t *cache);
int r5_color_shadow_render(struct r5_color_shadow *);
#endif
