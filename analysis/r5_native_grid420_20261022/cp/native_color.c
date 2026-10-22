/* Native ordinal overwrite prototype. No slot marker, Q table or owner stack.
 * One immutable bank shared by all requests, keyed by original native base.
 * Gamma publication is the common release/acquire gate for all three groups.
 */
#include "r5_boot_bank.h"
#include "native_gamma.h"
#include "r5_grid_diagnostics.h"
#define STATE ((const uint32_t *)0x1a39448u)
#define GAMMA ((struct r5_native_gamma418 *)(uintptr_t)(STATE[0]+28768u))
#define SEALED 0x35424c53u
static int ordinal(unsigned base){
 switch(base){case 0:return 0;case 3:return 1;case 2:return 2;case 1:return 3;
 case 16:return 4;case 15:return 5;case 19:return 6;case 20:return 7;
 case 17:return 8;case 18:return 9;case 5:return 10;case 13:return 11;default:return -1;}
}
static unsigned profile(unsigned one,unsigned movie){
 switch(one){case 0:return movie?21:0;case 1:return movie?27:6;case 2:return movie?23:2;case 3:return movie?22:1;
 case 4:return movie?46:42;case 5:return movie?45:41;case 6:return movie?56:54;case 7:return movie?57:55;
 case 8:return movie?47:43;case 9:return movie?48:44;default:return 53;}
}
static const struct r5_boot_value *selected(const uint32_t *w,unsigned actual){
 const uint8_t *state;const struct r5_boot_bank *b;int n;
 if(!STATE[0]||STATE[1]!=28768||__atomic_load_n(&GAMMA->ready,__ATOMIC_ACQUIRE)!=0x4186a11u||!w||!w[0]||!w[1])return 0;
 state=(const uint8_t *)(uintptr_t)w[0];n=ordinal(state[0x2e]);
 if(n<0||state[3]||(actual!=profile((unsigned)n,0)&&actual!=profile((unsigned)n,1)))return 0;
 if(actual!=((const uint8_t *)(uintptr_t)w[1])[0x25]||STATE[1]!=28768||!STATE[0])return 0;
 b=(const struct r5_boot_bank *)(uintptr_t)STATE[0];
 if(b->state!=SEALED||b->received_mask!=b->expected_mask||!(b->expected_mask&(1u<<n)))return 0;
 return &b->value[n];
}
int r5_native418_available(const uint32_t *w,unsigned actual){return selected(w,actual)!=0;}
const void *r5_native418_cc1(const void *original,const uint32_t *w,unsigned actual){
 const struct r5_boot_value *v;
 if((uintptr_t)original==0x16b1e34u||(uintptr_t)original==0x16b1e64u)return original;
 v=selected(w,actual);return v?v->cc1:original;
}
typedef void (*matrix_fn)(uint16_t *,uint32_t,const uint32_t *,uint32_t);
void r5_native418_matrix(uint16_t *out,uint32_t hue,const uint32_t *w,uint32_t actual){
 const struct r5_boot_value *v=selected(w,actual);const uint16_t *cal;unsigned e;
 if(!v){((matrix_fn)0x71e41fu)(out,hue,w,actual);return;}
 cal=(const uint16_t *)(uintptr_t)(w[1]+0x1a0u);if(hue>15)hue=0;
 for(e=0;e<3;e++){
  const uint16_t *k=(const void *)(v->block13+e*192+hue*12);
  out[0]=(uint16_t)(cal[0]+k[0]+k[1]);out[1]=(uint16_t)-k[0];out[2]=(uint16_t)-k[1];
  out[3]=(uint16_t)-k[2];out[4]=(uint16_t)(cal[1]+k[2]+k[3]);out[5]=(uint16_t)-k[3];
  out[6]=(uint16_t)-k[4];out[7]=(uint16_t)-k[5];out[8]=(uint16_t)(cal[2]+k[4]+k[5]);out+=9;
 }
}
int r5_native418_publish(struct r5_boot_bank *b){
 unsigned i;
 if(r5_native_gamma418_begin(GAMMA))return -1;
 for(i=0;i<12;i++)if(b->expected_mask&(1u<<i))
  if(r5_native_gamma418_put(GAMMA,i+1,(const uint32_t *)(const void *)b->value[i].gamma))return -1;
 b->state=SEALED;
 if(r5_native_gamma418_seal(GAMMA)){b->state=0;return -1;}
 return 0;
}

/* No pixel math is added here. Redirect the original correction controller's
 * table/type/transform and let its existing builder and uploader consume it.
 * The full7-bit grid replaces that stage's original table, not adds to it.
 */
static volatile struct r5_grid_diag *diag(void){return STATE[0]&&STATE[1]==28768?(void *)(uintptr_t)(STATE[0]+52252u):0;}
const int8_t *r5_native419_grid(const uint32_t *w,const uint32_t *out){
 const struct r5_boot_value *v;const uint8_t *root,*meta;volatile struct r5_grid_diag *d=diag();unsigned reason=0;int n=-1;
 if(d)d->select_calls++;
 if(!w||!w[0]||!w[1]||!out||!out[2]||!out[3]||!out[4]){reason=1;goto failed;}
 root=(const void *)(uintptr_t)w[0];meta=(const void *)(uintptr_t)out[4];n=ordinal(root[0x2e]);
 if(root[0x36]||root[3]||meta[0xb]>2){reason=2;goto failed;}
 v=selected(w,((const uint8_t *)(uintptr_t)w[1])[0x25]);
 if(!v){reason=3;goto failed;}
 if(v->grid_enabled!=1){reason=4;goto failed;}
 if(d){d->selected_mask|=1u<<n;d->last_slot=(unsigned)n+1;d->last_reason=0;}
 return (const int8_t *)v->grid;
failed:
 if(d){d->last_reason=reason;d->last_slot=n<0?0:(unsigned)n+1;}
 return 0;
}
void r5_grid420_built(const uint32_t *w,const uint32_t *out){
 volatile struct r5_grid_diag *d=diag();const struct r5_boot_value *v;unsigned index;int n;
 if(!d||!w||!w[0]||!w[1]||!out||!out[2]||!out[3]||!out[4])return;
 index=((const uint8_t *)(uintptr_t)out[4])[0xb];if(index>2)return;
 d->bank_pointer[index]=0;d->bank_slot[index]=0;
 n=ordinal(((const uint8_t *)(uintptr_t)w[0])[0x2e]);if(n<0)return;
 v=selected(w,((const uint8_t *)(uintptr_t)w[1])[0x25]);
 index=((const uint8_t *)(uintptr_t)out[4])[0xb];
 if(!v||!v->grid_enabled||index>2||*(const uint32_t *)(uintptr_t)(out[2]+0x184)!=(uintptr_t)v->grid)return;
 d->bank_pointer[index]=*(const uint32_t *)(uintptr_t)(out[3]+0x6b0)+index*1620u;
 d->bank_slot[index]=(unsigned)n+1;d->built_mask|=1u<<n;d->build_calls++;
}
void r5_grid420_uploaded(const uint8_t *s,unsigned enabled,uint32_t bank){
 volatile struct r5_grid_diag *d=diag();unsigned i;
 if(!d||!s||!enabled||!bank)return;
 for(i=0;i<3;i++)if(d->bank_pointer[i]==bank&&d->bank_slot[i]){
  d->upload_mask|=1u<<(d->bank_slot[i]-1);d->upload_calls++;break;
 }
}
