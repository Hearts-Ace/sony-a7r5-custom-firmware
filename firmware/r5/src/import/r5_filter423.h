#ifndef R5_FILTER423_H
#define R5_FILTER423_H
#include "sd_native_look.h"
#define R5_FILTER_COMPACT 2392u
/* Exact existing CP compact ABI. Names are UI data; full_name stays AP-only.
 * Return zero on invalid input/overlap, with output untouched. */
int r5_filter_pack_compact(const struct r5_native_look *,uint8_t [R5_FILTER_COMPACT]);
uint32_t r5_filter_compact_set_crc(const struct r5_look_set *);
/* Publish only after this complete set receives its SEAL acknowledgment.
 * Existing name pointers remain immutable through every later publication. */
int r5_filter_names_publish(const struct r5_look_set *);
const char *r5_filter_short_name(unsigned number);
const char *r5_filter_full_name(unsigned number);
uint32_t r5_filter_available_mask(void);
#endif
