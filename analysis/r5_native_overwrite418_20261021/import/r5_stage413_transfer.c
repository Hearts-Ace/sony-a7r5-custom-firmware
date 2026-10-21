/* One finite cold-start parameter upload. No menu/consumer publication. */
#include "r5_look_transfer.h"
extern void *r5_stage411_dlsym(void *,const char *);
extern int r5_stage413_capacity_ready(void);
extern int r5_native_ap_send(void *,const uint8_t *,size_t);
extern uint32_t r5_osal_msg_size(const void *);
#define LOAD(p) __atomic_load_n((p),__ATOMIC_ACQUIRE)
#define STORE(p,v) __atomic_store_n((p),(v),__ATOMIC_RELEASE)
struct transfer_state {
 uint32_t once,phase,result,inbox_state,matched,sends,polls,late;
 struct r5_transfer_ap tx;
 uint8_t inbox[R5_TRANSFER_ACK];
};
__attribute__((aligned(16))) struct transfer_state r5_stage413_transfer_state;
struct transfer_time {int64_t seconds,nanoseconds;};
typedef int (*clock_fn)(int,struct transfer_time *);
typedef int (*sleep_fn)(const struct transfer_time *,struct transfer_time *);
static int transition(uint32_t *p,uint32_t from,uint32_t to) {
 return __atomic_compare_exchange_n(p,&from,to,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);
}
int r5_stage413_inbound(const uint8_t *p,uint32_t source) {
 struct transfer_state *s=&r5_stage413_transfer_state;uint32_t n,old;unsigned i;
 if(source!=0x90030001u||!LOAD(&s->once))return 0;
 n=r5_osal_msg_size(p);if(!r5_transfer_is_envelope(p,n))return 0;
 if(LOAD(&s->inbox_state)==5){__atomic_fetch_add(&s->late,1,__ATOMIC_RELAXED);return 1;}
 if(n!=R5_TRANSFER_ACK||!transition(&s->inbox_state,0,1)) {
  old=LOAD(&s->inbox_state);
  while(old!=5&&old!=4&&!__atomic_compare_exchange_n(&s->inbox_state,&old,4,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)){}
  return 1;
 }
 for(i=0;i<R5_TRANSFER_ACK;i++)s->inbox[i]=p[i];
 (void)transition(&s->inbox_state,1,2);return 1;
}
static int now_ms(clock_fn clock,uint64_t *out) {
 struct transfer_time t;
 if(clock(1,&t)||t.seconds<0||t.nanoseconds<0||t.nanoseconds>=1000000000||
  (uint64_t)t.seconds>(UINT64_MAX-999u)/1000u)return -1;
 *out=(uint64_t)t.seconds*1000u+(uint64_t)t.nanoseconds/1000000u;return 0;
}
static uint32_t crcbyte(uint32_t c,uint8_t b) {
 unsigned k;c^=b;for(k=0;k<8;k++)c=(c>>1)^((0u-(c&1u))&0xedb88320u);return c;
}
static uint32_t set_crc(const struct r5_look_set *set) {
 uint32_t c=~0u;unsigned i,j,k;const uint8_t *p;
 for(k=0;k<4;k++)c=crcbyte(c,(uint8_t)(set->valid_mask>>(8*k)));
 for(i=1;i<=12;i++)if(set->valid_mask&(1u<<(i-1))) {
  for(k=0;k<4;k++)c=crcbyte(c,(uint8_t)(i>>(8*k)));
  p=(const uint8_t *)&set->look[i-1];
  for(j=0;j<R5_TRANSFER_VALUES;j++)c=crcbyte(c,p[j]);
 }
 return ~c;
}
static int send_packet(void *unused,const uint8_t *p,size_t n) {
 (void)unused;__atomic_fetch_add(&r5_stage413_transfer_state.sends,1,__ATOMIC_RELAXED);
 return r5_native_ap_send(0,p,n);
}
void r5_stage413_transfer_run(const struct r5_look_set *set) {
 struct transfer_state *s=&r5_stage413_transfer_state;
 uint32_t expected=0,token,old;uint64_t start,last,now;unsigned poll;
 clock_fn clock;sleep_fn sleep;uint8_t packet[R5_TRANSFER_MAX],ack[R5_TRANSFER_ACK];
 const struct transfer_time delay={0,100000000};
 struct r5_transfer_io io;int rc;unsigned i;
 io.context=0;io.send=send_packet;
 if(!set||!set->valid_mask||(set->valid_mask&~4095u)||!r5_stage413_capacity_ready()||
  !__atomic_compare_exchange_n(&s->once,&expected,1,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))return;
 STORE(&s->phase,1);s->result=1;
 clock=(clock_fn)r5_stage411_dlsym(0,"clock_gettime");
 sleep=(sleep_fn)r5_stage411_dlsym(0,"nanosleep");
 if(!clock||!sleep||now_ms(clock,&start)||start>UINT64_MAX-3000u)goto done;
 last=start;token=(uint32_t)start^(uint32_t)(start>>32)^0x41805231u;if(!token)token=1;
 if(r5_transfer_ap_begin(&s->tx,set,token,set_crc(set),start,start+3000u))goto done;
 STORE(&s->phase,2);
 for(poll=0;poll<40;poll++) {
  s->polls=poll+1;
  if(now_ms(clock,&now)||now<last||now<start||now-start>=3000u){s->result=2;goto done;}
  last=now;
  if(LOAD(&s->inbox_state)==4){s->result=3;goto done;}
  if(s->tx.phase==1||s->tx.phase==6) {
   if(s->sends>=14){s->result=4;goto done;}
   rc=r5_transfer_ap_step(&s->tx,&io,now,packet);if(rc<0){s->result=4;goto done;}
  }
  if(now_ms(clock,&now)||now<last||now<start||now-start>=3000u){s->result=2;goto done;}
  last=now;
  if(transition(&s->inbox_state,2,3)) {
   for(i=0;i<R5_TRANSFER_ACK;i++)ack[i]=s->inbox[i];
   rc=r5_transfer_ap_ack(&s->tx,ack,sizeof(ack),now);
   if(rc<0){s->result=5;goto done;}
   if(!transition(&s->inbox_state,3,0)){s->result=3;goto done;}
   if(rc==1){s->matched=1;s->result=0;goto done;}
   if(s->tx.phase==1)continue;
  }
  if(poll==39||sleep(&delay,0)){s->result=2;goto done;}
 }
done:
 old=LOAD(&s->inbox_state);
 while(old!=5&&!__atomic_compare_exchange_n(&s->inbox_state,&old,5,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)){}
 STORE(&s->phase,3);
}
/* Name hook contract: native UI caller copies the NUL-terminated ASCII name.
 * Pointer lifetime is the cold-start importer BSS; no unvalidated SD pointer.
 * Native ordinal (1..12) only; no six-slot marker conversion is involved. */
const char *r5_native12_name(unsigned number) {
 struct transfer_state *s=&r5_stage413_transfer_state;
 if(number<1||number>R5_LOOK_SLOTS||!LOAD(&s->matched)||
    !s->tx.set||!(r5_transfer_ap_active_mask(&s->tx)&(1u<<(number-1))))return 0;
 return s->tx.set->look[number-1].name;
}
