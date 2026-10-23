#ifndef R5_NATIVE_LUT_DIRECTORY_H
#define R5_NATIVE_LUT_DIRECTORY_H
#include "r5_lut_directory.h"
/* Resolve once on the caller-owned worker, before acquisition. No global cache.
 * Failure leaves output unchanged; no file operation or fallback. The returned
 * API does not prove a writable mount or native resolver lifecycle safety. */
int r5_native_lut_directory_api_init(struct r5_lut_directory_api *);
#endif
