#ifndef R5_FILTER_STORE_H
#define R5_FILTER_STORE_H
#include "r5_filter_file.h"
/* Each operation creates and closes its own anchored eMMC directory. A worker
 * serializes these operations with boot import and selection-sidecar writes. */
int r5_filter_store_available(void);
int r5_filter_store_index(struct r5f_index *);
/* Validated whole-package replacement: stage, fsync, byte-for-byte reread,
 * rename, directory fsync. No running CP state is changed by this operation. */
int r5_filter_store_publish(const uint8_t *,size_t,struct r5f_index *);
int r5_filter_store_read(const struct r5f_index *,unsigned,uint8_t [R5F_COMPACT]);
int r5_filter_store_selection(unsigned *,int write);
#endif
