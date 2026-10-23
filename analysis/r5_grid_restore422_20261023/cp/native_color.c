/* Native ordinal overwrite prototype. No slot marker, Q table or owner stack.
 * One immutable bank shared by all requests, keyed by original native base.
 * Gamma publication is the common release/acquire gate for all three groups.
 */
#include "r5_boot_bank.h"
#include "native_gamma.h"
#include "r5_grid_diagnostics.h"
#include "r5_grid422.h"
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
static const struct r5_boot_bank *acquired(void){
 const struct r5_boot_bank *b;const struct r5_native_gamma418 *g;
 if(STATE[1]!=28768)return 0;
 b=(const void *)(uintptr_t)__atomic_load_n(&STATE[0],__ATOMIC_ACQUIRE);
 if(!b)return 0;g=(const void *)((uintptr_t)b+28768u);
 if(__atomic_load_n(&g->ready,__ATOMIC_ACQUIRE)!=0x4186a11u)return 0;
 return b;
}
static const struct r5_boot_value *selected_mode(const uint32_t *w,unsigned actual,unsigned snapshot,const struct r5_boot_bank *b){
 const uint8_t *state;int n;
 /* One acquired generation per lookup. Retired generations remain alive. */
 if(!w||!w[0]||!w[1]||!b)return 0;
 state=(const uint8_t *)(uintptr_t)w[0];n=ordinal(state[0x2e]);
 if(n<0||state[3]>snapshot||(actual!=profile((unsigned)n,0)&&actual!=profile((unsigned)n,1)))return 0;
 if(actual!=((const uint8_t *)(uintptr_t)w[1])[0x25])return 0;
 if(b->state!=SEALED||b->received_mask!=b->expected_mask||!(b->expected_mask&(1u<<n)))return 0;
 return &b->value[n];
}
static const struct r5_boot_value *selected(const uint32_t *w,unsigned actual){return selected_mode(w,actual,0,acquired());}
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
 unsigned i;struct r5_native_gamma418 *g=(void *)((uintptr_t)b+28768u);
 if(r5_native_gamma418_begin(g))return -1;
 for(i=0;i<12;i++)if(b->expected_mask&(1u<<i))
  if(r5_native_gamma418_put(g,i+1,(const uint32_t *)(const void *)b->value[i].gamma))return -1;
 r5_grid422_prepare(b);
 b->state=SEALED;
 if(r5_native_gamma418_seal(g)){b->state=0;return -1;}
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
 /* Native direct destination is work+0x5c, selected by env+6==1.
  * Index3 is valid only on that route; never index a fourth array bank. */
 if(root[0x36]||root[3]||
    (meta[0xb]>2 && !(meta[0xb]==3 && ((const uint8_t *)(uintptr_t)w[1])[6]==1))){reason=2;goto failed;}
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
 index=((const uint8_t *)(uintptr_t)out[4])[0xb];if(index>3||(index==3&&((const uint8_t *)(uintptr_t)w[1])[6]!=1))return;
 d->bank_pointer[index]=0;d->bank_slot[index]=0;
 n=ordinal(((const uint8_t *)(uintptr_t)w[0])[0x2e]);if(n<0)return;
 v=selected(w,((const uint8_t *)(uintptr_t)w[1])[0x25]);
 index=((const uint8_t *)(uintptr_t)out[4])[0xb];
 if(!v||!v->grid_enabled||index>3||*(const uint32_t *)(uintptr_t)(out[2]+0x184)!=(uintptr_t)v->grid)return;
 d->bank_pointer[index]=((const uint8_t *)(uintptr_t)w[1])[6]==1?out[3]+0x5cu:*(const uint32_t *)(uintptr_t)(out[3]+0x6b0)+index*1620u;
 d->bank_slot[index]=(unsigned)n+1;d->built_mask|=1u<<n;d->build_calls++;
}
void r5_grid420_uploaded(const uint8_t *s,unsigned enabled,uint32_t bank){
 volatile struct r5_grid_diag *d=diag();unsigned i;
 if(!d||!s||!enabled||!bank)return;
 for(i=0;i<4;i++)if(d->bank_pointer[i]==bank&&d->bank_slot[i]){
  if(enabled==2){d->copy_mask|=1u<<(d->bank_slot[i]-1);d->copy_calls++;}
  else{d->upload_mask|=1u<<(d->bank_slot[i]-1);d->upload_calls++;}break;
 }
}

/* Admission for controller repairs: same live selected table, valid destination.
 * No changes for original tables, absent payload, foreign modes or disabled grids. */
int r5_grid421_current(const uint32_t *w,const uint32_t *out) {
 const int8_t *p=r5_native419_grid(w,out);unsigned direct;
 if(!p||*(const uint32_t *)(uintptr_t)(out[2]+0x184)!=(uintptr_t)p)return 0;
 direct=((const uint8_t *)(uintptr_t)w[1])[6];
 return direct==1||(direct==0&&*(const uint32_t *)(uintptr_t)(out[3]+0x6b0));
}

int r5_grid421_retry_ready(const uint32_t *w,const uint32_t *out) {
 volatile struct r5_grid_diag *d=diag();int n;uint32_t table;unsigned index;
 if(!r5_grid421_current(w,out)||!d||((const uint8_t *)(uintptr_t)w[1])[6])return 0;
 n=ordinal(((const uint8_t *)(uintptr_t)w[0])[0x2e]);
 index=((const uint8_t *)(uintptr_t)out[4])[0xb];if(n<0||index>2)return 0;
 table=*(const uint32_t *)(uintptr_t)(out[3]+0x6b0)+index*1620u;
 /* Native cache keys do not include our late-arriving table pointer. Build
  * once if this exact output bank has never held this slot in this epoch. */
 if(d->bank_pointer[index]!=table||d->bank_slot[index]!=(unsigned)n+1)
  ((void (*)(const uint32_t *,const uint32_t *))0x231655u)(w,out);
 return d->bank_pointer[index]==table&&d->bank_slot[index]==(unsigned)n+1;
}

/* The native builder's audited type1/transform2, root36=0 format. Publish all
 * level variants before the common ready/release; retired generations stay live.
 * Level1..7 use signed arithmetic shift; 0 and >=8 use the full eighth class. */
void r5_grid422_prepare(struct r5_boot_bank *b) {
 struct r5_grid422 *g=(void *)((uintptr_t)b+R5_GRID422_OFFSET);
 const uint16_t *order=(const void *)0xe8c1d8u;unsigned n,k,i,c;
 for(n=0;n<12;n++)if((b->expected_mask&(1u<<n))&&b->value[n].grid_enabled)
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
extern void r5_grid420_builder_original(const uint32_t *,const uint32_t *);
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
  r5_grid420_builder_original(w,out);
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
 const struct r5_boot_bank *b=0;
 unsigned n=0,level=root[0x2f],index;uint8_t *s=(void *)(uintptr_t)out[2];
 volatile struct r5_grid_diag *d;
 unsigned route=root[3]<=1;
 if(route){b=acquired();if(!root[0x36])v=selected_mode(w,env[0x25],1,b);if(v){source=(const int8_t *)v->grid;n=(unsigned)ordinal(root[0x2e]);}}
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
  if(v->grid_enabled) {
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
 d->last_reason=4;
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
