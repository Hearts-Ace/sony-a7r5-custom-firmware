#include "r5_sound_snapshot_wire.h"
#ifndef R5SS_FILTER_CONSUME_ADDRESS
#error R5SS_FILTER_CONSUME_ADDRESS is required
#endif
typedef int (*r5ss_consume_fn)(const unsigned char *,unsigned);
int r5ss_cp_extended_consume(const unsigned char *p,unsigned source){if(r5ss_cp_snapshot_consume(p,source))return 1;return ((r5ss_consume_fn)R5SS_FILTER_CONSUME_ADDRESS)(p,source);}
