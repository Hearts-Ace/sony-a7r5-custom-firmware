/* CP control actor. Heavy preparation runs before the native settings lock;
 * only native 402f acceptance publishes the immutable parameter owner. */
#include "context.h"
#include "grid.h"
#include "control.h"
#include "owners.h"
#define AP_QUEUE R5S_QUEUE_AP
#define CP_QUEUE 0x90030001u
#define FN(a,t) ((t)(uintptr_t)(a))
static uint32_t get(const uint8_t *p){return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put(uint8_t *p,uint32_t x){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(x>>(i*8));}
static uint32_t crc(const uint8_t *p,unsigned n,int wire){uint32_t c=~0u;for(unsigned i=0;i<n;i++){c^=wire&&i>=28&&i<32?0:p[i];for(unsigned k=0;k<8;k++)c=(c>>1)^(0xedb88320u&(0u-(c&1u)));}return ~c;}
static int signed16(const uint8_t *p){unsigned v=p[0]|(unsigned)p[1]<<8;return v<32768?(int)v:(int)v-65536;}
static int name_valid(const uint8_t *p){unsigned i=0,j,n;uint32_t cp,min;if(!p[0])return 0;
 while(i<32&&p[i]){unsigned a=p[i++];if(a<128){if(a<32||a==127)return 0;continue;}
 if(a>=0xc2&&a<=0xdf){n=1;cp=a&31;min=128;}else if(a>=0xe0&&a<=0xef){n=2;cp=a&15;min=2048;}else if(a>=0xf0&&a<=0xf4){n=3;cp=a&7;min=65536;}else return 0;
 for(j=0;j<n;j++){if(i>=32||(p[i]&0xc0)!=0x80)return 0;cp=cp<<6|(p[i++]&63);}
 if(cp<min||cp>0x10ffff||(cp>=0xd800&&cp<=0xdfff)||cp<=159)return 0;}
 if(i==32)return 0;for(;i<32;i++)if(p[i])return 0;return 1;
}
static int valid(const uint8_t *p){uint32_t last=0;unsigned i,g;
 if(!name_valid(p)||get(p+1172)!=1||p[2391])return 0;
 for(i=0;i<1215;i++){int v=(int8_t)p[1176+i];if(v< -64||v>63)return 0;}
 for(g=0;g<3;g++)for(i=0;i<8;i++){int v=signed16(p+32+2*i);if(g)v+=signed16(p+32+16*g+2*i);if(i<4?(v< -1024||v>1023):(v<0||v>1023))return 0;}
 for(i=0;i<288;i++){int v=signed16(p+80+2*i);if(v< -8192||v>8191)return 0;}
 for(i=0;i<129;i++){uint32_t v=get(p+656+4*i);if((!i&&v)||v<last||v>131071)return 0;last=v;}
 return 1;
}
static void dispose(void *p){FN(0x5ef73cu,void(*)(void *))(p);}
static void *prepare(const void *p){
 struct od_context *c=FN(0x5ef69cu,void*(*)(uint32_t))(sizeof(*c));
 if(!c)return 0;
 for(unsigned i=0;i<sizeof(c->value);i++)((uint8_t *)&c->value)[i]=((const uint8_t *)p)[i];
 od_grid_prepare(c);return c;
}
static void reply(struct r5s_key key,unsigned op,unsigned status,unsigned detail){
 typedef int(*alloc_fn)(uint32_t,void **,uint32_t,uint32_t);
 void *allocation=0;
 if(FN(0x53c221u,alloc_fn)(AP_QUEUE,&allocation,40,0)||!allocation)return;
 uint8_t *p=allocation;
 FN(0xbaaaa1u,void(*)(void *,uint32_t))(p,CP_QUEUE);
 for(unsigned i=0;i<40;i++)p[i]=0;
 p[0]=0xe7;p[1]=1;p[2]=op|0x80;
 put(p+4,R5S_MAGIC);put(p+8,key.epoch);put(p+12,key.sequence);
 put(p+16,key.slot);put(p+20,key.digest);put(p+24,8);
 put(p+32,status);put(p+36,detail);put(p+28,crc(p,40,1));
 if(FN(0x53bb55u,int(*)(uint32_t,void *))(AP_QUEUE,p))
  (void)FN(0x53c31du,int(*)(uint32_t,void *))(AP_QUEUE,p);
}
unsigned od_collect(void){
 r5g_collect(&OD_STATE->submit.pool,dispose);
 unsigned outstanding=0;
 for(unsigned i=0;i<R5G_CELLS;i++){
  struct r5g_cell *c=&OD_STATE->submit.pool.cells[i];
  if(__atomic_load_n(&c->state,__ATOMIC_ACQUIRE)&&
     c->ticket!=OD_STATE->submit.current&&c->ticket!=OD_STATE->submit.pending.ticket)outstanding++;
 }
 return outstanding;
}
/* This ABI is also called through the sound dispatcher. The early native
 * receive hook consumes matching filter frames first, before acquiring 0x24. */
int r5_cp_stage413_consume(const uint8_t *p,uint32_t source){
 if(source!=AP_QUEUE||!p)return 0;
 unsigned n=FN(0xbaad0du,unsigned(*)(const void *))(p);
 if(n<8||p[0]!=0xe7||get(p+4)!=R5S_MAGIC)return 0;
 if(n<32||n>2424)return 1;
 struct r5s_key key={get(p+8),get(p+12),get(p+16),get(p+20)};
 unsigned op=p[2],status=R5S_CONFLICT,detail=0;
 if(p[1]!=1||p[3]||!key.epoch||!key.sequence||key.slot>12||get(p+28)!=crc(p,n,1))goto done;
 if(op==R5S_PREPARE){
  if(key.slot){
   if(n!=2424||get(p+24)!=2392||key.digest!=crc(p+32,2392,0)||!valid(p+32))goto done;
  }else if(n!=32||get(p+24)||key.digest)goto done;
  status=r5s_prepare(&OD_STATE->submit,key,p+32,prepare,dispose,&detail);
 }else if(op==R5S_ABORT){
  if(n!=32||get(p+24))goto done;
  status=r5s_abort(&OD_STATE->submit,key,dispose);detail=OD_STATE->submit.cookie;
 }else if(op==R5S_COLLECT){
  if(n!=32||get(p+24)||key.slot||key.digest)goto done;
  status=R5S_OK;detail=od_collect();
 }
done:reply(key,op,status,detail);return 1;
}
/* Called by the original 5-message discriminator, with lock 0x24 held.
 * Tagged stale jobs are not allowed to fall through as ordinary color sets.
 * No table preparation, allocation, free or reply occurs in this boundary. */
unsigned od_native_dispatch(const uint8_t *p,uint32_t source){
 unsigned n=FN(0xbaad0du,unsigned(*)(const void *))(p);
 if(n>=4&&p[0]==5&&p[2]==0x2f&&p[3]==0x40){
  int status=r5s_accept402f(&OD_STATE->submit,p,n,source);
  if(status==R5S_OK||status==R5S_DUPLICATE){
   if(status==R5S_OK){
    unsigned result=FN(0x345b99u,unsigned(*)(const uint8_t *,uint32_t))(p,source);
    od_color_accept();
    OD_STATE->accept_pending=1;return result;
   }
   OD_STATE->accept_pending=1;return 1;
  }
  if(status!=R5S_STOCK)return 1;
  unsigned result=FN(0x345b99u,unsigned(*)(const uint8_t *,uint32_t))(p,source);
  if(n==12&&!p[1])od_color_accept();
  return result;
 }
 return FN(0x345b99u,unsigned(*)(const uint8_t *,uint32_t))(p,source);
}
/* Still in the same serialized receiver, after its native unlock and before
 * freeing this message. An ACCEPT cannot be re-associated with a later key. */
void od_receive_complete(void){
 if(OD_STATE->accept_pending){
  OD_STATE->accept_pending=0;
  reply(OD_STATE->submit.key,R5S_ACCEPT,R5S_OK,OD_STATE->submit.cookie);
 }
}
