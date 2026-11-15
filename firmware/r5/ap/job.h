#ifndef R5_OWNER_JOB_H
#define R5_OWNER_JOB_H
#include "wire.h"

struct r5j_object { uint64_t words[7]; };
typedef void (*r5j_leaf)(uint32_t mode, uint32_t look, uint8_t *out);

/* Only an AP worker-validated exact job may receive the prepared cookie. */
int r5j_copy(struct r5j_object *copy, const void *original, uint32_t cookie);
/* This is a serializer-local hook; the target field has four initialized
 * bytes, while the original leaf writes just the color byte. */
void r5j_serialize_color(uint32_t mode, uint32_t look, uint8_t out[4], r5j_leaf leaf);
#endif
