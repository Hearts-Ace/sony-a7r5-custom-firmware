#include <stdint.h>
extern int r5ss_snapshot_inbound(const uint8_t *,uint32_t);
extern void r5sound_inbound(const uint8_t *,uint32_t);
extern int r5_filter_inbound(const uint8_t *,uint32_t);
int r5_filter_dispatch_inbound(const uint8_t *p,uint32_t source){
 if(r5ss_snapshot_inbound(p,source))return 1;
 r5sound_inbound(p,source);return r5_filter_inbound(p,source);
}
