#ifndef R5_FILTER_RUNTIME_H
#define R5_FILTER_RUNTIME_H
#include "r5_filter_file.h"
unsigned r5_filter_selected(void);
unsigned r5_filter_pending(void);
int r5_filter_request(unsigned);
unsigned r5_filter_command_state(void);
unsigned r5_filter_command_sequence(void);
void r5_filter_refresh_construct425(void *,const void *);
void r5_filter_refresh_execute425(void *);
void r5_filter_service(void);
void r5_filter_serialize_color(uint32_t,uint32_t,uint8_t [4]);
int r5_filter_inbound(const uint8_t *,uint32_t);
/* Exactly one immutable catalog is published during this AP lifetime. Resume
 * verifies its identity, then marks selection dirty for a fresh CP transaction. */
int r5_filter_catalog_ready(const struct r5f_index *,unsigned,unsigned);
const char *r5_filter_short_name(unsigned);
const char *r5_filter_full_name(unsigned);
uint32_t r5_filter_available_mask(void);
#endif
