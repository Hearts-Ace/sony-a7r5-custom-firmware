#ifndef R5_LUT_MOUNT_GUARD_H
#define R5_LUT_MOUNT_GUARD_H
#include <stddef.h>
#include <stdint.h>

/* Offline parser for a COMPLETE /proc/self/mountinfo snapshot, supplied by a
 * separately bound worker reader. No mount/mkdir/partition writes. Data <=64K,
 * lines <=4096, <=512 records; missing, ambiguous or truncated snapshots fail.
 * Require exact /usr/data/lut, root/, vfat, /dev/nflasha30, and rw mount+super
 * options without ro. Other source aliases require independent evidence.
 * Caller must prove this mount remains stable across open/publish; this
 * snapshot alone is NOT a lifetime lease or writable-storage guarantee. */
int r5_lut_mountinfo_check(const uint8_t *,size_t);
#endif
