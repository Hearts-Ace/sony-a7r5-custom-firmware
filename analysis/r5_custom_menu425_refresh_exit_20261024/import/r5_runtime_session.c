#include <stdint.h>
#include <stddef.h>
#include "r5_runtime_session.h"
#include "r5_filter_runtime423.h"
extern void *r5_stage411_dlsym(void *,const char *);
extern void *r5_stage411_child(void *);
#define LOAD(p) __atomic_load_n((p),__ATOMIC_ACQUIRE)
#define STORE(p,v) __atomic_store_n((p),(v),__ATOMIC_RELEASE)
#define CLOSED 0x80000000u
#define WAKE 0x40000000u
#define READERS 0x3fffffffu
/* Epoch, power intent, admission and readers share one CAS word. A delayed
 * older power callback cannot overwrite a newer callback's wake intent. */
static uint64_t gate;
static uint32_t handled,owner_epoch,serial;
uint32_t r5_session_event_epoch(void){return (uint32_t)(LOAD(&gate)>>32);}
uint32_t r5_session_epoch(void){return LOAD(&owner_epoch);}
int r5_session_current(void){uint64_t g=LOAD(&gate);return (uint32_t)(g>>32)==LOAD(&owner_epoch)&&((uint32_t)g&WAKE)!=0;}
int r5_session_admit(void){
 uint64_t old=LOAD(&gate),next;
 do{if(((uint32_t)old&CLOSED)||((uint32_t)old&READERS)==READERS)return 0;next=old+1;}
 while(!__atomic_compare_exchange_n(&gate,&old,next,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE));
 return 1;
}
void r5_session_leave(void){__atomic_fetch_sub(&gate,1,__ATOMIC_RELEASE);}
void r5_session_finish(void){__atomic_fetch_or(&gate,(uint64_t)CLOSED,__ATOMIC_ACQ_REL);}
void r5_stage421_power(const uint32_t *m){
 uint64_t old,next;uint32_t e,event;
 if(!m)return;event=m[0];if(event!=0x920143u&&event!=0x92015au)return;
 old=LOAD(&gate);
 do{e=(uint32_t)(old>>32);if(e==0xfffffffeu)return;
  next=((uint64_t)(e+1)<<32)|((uint32_t)old&READERS)|CLOSED|(event==0x92015au?WAKE:0);
 }while(!__atomic_compare_exchange_n(&gate,&old,next,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE));
 /* No IO, bank overwrite/free or mailbox reset in the native power callback. */
}
void r5_session_cold(void){
 uint64_t expected=0;
 (void)__atomic_compare_exchange_n(&gate,&expected,CLOSED|WAKE,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);
}
int r5_session_prepare(void){
 uint64_t old=LOAD(&gate);uint32_t e=(uint32_t)(old>>32);
 if((uint32_t)old!=(CLOSED|WAKE)||e+1==LOAD(&handled))return 0;
 STORE(&owner_epoch,e);
 r5_stage421_probe_reset();r5_stage421_transfer_reset();r5_stage421_log_reset();
 if(!__atomic_compare_exchange_n(&gate,&old,old&~(uint64_t)CLOSED,0,__ATOMIC_RELEASE,__ATOMIC_ACQUIRE))return 0;
 STORE(&handled,e+1);return 1;
}
void *r5_stage421_loop(void *s){
 struct time {int64_t sec,ns;};const struct time pause={0,100000000};
 int (*sleep)(const void *,void *)=(void *)r5_stage411_dlsym(0,"nanosleep");
 if(!sleep)return 0;
 for(;;){if(r5_session_prepare()){r5_stage411_child(s);r5_session_finish();}
  r5_filter_service();
  if(sleep(&pause,0))return 0;
 }
}
/* Single owner drains ACK readers before another transfer, including the
 * second transaction when SD replaces the early internal configuration. */
int r5_session_new_transfer(void){
 struct time {int64_t sec,ns;};const struct time pause={0,1000000};
 int (*sleep)(const void *,void *)=(void *)r5_stage411_dlsym(0,"nanosleep");
 uint64_t old;unsigned i;
 if(!sleep||!r5_session_current()||serial==0xffffffffu)return 0;
 r5_session_finish();
 for(i=0;i<100;i++){
  if(!r5_session_current())return 0;old=LOAD(&gate);
  if((uint32_t)old==(CLOSED|WAKE)){
   r5_stage421_probe_reset();r5_stage421_transfer_reset();serial++;
   return __atomic_compare_exchange_n(&gate,&old,old&~(uint64_t)CLOSED,0,__ATOMIC_RELEASE,__ATOMIC_ACQUIRE);
  }
  if(sleep(&pause,0))return 0;
 }
 return 0;
}
uint32_t r5_session_token(uint32_t salt){uint32_t t=(serial*0x9e3779b1u)^salt;return t?t:1;}
