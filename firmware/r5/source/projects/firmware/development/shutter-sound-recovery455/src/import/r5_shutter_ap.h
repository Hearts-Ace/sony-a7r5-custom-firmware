#ifndef R5_SHUTTER_AP_ADAPTER_H
#define R5_SHUTTER_AP_ADAPTER_H
#include "r5_shutter.h"

typedef struct {
 uint32_t silent_raw,signals_raw,volume_raw,audible;
} r5ss_native_policy;

/* Worker-only original silent/global audio policy. volume_raw stays zero;
 * the unsupported native827 never controls custom shutter loudness. */
int r5ss_native_gate(r5ss_native_policy *out);

/* Bounded observer. Returns 1 for the native exposure notification, 0 for
 * every other packet; leaves out unchanged on rejection. Caller must always
 * continue original inbound dispatch, irrespective of this return value.
 * Only the original class4/type1001/28-byte exposure contract is admitted;
 * class11 can be consumed before native dispatch. Sequence/member/ordinal are
 * retained for the bounded M4-style duplicate filter; no packet is consumed
 * by this observer and the original dispatch continues unchanged. */
int r5ss_parse_exposure(const void *packet,size_t bytes,uint32_t source,
                       r5ss_exposure *out);

#endif
