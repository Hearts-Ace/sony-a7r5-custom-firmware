/* One finite cold-start parameter upload. No menu/consumer publication. */
#include "r5_look_transfer.h"
#include "r5_runtime_session.h"
#include "r5_filter423.h"
#include "r5_filter_runtime423.h"
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
 if(n>=12&&((uint32_t)p[8]|(uint32_t)p[9]<<8|(uint32_t)p[10]<<16|(uint32_t)p[11]<<24)!=s->tx.token)return 1;
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
 if(!set||(set->valid_mask&~4095u)||!r5_stage413_capacity_ready()||
  !__atomic_compare_exchange_n(&s->once,&expected,1,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))return;
 STORE(&s->phase,1);s->result=1;
 clock=(clock_fn)r5_stage411_dlsym(0,"clock_gettime");
 sleep=(sleep_fn)r5_stage411_dlsym(0,"nanosleep");
 if(!clock||!sleep||now_ms(clock,&start)||start>UINT64_MAX-3000u)goto done;
 last=start;token=r5_session_token(0x41805231u);if(!token)token=1;
 if(r5_transfer_ap_begin(&s->tx,set,token,r5_filter_compact_set_crc(set),start,start+3000u))goto done;
 STORE(&s->phase,2);
 for(poll=0;poll<40;poll++) {
  s->polls=poll+1;
  if(!r5_session_current()||now_ms(clock,&now)||now<last||now<start||now-start>=3000u){s->result=2;goto done;}
  last=now;
  if(LOAD(&s->inbox_state)==4){s->result=3;goto done;}
  if(s->tx.phase==1||s->tx.phase==6) {
   if(s->sends>=14){s->result=4;goto done;}
   rc=r5_transfer_ap_step(&s->tx,&io,now,packet);if(rc<0){s->result=4;goto done;}
  }
  if(!r5_session_current()||now_ms(clock,&now)||now<last||now<start||now-start>=3000u){s->result=2;goto done;}
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
/* Independent menu names publish only after a matching complete data ACK. */
int r5_stage421_parameters_ready(void){
 struct transfer_state *s=&r5_stage413_transfer_state;
 if(!LOAD(&s->matched)||!s->tx.set)return 0;
 {int names=r5_filter_names_publish(s->tx.set);
  r5_filter_bank_ready(s->tx.token,s->tx.payload_crc,s->tx.mask);
  r5_filter_service();return names;}
}

void r5_transfer420_log(unsigned drive){
 extern int r5_log420_emit(unsigned,const char *,const uint32_t *,unsigned);
 struct transfer_state *s=&r5_stage413_transfer_state;
 uint32_t v[11]={s->phase,s->result,s->matched,s->sends,s->tx.phase,s->tx.error,s->tx.slot,s->tx.mask,s->tx.payload_crc,s->tx.token,r5_session_epoch()};
 r5_log420_emit(drive,s->matched?"CP_PARAMETERS_SEALED":"CP_PARAMETERS_NOT_APPLIED",v,11);
 /* result5 means the worker consumed one complete44B ACK. Keep its raw
  * header/state/status/mask so CRC/echo errors cannot masquerade as OOM. */
 if(s->result==5){
  for(unsigned i=0;i<11;i++){
   const uint8_t *p=s->inbox+4*i;
   v[i]=(uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;
  }
  r5_log420_emit(drive,"CP_PARAMETERS_REJECTED_ACK",v,11);
 }
}

void r5_stage421_transfer_reset(void){extern void *memset(void *,int,size_t);memset(&r5_stage413_transfer_state,0,sizeof(r5_stage413_transfer_state));}

int r5_stage421_transfer_matched(void){return LOAD(&r5_stage413_transfer_state.matched)!=0;}
