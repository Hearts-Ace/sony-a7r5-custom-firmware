/* Independent configuration423. Base/profile retain their original meaning;
 * all custom stages acquire one immutable (bank, selected) view. */
#include "r5_boot_bank.h"
#include "native_gamma.h"
#include "r5_grid_diagnostics.h"
#include "r5_grid422.h"
#include "r5_custom_filter423.h"
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
static const struct r5_boot_value *selected_mode(const uint32_t *w,unsigned actual,unsigned snapshot,const struct r5_filter423_view *view){
 const uint8_t *state;const struct r5_boot_bank *b;int n;unsigned selected;
 if(!w||!w[0]||!w[1]||!view||!(selected=view->selected)||selected>12)return 0;
 b=(const void *)(uintptr_t)view->bank;
 state=(const uint8_t *)(uintptr_t)w[0];n=ordinal(state[0x2e]);
 if(n<0||state[3]>snapshot||(actual!=profile((unsigned)n,0)&&actual!=profile((unsigned)n,1)))return 0;
 if(actual!=((const uint8_t *)(uintptr_t)w[1])[0x25])return 0;
 if(!b||b->state!=SEALED||b->received_mask!=b->expected_mask||!(b->expected_mask&(1u<<(selected-1))))return 0;
 return &b->value[selected-1];
}
static const struct r5_boot_value *selected(const uint32_t *w,unsigned actual){return selected_mode(w,actual,0,r5_filter423_acquire());}
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
 const uint32_t (*table)[7]=(const void *)0x107e968u;
 const uint32_t (*route)[2]=(const void *)0x107eefcu;
 uint32_t (*off)[7]=(void *)((uintptr_t)b+R5_FILTER423_OFF_TABLE);
 unsigned n,k,j;
 for(n=0;n<51;n++)for(k=0;k<7;k++)off[n][k]=table[n][k];
 for(n=0;n<12;n++){
  unsigned wire=((n<6?0x1f008860u:0x1a594693u)>>((n%6)*5))&31u;
  unsigned a=route[wire][0],v=route[wire][1];
  for(j=0;j<7;j++){off[51+2*n][j]=table[a][j==6?6:0];off[52+2*n][j]=j==6?table[v][6]:0;}
 }
 for(n=0;n<=12;n++){
  struct r5_filter423_view *view=r5_filter423_view(b,n);
  if(n&&!(b->expected_mask&(1u<<(n-1))))continue;
  view->bank=(uint32_t)(uintptr_t)b;view->selected=n;
  if(n){
   struct r5_native_gamma418 *g=r5_filter423_gamma(b,n-1);
   if(r5_native_gamma418_begin(g)||r5_native_gamma423_put(g,(const void *)b->value[n-1].gamma)||r5_native_gamma418_seal(g))return -1;
   view->table=(uint32_t)(uintptr_t)g->table;view->route=(uint32_t)(uintptr_t)g->route;view->normal_route=(uint32_t)(uintptr_t)g->normal_route;
  }else{view->table=(uint32_t)(uintptr_t)off;view->route=0x107eefcu;view->normal_route=0xdcc514u;}
  view->ready=R5_FILTER423_MAGIC;
 }
 r5_grid422_prepare(b);
 __atomic_store_n(&b->state,SEALED,__ATOMIC_RELEASE);return 0;
}
static volatile struct r5_grid_diag *diag(void){
 const struct r5_filter423_view *v=r5_filter423_acquire();return v?(void *)(uintptr_t)(v->bank+52252u):0;
}
void r5_grid420_uploaded(const uint8_t *s,unsigned enabled,uint32_t bank){
 volatile struct r5_grid_diag *d=diag();unsigned i;
 if(!d||!s||!enabled||!bank)return;
 for(i=0;i<4;i++)if(d->bank_pointer[i]==bank&&d->bank_slot[i]){
  if(enabled==2){d->copy_mask|=1u<<(d->bank_slot[i]-1);d->copy_calls++;}
  else{d->upload_mask|=1u<<(d->bank_slot[i]-1);d->upload_calls++;}break;
 }
}

/* The native builder's audited type1/transform2, root36=0 format. Publish all
 * level variants before the common ready/release; retired generations stay live.
 * Level1..7 use signed arithmetic shift; 0 and >=8 use the full eighth class. */
