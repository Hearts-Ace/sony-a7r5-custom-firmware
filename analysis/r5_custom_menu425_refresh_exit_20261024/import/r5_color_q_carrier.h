#ifndef R5_COLOR_Q_CARRIER_H
#define R5_COLOR_Q_CARRIER_H
#include "r5_color_consumer.h"
/* Synchronous native Q rebuild only; never keep a stack carrier in Q. */
void r5_color_q_reconstruct(void *,const void *,const void *,const void *,uint32_t);
uint32_t r5_color_q_dispatch(const uint32_t *,void *);
int r5_color_q_eligible(const struct r5_color_carrier *,uint32_t mask);
#endif
