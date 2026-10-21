#ifndef R5_BOOT_SERVICES_H
#define R5_BOOT_SERVICES_H
#include <stdint.h>
#include "sd_native_persist.h"

/* Explicit binder ABI, based on R5 Linux arm64 libc evidence. No original
 * address or implicit host-OS constants. Worker only; trusted /usr/data parent
 * and serialized directory ownership are prerequisites. Not an SD service. */
struct r5_native_timespec { int64_t seconds,nanoseconds; };
struct r5_boot_service_api {
    int (*clock_gettime)(int,struct r5_native_timespec *);
    int (*mkdir)(const char *,unsigned);
    int (*open)(const char *,int,unsigned);
    int (*fsync)(int);
    int (*close)(int);
    int *(*error_number)(void);
};
enum r5_directory_result { R5_DIRECTORY_READY=0,R5_DIRECTORY_ERROR=1,
    R5_DIRECTORY_UNCERTAIN=2 };
/* Failure leaves *out unchanged. CLOCK_MONOTONIC=1; no polling/timeouts or
 * system-clock substitution. This does not bound blocking native services. */
int r5_boot_monotonic_ms(const struct r5_boot_service_api *,uint64_t *out);
/* Only /usr/data/lut; mode0700; no recursive mkdir and no unlink/retry. Open
 * parent first; mkdir success or EEXIST must be followed by O_DIRECTORY /
 * O_NOFOLLOW open of child. New child requires parent fsync before READY.
 * Errors may leave an empty newly created directory, never remove it. */
int r5_boot_prepare_directory(const struct r5_boot_service_api *);
#endif
