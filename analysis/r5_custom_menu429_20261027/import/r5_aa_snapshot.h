#ifndef R5_AA_SNAPSHOT_H
#define R5_AA_SNAPSHOT_H
#include <stdint.h>
/* Registry lives in the already allocated preview owner, not a new BSS area. */
void **r5_preview_aa_registry(void);
int r5_aa_snapshot_ready(void);
/* Every call counts one reader, including fallback before initialization.
 * Returned table also serves as its non-null release token. */
void *r5_aa_snapshot_table(void);
void r5_preview_aa_enter(void);
void r5_preview_aa_leave(void);
int r5_preview_aa_idle(void);
void r5_aa_snapshot_gamma(void *request,const void *table);
void r5_aa_snapshot_mode2(void *request);
void r5_aa_snapshot_release(const void *table);
#endif
