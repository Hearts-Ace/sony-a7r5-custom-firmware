/* Stage5b: one demand-allocated zero bank, no parameter payload or consumer.
 * Original receive task serializes this handler with its resource24 lock.
 * Bank allocation uses the original shared-heap function and its own mutex;
 * that native mutex is not promised nonblocking. No boot/init hook is added.
 */
#include "r5_stage413_probe.h"
#include "r5_look_transfer.h"
#define FN(a,t) ((t)(uintptr_t)(a))
typedef uint32_t (*size_fn)(const void *);
typedef int (*alloc_fn)(uint32_t,void **,uint32_t,uint32_t);
typedef int (*send_fn)(uint32_t,void *);
typedef int (*free_fn)(uint32_t,void *);
typedef void (*source_fn)(void *,uint32_t);
typedef void *(*bank_alloc_fn)(uint32_t);
#define BANK_BYTES 14128u
#define ALLOCATION_BYTES 37612u
#define STATE ((volatile uint32_t *)(uintptr_t)0x1a39448u)

/* STATE[0]=retained bank pointer; STATE[1]=0 untried,1 attempted failure,
 * or14128 verified. Both words are in an explicit8B BSS/clear extension.
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
 STATE[1]=BANK_BYTES;return BANK_BYTES;
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
  if(r5_transfer_is_envelope(p,n)) {
   uint8_t ack[R5_TRANSFER_ACK];
   struct r5_boot_bank *bank=(struct r5_boot_bank *)(uintptr_t)STATE[0];
   struct r5_transfer_cp *ctx=(struct r5_transfer_cp *)(uintptr_t)0x1a39450u;
   if(n>R5_TRANSFER_MAX||!bank||STATE[1]!=BANK_BYTES)return 1;
   if(!r5_transfer_cp_receive(ctx,bank,p,n,ack))return 1;
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
