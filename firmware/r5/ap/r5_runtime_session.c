#include <stdint.h>
#include "r5_runtime_session.h"
#include "r5_filter_runtime.h"
#include "r5sound_runtime.h"
extern void *r5_stage411_dlsym(void *,const char *);
extern void *r5_stage411_child(void *);
#define LOAD(p) __atomic_load_n((p),__ATOMIC_ACQUIRE)
#define STORE(p,v) __atomic_store_n((p),(v),__ATOMIC_RELEASE)
#define CLOSED 0x80000000u
#define WAKE 0x40000000u
/* Epoch and wake intent share a CAS word so delayed power callbacks cannot
 * overwrite a newer wake intent. Only the file worker starts a session. */
static uint64_t gate;
static uint32_t handled,owner_epoch,owner_cold;
int r5_session_cold_start(void){return LOAD(&owner_cold)!=0;}
uint32_t r5_session_event_epoch(void){return (uint32_t)(LOAD(&gate)>>32);}
uint32_t r5_session_epoch(void){return LOAD(&owner_epoch);}
int r5_session_current(void){uint64_t g=LOAD(&gate);return (uint32_t)(g>>32)==LOAD(&owner_epoch)&&((uint32_t)g&WAKE)!=0;}
void r5_session_finish(void){__atomic_fetch_or(&gate,(uint64_t)CLOSED,__ATOMIC_ACQ_REL);}
void r5_stage421_power(const uint32_t *m){
    uint64_t old,next;uint32_t epoch,event;
    if(!m)return;event=m[0];if(event!=0x920143u&&event!=0x92015au)return;
    r5sound_power(m);old=LOAD(&gate);
    do{epoch=(uint32_t)(old>>32);if(epoch==0xfffffffeu)return;
       next=((uint64_t)(epoch+1)<<32)|CLOSED|(event==0x92015au?WAKE:0);
    }while(!__atomic_compare_exchange_n(&gate,&old,next,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE));
}
void r5_session_cold(void){uint64_t expected=0;(void)__atomic_compare_exchange_n(&gate,&expected,CLOSED|WAKE,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);}
int r5_session_prepare(void){
    uint64_t old=LOAD(&gate);uint32_t epoch=(uint32_t)(old>>32);
    if((uint32_t)old!=(CLOSED|WAKE)||epoch+1==LOAD(&handled))return 0;
    STORE(&owner_epoch,epoch);
    if(!__atomic_compare_exchange_n(&gate,&old,old&~(uint64_t)CLOSED,0,__ATOMIC_RELEASE,__ATOMIC_ACQUIRE))return 0;
    STORE(&owner_cold,LOAD(&handled)==0);STORE(&handled,epoch+1);return 1;
}
uint32_t r5_session_token(uint32_t salt){uint32_t t=((r5_session_epoch()+1)*0x9e3779b1u)^salt;return t?t:1;}
void *r5_stage421_loop(void *state){
    struct time {int64_t sec,ns;};struct time pause={0,100000000};
    int (*sleep)(const void *,void *)=(void *)r5_stage411_dlsym(0,"nanosleep");int ready=0;
    if(!sleep)return 0;
    for(;;){
        if(r5_session_prepare()){ready=r5_stage411_child(state)!=0;if(ready)r5sound_boot();r5_session_finish();}
        r5_filter_service();pause.ns=ready&&r5sound_service()?10000000:100000000;
        if(sleep(&pause,0))return 0;
    }
}
int r5sound_worker_yield(void){
    struct time {int64_t sec,ns;};const struct time pause={0,1000000};
    int (*sleep)(const void *,void *)=(void *)r5_stage411_dlsym(0,"nanosleep");
    if(!r5_session_current())return 0;r5_filter_service();if(sleep)(void)sleep(&pause,0);return r5_session_current();
}