void r5_grid422_prepare(struct r5_boot_bank *b) {
 struct r5_grid422 *g=(void *)((uintptr_t)b+R5_GRID422_OFFSET);
 const uint16_t *order=(const void *)0xe8c1d8u;unsigned n,k,i,c;
 for(n=0;n<12;n++)if(b->expected_mask&(1u<<n))
  for(k=0;k<8;k++)for(i=0;i<405;i++) {
   uint32_t packed=0;
   for(c=0;c<3;c++) {
    int v=b->value[n].grid[c][i];if(k<7)v=v*(int)(k+1)>>3;
    packed|=((uint32_t)v&127u)<<(22u-10u*c);
   }
   g->packed[n][k][order[i]]=packed;
  }
 g->mask=b->expected_mask;
 __atomic_store_n(&g->ready,R5_GRID422_MAGIC,__ATOMIC_RELEASE);
}

/* Native fallback snapshots belong to the generation captured before the
 * controller. No live raw pointer survives this call. An unexposed entry may
 * return to FREE after a hit; published packed data never changes or retires.
 * At most31 entries commit, preserving capacity for a repeated-hit snapshot.
 * Concurrent contention never waits and reports an explicit resource error. */

const uint32_t *r5_grid422_restore(struct r5_boot_bank *b,const uint8_t *root,const uint8_t *s) {
 struct r5_grid422 *g=(void *)((uintptr_t)b+R5_GRID422_OFFSET);
 struct r5_grid422_restore_entry *e=0,*q;
 const uint8_t *raw=(const void *)(uintptr_t)*(const uint32_t *)(const void *)(s+0x184);
 unsigned i,j,n=0,kind=s[0x188],transform=s[0x189],level=root[0x2f],key,canonical;
 volatile struct r5_grid_diag *d=(void *)((uintptr_t)b+52252u);
 if(__atomic_load_n(&g->ready,__ATOMIC_ACQUIRE)!=R5_GRID422_MAGIC||kind>2||transform>2||root[0x36]){d->last_reason=6;return 0;}
 if(raw)n=kind==1?1215:162;
 /* The native fast path has a real level-0 distinction for the otherwise
  * unusual kind-0/non-null source. Preserve that class; all levels >=8 share
  * the audited full-strength builder class. */
 canonical=level>7?8:level;
 key=(raw?0x1000000u:0)|(kind<<16)|(transform<<8)|canonical;
 for(i=0;i<R5_GRID422_RESTORE_ENTRIES;i++) {
  uint32_t free=0;
  if(__atomic_compare_exchange_n(&g->restore[i].ready,&free,1,0,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED)){e=&g->restore[i];break;}
 }
 if(!e)goto failed;
 e->key=key;for(j=0;j<n;j++)e->raw[j]=raw[j];
 for(i=0;i<R5_GRID422_RESTORE_ENTRIES;i++) {
  q=&g->restore[i];
  if(__atomic_load_n(&q->ready,__ATOMIC_ACQUIRE)!=2||q->key!=key)continue;
  for(j=0;j<n&&e->raw[j]==q->raw[j];j++){}
  if(j==n){__atomic_store_n(&e->ready,0,__ATOMIC_RELEASE);d->last_reason=0;return q->packed;}
 }
 if(__atomic_fetch_add(&g->restore_used,1,__ATOMIC_ACQ_REL)>=R5_GRID422_RESTORE_LIMIT){
  __atomic_fetch_sub(&g->restore_used,1,__ATOMIC_RELEASE);
  __atomic_store_n(&e->ready,0,__ATOMIC_RELEASE);goto failed;
 }
 {
  /* Audited native read-set: root3/2f/36, env6, state184/188/189,
   * meta+b; writes only direct work28..34 and work5c packed[405].
   * The biased state address is formed as an integer, never C pointer
   * arithmetic outside the local object; actual native accesses land in it. */
  uint8_t r[55],env[7],meta[12];
  struct {uint32_t raw;uint8_t kind,transform;} fields;
  uint32_t w[2],out[5];
  r[3]=0;r[0x2f]=(uint8_t)canonical;r[0x36]=0;env[6]=1;meta[11]=3;
  fields.raw=raw?(uint32_t)(uintptr_t)e->raw:0;fields.kind=kind;fields.transform=transform;
  w[0]=(uint32_t)(uintptr_t)r;w[1]=(uint32_t)(uintptr_t)env;
  out[2]=(uint32_t)((uintptr_t)&fields-0x184u);out[3]=(uint32_t)(uintptr_t)e->work;out[4]=(uint32_t)(uintptr_t)meta;
  ((void (*)(const uint32_t *,const uint32_t *))0x231655u)(w,out);
 }
 __atomic_store_n(&e->ready,2,__ATOMIC_RELEASE);d->last_reason=0;return e->packed;
failed:
 d->last_reason=5;return 0;
}

