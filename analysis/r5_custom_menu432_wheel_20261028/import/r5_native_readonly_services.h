#ifndef R5_NATIVE_READONLY_SERVICES_H
#define R5_NATIVE_READONLY_SERVICES_H
#include <stddef.h>
#include <stdint.h>
/* Explicit worker-only native bindings, no startup hooks or ambient scratch.
 * Mount acceptance is a snapshot, not a lease or guarantee storage is writable.
 * Clock symbol resolution may lock/block; no wall-time bound is claimed. */
int r5_native_lut_mountinfo_read(uint8_t *scratch,size_t capacity);
int r5_native_monotonic_ms(uint64_t *out);
#endif
