#include "r5_shutter_ap.h"

/* Keep the original silent-mode gate here. The audio-signals switch is read
 * by the owned backend authorize step so a global mute consumes the pending
 * exposure without turning an expected E002 into a backend fault. */
extern uint32_t r5ss_native_silent_get(void);
int r5ss_native_gate(r5ss_native_policy *out){
 if(!out)return R5SS_INVALID;
 uint32_t silent=r5ss_native_silent_get();
 *out=(r5ss_native_policy){silent,0,0,silent==1u};
 return silent<=1u?R5SS_OK:R5SS_NATIVE;
}

static uint32_t half(const uint8_t *p){
 return (uint32_t)p[0]|((uint32_t)p[1]<<8);
}
static uint32_t word(const uint8_t *p){
 return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
static uint32_t exposure_serial;
int r5ss_parse_exposure(const void *packet,size_t bytes,uint32_t source,
                       r5ss_exposure *out){
 const uint8_t *p=(const uint8_t *)packet;
 if(!p||!out||bytes<4u||
    (source!=0x90030001u&&source!=0x90040193u&&
     source!=0x8102021fu&&source!=0x90bf0274u))return 0;
 /* R5's native exposure producer emits the same 28-byte contract as M4:
  * class4/type1001, marker F000, then sequence/member/ordinal.  Retaining
  * those fields lets the bounded scheduler suppress duplicate delivery
  * instead of assigning a fresh local id to every copy of one exposure. */
 if(bytes!=28u||p[0]!=4u||half(p+2)!=0x1001u||word(p+8)!=0xf000u)return 0;
 *out=(r5ss_exposure){word(p+4),word(p+12),word(p+16)};
 return 1;
}

