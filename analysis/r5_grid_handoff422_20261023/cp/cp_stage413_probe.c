/* Retained immutable parameter generations, published only after full sealing.
 * Original receive task serializes this handler with its resource24 lock.
 * Bank allocation uses the original shared-heap function and its own mutex;
 * that native mutex is not promised nonblocking. No boot/init hook is added.
 */
#include "r5_stage413_probe.h"
#include "r5_look_transfer.h"
#include "r5_grid_diagnostics.h"
#include "r5_grid422.h"
#define FN(a,t) ((t)(uintptr_t)(a))
typedef uint32_t (*size_fn)(const void *);
typedef int (*alloc_fn)(uint32_t,void **,uint32_t,uint32_t);
typedef int (*send_fn)(uint32_t,void *);
typedef int (*free_fn)(uint32_t,void *);
typedef void (*source_fn)(void *,uint32_t);
typedef void *(*bank_alloc_fn)(uint32_t);
#define BANK_BYTES 28768u
#define TX_OFFSET (52252u+sizeof(struct r5_grid_diag))
#define ALLOCATION_BYTES R5_GRID422_ALLOCATION
_Static_assert(TX_OFFSET+24u==52348u,"preserve original transfer offset");
#define MANAGER ((volatile uint32_t *)(uintptr_t)0x1a39450u)
#define STATE ((volatile uint32_t *)(uintptr_t)0x1a39448u)

/* STATE[0]=retained bank pointer; STATE[1]=0 untried,1 attempted failure,
 * or28768 verified. Both words are in an explicit8B BSS/clear extension.
 * Mark before calling the heap, so a failed allocation is never retried.
 */
static __attribute__((noinline)) uint32_t bank_once(void) {
 uintptr_t a;volatile uint8_t *b;unsigned i;
 if(STATE[1])return STATE[1]==BANK_BYTES&&STATE[0]?BANK_BYTES:0;
 STATE[1]=1;
 a=(uintptr_t)FN(0x5ef69cu,bank_alloc_fn)(ALLOCATION_BYTES);
 if(!a||(a&7u)||a>UINT32_MAX-(ALLOCATION_BYTES-1u))return 0;
 STATE[0]=(uint32_t)a;b=(volatile uint8_t *)a;
 b[0]=0x5au;b[ALLOCATION_BYTES-1u]=0xa5u;
 if(b[0]!=0x5au||b[ALLOCATION_BYTES-1u]!=0xa5u)return 0;
 for(i=0;i<ALLOCATION_BYTES;i++)b[i]=0;
 for(i=0;i<ALLOCATION_BYTES;i++)if(b[i])return 0;
 MANAGER[0]=(uint32_t)a;MANAGER[1]=1;STATE[1]=BANK_BYTES;return BANK_BYTES;
}