/* This call-site wrapper owns a source snapshot across the original controller.
 * It never indexes a fourth native bank, modifies live direct/index, allocates,
 * or looks up STATE again after original controller returns. Shared color
 * selection still rejects root3!=0; only this audited grid handoff accepts 0/1. */
void r5_grid422_controller(const uint32_t *w,const uint32_t *out) {
 const uint8_t *root=(const void *)(uintptr_t)w[0],*env=(const void *)(uintptr_t)w[1];
 const struct r5_boot_value *v=0;const int8_t *source=0;
 const struct r5_boot_bank *b=0;const struct r5_filter423_view *view=0;
 unsigned n=0,level=root[0x2f],index;uint8_t *s=(void *)(uintptr_t)out[2];
 volatile struct r5_grid_diag *d;
 unsigned route=root[3]<=1;
 if(route){view=r5_filter423_acquire();if(view)b=(const void *)(uintptr_t)view->bank;if(!root[0x36])v=selected_mode(w,env[0x25],1,view);if(v){source=(const int8_t *)v->grid;n=view->selected-1;}}
 ((void (*)(const uint32_t *,const uint32_t *))0x230da9u)(w,out);
 index=((const uint8_t *)(uintptr_t)out[4])[0xb];
 /* Preserve every old builder-admitted destination. Its direct selector is
  * exactly env6==1; all other values use the three native array banks.
  * The one added route is the proved ordinary non-direct index3 context. */
 if(!route||!b||index>3||(index==3&&env[6]!=1&&
    !(root[1]==1&&env[0xc]==6&&!env[6])))return;
 d=(void *)((uintptr_t)b+52252u);
 if(source) {
  const struct r5_grid422 *g;
  g=(const void *)((uintptr_t)b+R5_GRID422_OFFSET);
  if(__atomic_load_n(&g->ready,__ATOMIC_ACQUIRE)!=R5_GRID422_MAGIC||!(g->mask&(1u<<n))){d->last_reason=6;goto disabled;}
  {
   *(uint32_t *)(void *)(s+0x20)=(uint32_t)(uintptr_t)g->packed[n][level>=1&&level<=7?level-1:7];
   s[0x24]=1;s[0x18]=root[0x2c4]?0:1;s[0x19]=32;
   d->bank_pointer[index]=*(uint32_t *)(void *)(s+0x20);d->bank_slot[index]=n+1;
   d->selected_mask|=1u<<n;d->built_mask|=1u<<n;d->last_reason=0;d->last_slot=n+1;
   goto snapshot;
  }
 } else {
  /* Restore a freshly built original table even when its value is zero.
   * Native enable/strength remain policy-owned; a missing/clear payload is
   * not permission to keep a prior custom hardware table with submit0. */
  const uint32_t *packed=r5_grid422_restore((struct r5_boot_bank *)(uintptr_t)b,root,s);
  *(uint32_t *)(void *)(s+0x20)=(uint32_t)(uintptr_t)packed;s[0x24]=packed?1:0;
  d->bank_pointer[index]=0;d->bank_slot[index]=0;d->last_slot=0;
  if(!packed)s[0x18]=0;
  goto snapshot;
 }
disabled:
 /* Explicit off or unsupported source: transmit a disabled stage so a
  * previous FL2 table is never merely left enabled with no new submit. */
 d->bank_pointer[index]=0;d->bank_slot[index]=0;d->last_slot=0;
 s[0x18]=0;*(uint32_t *)(void *)(s+0x20)=0;s[0x24]=0;
snapshot:
 /* Original root3 snapshot was copied by the native controller before our
  * handoff. Synchronize exactly the fields this wrapper changed, preserving
  * every other native snapshot byte and all later packet policy gates. */
 if(root[3]) {
  uint8_t *saved=(void *)(uintptr_t)out[1];
  *(uint32_t *)(void *)(saved+0x4c)=*(const uint32_t *)(const void *)(s+0x18);
  *(uint32_t *)(void *)(saved+0x54)=*(const uint32_t *)(const void *)(s+0x20);
  saved[0x58]=s[0x24];
 }
}
