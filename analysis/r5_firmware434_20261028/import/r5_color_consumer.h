#ifndef R5_COLOR_CONSUMER_H
#define R5_COLOR_CONSUMER_H
#include "r5_boot_bank.h"
/* CP-only native adapter. One owned carrier spans snapshot and its synchronous
 * dispatch; it is never retained by an asynchronous Gamma request. */
struct r5_color_meta {
    uint32_t sequence, model, marker, base, valid, token;
};
struct r5_color_carrier {
    uint32_t native_wrapper[8];
    uint32_t cookie, self, model, sequence, marker, base, token, profile;
};
void r5_color_capture_copy(void *, const void *, uint32_t);
void r5_color_source_copy(void *, const void *, uint32_t);
void r5_color_source_complete(void *, const void *, uint32_t);
uint32_t r5_color_snapshot_dispatch(void *, const uint32_t *, void *, const uint32_t *, void *);
void r5_color_cc1(uint16_t *, uint32_t, const struct r5_color_carrier *);
void r5_color_block13(uint16_t *, uint32_t, const struct r5_color_carrier *, uint32_t);
#endif
