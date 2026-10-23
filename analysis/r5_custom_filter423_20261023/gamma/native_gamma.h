#ifndef R5_NATIVE_GAMMA418_H
#define R5_NATIVE_GAMMA418_H
#include <stdint.h>
/* Caller-owned zeroed BSS lifetime. Native references use getter_gates which
 * return ORIGINAL tables until ready's final release-store. Once published,
 * this context is immutable and must never be reinitialized or freed. */
struct r5_native_gamma418 {
 uint32_t table[75][7];
 uint32_t route[22][2];
 /* ST/NT and BW/SE have exactly the same original three records. A single
  * selected curve makes those pairs identical, so only ten groups are needed. */
 uint8_t record[10][3][576];
 uint32_t ready,mask;
 uint32_t normal_route[58][2];
};
/* 1-based actual menu order: ST,PT,NT,VV,VV2,FL,FL2,FL3,IN,SH,BW,SE. */
int r5_native_gamma418_begin(struct r5_native_gamma418 *);
int r5_native_gamma418_put(struct r5_native_gamma418 *,uint32_t one_based,const uint32_t points[129]);
int r5_native_gamma423_put(struct r5_native_gamma418 *,const uint32_t points[129]);
int r5_native_gamma418_seal(struct r5_native_gamma418 *);
_Static_assert(sizeof(struct r5_native_gamma418)==20028u,"Gamma423 shared-record ABI");
#endif
