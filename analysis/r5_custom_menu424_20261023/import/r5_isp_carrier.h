#ifndef R5_ISP_CARRIER_H
#define R5_ISP_CARRIER_H
#include <stdint.h>
struct isp_carrier {uint32_t self,epoch,descriptor,stage,sequence,marker,base,token,valid,build_stage;};
struct isp_meta {uint32_t sequence,model,marker,base,valid,token;};
uint32_t r5_isp_owner(void *,void *);
void r5_isp_stage_before(const uint32_t *,void *);
void r5_isp_stage_after(void);
uint32_t r5_isp_identity(uint32_t stage);
uint32_t r5_isp_custom_eligible(uint32_t stage);
void r5_isp_stage_shim(void);
#endif
