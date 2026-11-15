#include "context.h"
#include "owners.h"
/* Descriptor Look byte to native still/movie profile. Zero rows are
 * unrecognized; ST is distinguishable by its nonzero movie profile. */
static const uint8_t look_profile[][2]={
 [0]={0,21},[1]={1,22},[2]={2,23},[3]={6,27},[5]={53,53},
 [13]={53,53},[15]={41,45},[16]={42,46},[17]={43,47},
 [18]={44,48},[19]={54,56},[20]={55,57},
};
int od_match(const struct od_context *c,const uint32_t *w,unsigned actual,unsigned snapshot){
 if(!c||!w||!w[0]||!w[1])return 0;
 const uint8_t *s=(const void *)(uintptr_t)w[0];
 unsigned look=s[0x2e];
 if(look>=sizeof(look_profile)/sizeof(look_profile[0])||s[3]>snapshot)return 0;
 const uint8_t *p=look_profile[look];
 return p[1]&&(actual==p[0]||actual==p[1])&&actual==((const uint8_t *)(uintptr_t)w[1])[0x25];
}
int od_available(const uint32_t *w,unsigned a){struct r5g_lease lease;const struct od_context *c=od_work_pin(w,&lease);int ok=od_match(c,w,a,0);od_work_drop(&lease);return ok;}
void od_cc1(const uint16_t *original,const uint16_t *cal,uint16_t *out,const uint32_t *w,unsigned a){
 struct r5g_lease lease;const struct od_context *c=od_work_pin(w,&lease);const uint16_t *v=original;unsigned i;
 if((uintptr_t)original!=0x16b1e34u&&(uintptr_t)original!=0x16b1e64u&&od_match(c,w,a,0))v=(const void *)c->value.cc1;
 for(i=0;i<8;i++){uint16_t b=(uint16_t)(cal[i]+v[i]);out[i]=b;out[8+i]=(uint16_t)((int16_t)b+v[8+i]);out[16+i]=(uint16_t)((int16_t)b+v[16+i]);}
 od_work_drop(&lease);
}
void od_matrix(uint16_t *out,uint32_t hue,const uint32_t *w,uint32_t a){
 struct r5g_lease lease;const struct od_context *c=od_work_pin(w,&lease);const uint16_t *cal;unsigned e;
 if(!od_match(c,w,a,0)){od_work_drop(&lease);((void(*)(uint16_t *,uint32_t,const uint32_t *,uint32_t))0x71e41fu)(out,hue,w,a);return;}
 cal=(const void *)(uintptr_t)(w[1]+0x1a0u);if(hue>15)hue=0;
 for(e=0;e<3;e++){const uint16_t *k=(const void *)(c->value.block13+e*192+hue*12);
 out[0]=(uint16_t)(cal[0]+k[0]+k[1]);out[1]=(uint16_t)-k[0];out[2]=(uint16_t)-k[1];out[3]=(uint16_t)-k[2];out[4]=(uint16_t)(cal[1]+k[2]+k[3]);out[5]=(uint16_t)-k[3];out[6]=(uint16_t)-k[4];out[7]=(uint16_t)-k[5];out[8]=(uint16_t)(cal[2]+k[4]+k[5]);out+=9;}
 od_work_drop(&lease);
}
/* Native metadata stays in the original table. This span is read
 * synchronously by the original inner builder under the returned lease.
 * aa7f80 advances past the container header; aa8212 stores the native
 * color owner field at +0xc in the resulting Gamma input. */
const uint8_t *od_gamma_acquire(const void *input,struct r5g_lease *lease){
 const struct od_context *c=od_field_pin((uintptr_t)input+0xcu,lease);
 return c?c->value.gamma:0;
}
