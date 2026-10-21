#ifndef R5_PREVIEW_H
#define R5_PREVIEW_H
#include "r5_color_consumer.h"
/* Independent live ISP bank: no request-Q identity is manufactured. */
int r5_preview_ready(void);
void **r5_preview_aa_registry(void);
void r5_preview_aa_enter(void);
void r5_preview_aa_leave(void);
int r5_preview_aa_idle(void);
void r5_preview_snapshot(const struct r5_color_carrier *,void *,uint32_t valid,const void *out);
int r5_preview_eligible(const struct r5_color_carrier *,uint32_t mask);
uint32_t r5_preview_owner(void *,void *);
void r5_preview_stage_before(const uint32_t *,void *);
void r5_preview_stage_after(void);
void r5_preview_stage_shim(void);
uint32_t r5_preview_build(uint32_t,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t);
void r5_preview_gamma_set(void *);
void r5_preview_publish(void *,void *);
uint32_t r5_preview_flip(void);
void r5_preview_complete(void *);
#endif