static uint32_t word(const uint8_t *p,unsigned o) {
 return p[o]|(uint32_t)p[o+1]<<8|(uint32_t)p[o+2]<<16|(uint32_t)p[o+3]<<24;
}
static void put(uint8_t *p,unsigned o,uint32_t v) {
 p[o]=(uint8_t)v;p[o+1]=(uint8_t)(v>>8);
 p[o+2]=(uint8_t)(v>>16);p[o+3]=(uint8_t)(v>>24);
}
static __attribute__((noinline)) uint32_t crc28(const uint8_t *p) {
 uint32_t c=0xffffffffu;unsigned i,j;
 for(i=0;i<28;i++){
  c^=p[i];for(j=0;j<8;j++)c=(c>>1)^(0xedb88320u&-(c&1u));
 }
 return c^0xffffffffu;
}
int r5_cp_stage413_consume(const uint8_t *p,uint32_t source) {
 void *allocation=0;uint8_t *reply;unsigned i;uint32_t bank_result;
 if(source==R5_STAGE413_AP_QUEUE&&p) {
  uint32_t n=FN(0xbaad0du,size_fn)(p);
  if(r5_diag_envelope(p,n)) {
   if(n!=32||p[1]!=1||p[2]!=1||p[3]!=32||!word(p,8)||word(p,12)||word(p,16)||word(p,20)||word(p,24)||word(p,28)!=r5_diag_crc(p,n))return 1;
   if(FN(0x53c221u,alloc_fn)(source,&allocation,R5_DIAG_BYTES,0)||!allocation)return 1;
   reply=allocation;FN(0xbaaaa1u,source_fn)(reply,R5_STAGE413_CP_QUEUE);
   for(i=0;i<R5_DIAG_BYTES;i++)reply[i]=0;
   for(i=0;i<12;i++)reply[i]=p[i];reply[2]=0x81;reply[3]=R5_DIAG_BYTES;
   put(reply,12,0x420);put(reply,16,STATE[1]);
   if(STATE[0]&&STATE[1]==BANK_BYTES) {
    const struct r5_boot_bank *b=(const void *)(uintptr_t)STATE[0];
    const volatile struct r5_grid_diag *d=(const void *)(uintptr_t)(STATE[0]+52252u);
    uint32_t mask=0;put(reply,20,b->state);put(reply,24,b->received_mask);
    for(i=0;i<12;i++)if((b->received_mask&(1u<<i))&&b->value[i].grid_enabled)mask|=1u<<i;
    put(reply,32,mask);
    for(i=0;i<8;i++)put(reply,36+4*i,((const volatile uint32_t *)d)[i]);
    put(reply,68,d->copy_mask);put(reply,72,d->copy_calls);put(reply,76,MANAGER[1]);put(reply,80,r5_transfer_bank_crc(b));
   }
   put(reply,28,r5_diag_crc(reply,R5_DIAG_BYTES));
   if(FN(0x53bb55u,send_fn)(source,reply))(void)FN(0x53c31du,free_fn)(source,reply);
   return 1;
  }
 }
 if(source==R5_STAGE413_AP_QUEUE&&p) {
  uint32_t n=FN(0xbaad0du,size_fn)(p);
  if(r5_transfer_is_envelope(p,n)) {
   uint8_t ack[R5_TRANSFER_ACK];
   struct r5_boot_bank *bank;struct r5_transfer_cp *ctx;
   if(n>R5_TRANSFER_MAX||!STATE[0]||STATE[1]!=BANK_BYTES)return 1;
   /* CRC and full header precede allocation or generation changes. */
   if(n>=32&&p[1]==3&&!p[3]&&word(p,8)&&!(word(p,12)&~4095u)&&
      word(p,28)==r5_diag_crc(p,n)&&p[2]==R5_X_BEGIN&&n==32&&!word(p,16)&&!word(p,24)) {
    const struct r5_boot_bank *active=(const void *)(uintptr_t)STATE[0];
    if(active->state==0x35424c53u&&active->expected_mask==word(p,12)&&
       r5_transfer_bank_crc(active)==word(p,20)) {
     /* Reuse cancels an abandoned staging owner. Late PUT/SEAL must not
      * resurrect a transaction from a prior AP session. */
     MANAGER[0]=0;
     for(i=0;i<32;i++)ack[i]=p[i];ack[2]=R5_X_ACK;
     put(ack,32,active->state);put(ack,36,0);put(ack,40,active->received_mask);
     put(ack,28,r5_diag_crc(ack,sizeof(ack)));goto transfer_reply;
    }
    if(!MANAGER[0]||((struct r5_boot_bank *)(uintptr_t)MANAGER[0])->state) {
     uintptr_t a;volatile uint8_t *q;
     /* Bound retained generations; never overwrite or free reader-owned data. */
     if(MANAGER[1]>=16)goto generation_failed;
     a=(uintptr_t)FN(0x5ef69cu,bank_alloc_fn)(ALLOCATION_BYTES);
     if(!a||(a&7u)||a>UINT32_MAX-(ALLOCATION_BYTES-1u))goto generation_failed;
     q=(void *)a;for(i=0;i<ALLOCATION_BYTES;i++)q[i]=0;
     MANAGER[0]=(uint32_t)a;MANAGER[1]++;
    }
   }
   bank=(void *)(uintptr_t)MANAGER[0];
   ctx=bank?(void *)((uintptr_t)bank+TX_OFFSET):0;
   /* Ignore foreign/stale owners without poisoning a newer transaction or
    * mutating an already published generation. Return a visible rejection. */
   if(!bank||(p[2]!=R5_X_BEGIN&&
       (n<32||word(p,8)!=ctx->token||ctx->phase!=1))) {
    for(i=0;i<32;i++)ack[i]=i<n?p[i]:0;ack[2]=R5_X_ACK;
    put(ack,32,((const struct r5_boot_bank *)(uintptr_t)STATE[0])->state);
    put(ack,36,R5_X_BAD_STATE);put(ack,40,0);
    put(ack,28,r5_diag_crc(ack,sizeof(ack)));goto transfer_reply;
   }
   if(!r5_transfer_cp_receive(ctx,bank,p,n,ack))return 1;
   if(ctx->phase==2&&bank->state==0x35424c53u)
    __atomic_store_n(&STATE[0],(uint32_t)(uintptr_t)bank,__ATOMIC_RELEASE);
   goto transfer_reply;
generation_failed:
   for(i=0;i<32;i++)ack[i]=p[i];ack[2]=R5_X_ACK;
   put(ack,32,((const struct r5_boot_bank *)(uintptr_t)STATE[0])->state);
   put(ack,36,6);put(ack,40,0); /* retained-generation/heap resource limit */
   put(ack,28,r5_diag_crc(ack,sizeof(ack)));
transfer_reply:
   if(FN(0x53c221u,alloc_fn)(source,&allocation,R5_TRANSFER_ACK,0)||!allocation)return 1;
   reply=(uint8_t *)allocation;
   FN(0xbaaaa1u,source_fn)(reply,R5_STAGE413_CP_QUEUE);
   for(i=0;i<R5_TRANSFER_ACK;i++)reply[i]=ack[i];
   if(FN(0x53bb55u,send_fn)(source,reply))(void)FN(0x53c31du,free_fn)(source,reply);
   return 1;
  }
 }
 if(source!=R5_STAGE413_AP_QUEUE||!p||
    FN(0xbaad0du,size_fn)(p)!=R5_STAGE413_BYTES)return 0;
 if(p[0]!=R5_STAGE413_CLASS||p[1]!=R5_STAGE413_VERSION||
    p[2]!=R5_STAGE413_REQUEST||p[3]!=R5_STAGE413_BYTES||
    word(p,4)!=R5_STAGE413_MAGIC||!word(p,8)||
    (word(p,16)&~4095u)||word(p,20)||word(p,24)||
    word(p,28)!=crc28(p))return 0;
 bank_result=bank_once();
 /* Reply failures do not roll back or reallocate the one retained bank.
  * Original receive task always releases the incoming message once. */
 if(FN(0x53c221u,alloc_fn)(source,&allocation,R5_STAGE413_BYTES,0)||!allocation)return 1;
 reply=(uint8_t *)allocation;
 FN(0xbaaaa1u,source_fn)(reply,R5_STAGE413_CP_QUEUE);
 for(i=0;i<R5_STAGE413_BYTES;i++)reply[i]=p[i];
 reply[2]=R5_STAGE413_ACK;put(reply,20,bank_result);put(reply,24,R5_STAGE413_CP_BUILD);
 put(reply,28,crc28(reply));
 if(FN(0x53bb55u,send_fn)(source,reply))
  (void)FN(0x53c31du,free_fn)(source,reply);
 return 1;
}
