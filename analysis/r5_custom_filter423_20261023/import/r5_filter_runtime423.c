/* One AP file/transport worker; UI and native receive callbacks never do IO. */
#include "r5_filter_runtime423.h"
#include "r5_filter423.h"
#include "r5_filter_selection423.h"
#include "r5_runtime_session.h"
#include "r5_native_lut_directory.h"
extern void *r5_stage411_dlsym(void *,const char *);
extern int r5_native_ap_send(void *,const uint8_t *,size_t);
extern uint32_t r5_osal_msg_size(const void *);
extern void r5_native_creative_sequence_request(const void *);
#define LOAD(p) __atomic_load_n((p),__ATOMIC_ACQUIRE)
#define STORE(p,v) __atomic_store_n((p),(v),__ATOMIC_RELEASE)
/* desired: high32 request serial, low32 numbered configuration. */
static uint64_t desired;
static uint32_t applied,mask_ready;
static uint64_t handled;
static uint32_t initialized,saved,saved_valid,alias,bank_crc,mask,select_sequence,dirty;
static uint32_t inbox_state;
static uint64_t attempted_command;static uint32_t attempted_alias,attempts;
static struct r5_filter_select_request expected;
static uint8_t inbox[32];
struct time423 {int64_t sec,ns;};
typedef int (*sleep_fn)(const void *,void *);
typedef int (*clock_fn)(int,struct time423 *);
static int current(void){return initialized && alias && r5_session_current();}
unsigned r5_filter_selected(void){return LOAD(&applied);}
unsigned r5_filter_pending(void){return LOAD(&desired)!=LOAD(&handled)||LOAD(&dirty);}
int r5_filter_request(unsigned n){
    uint64_t old,next;uint32_t serial;
    if(n>12 || !LOAD(&mask_ready) || (n && !(r5_filter_available_mask()&(1u<<(n-1)))))return -1;
    old=LOAD(&desired);
    do{serial=(uint32_t)(old>>32);if(serial==0xffffffffu)return -1;
       next=((uint64_t)(serial+1)<<32)|n;
    }while(!__atomic_compare_exchange_n(&desired,&old,next,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE));
    return 0;
}
void r5_filter_load_selection(struct r5_lut_directory *d){
    unsigned n=0;int rc=r5_filter_selection_load(d,&n);
    /* Bad/absent sidecar starts off. A UI request already accepted this session
     * takes precedence over a later finite boot worker storage snapshot. */
    {uint64_t old=LOAD(&desired);if(!(old>>32))(void)__atomic_compare_exchange_n(&desired,&old,n,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);initialized=1;}
    if(rc==R5_IMPORTED){saved=n;saved_valid=1;}else saved_valid=0;
}
void r5_filter_bank_ready(uint32_t token,uint32_t crc,uint32_t valid_mask){
    uint64_t old,next;uint32_t n;
    if(!token || (valid_mask&~4095u))return;
    if(alias!=token || bank_crc!=crc || mask!=valid_mask)select_sequence=0;
    alias=token;bank_crc=crc;mask=valid_mask;STORE(&dirty,1);
    if(!initialized){initialized=1;saved_valid=0;}
    old=LOAD(&desired);
    for(;;){n=(uint32_t)old;if(!n || (n<=12 && (mask&(1u<<(n-1)))))break;
        if((uint32_t)(old>>32)==0xffffffffu)break;next=((uint64_t)((uint32_t)(old>>32)+1)<<32);
        if(__atomic_compare_exchange_n(&desired,&old,next,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))break;
    }
    STORE(&mask_ready,1);
}
int r5_filter_inbound(const uint8_t *p,uint32_t source){
    uint32_t n,zero=0;unsigned i;
    if(source!=0x90030001u)return 0;n=r5_osal_msg_size(p);
    if(!r5_filter_select_is_envelope(p,n))return 0;
    /* Consume late, malformed and foreign-selection packets without forwarding
     * the private envelope into native dispatch. Worker validates exact ACK. */
    if(n!=32 || !__atomic_compare_exchange_n(&inbox_state,&zero,1,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))return 1;
    if(r5_filter_select_ack(&expected,p,n)==-256){zero=1;(void)__atomic_compare_exchange_n(&inbox_state,&zero,0,0,__ATOMIC_RELEASE,__ATOMIC_ACQUIRE);return 1;}
    for(i=0;i<32;i++)inbox[i]=p[i];zero=1;
    (void)__atomic_compare_exchange_n(&inbox_state,&zero,2,0,__ATOMIC_RELEASE,__ATOMIC_ACQUIRE);return 1;
}
static int now(clock_fn f,uint64_t *out){
    struct time423 t;if(f(1,&t)||t.sec<0||t.ns<0||t.ns>=1000000000 || (uint64_t)t.sec>(UINT64_MAX-999)/1000)return -1;
    *out=(uint64_t)t.sec*1000+(uint64_t)t.ns/1000000;return 0;
}
static int save(unsigned n){
    struct r5_lut_directory d={0};struct r5_lut_directory_api a;
    uint8_t scratch[65537];int rc;
    if(r5_native_lut_directory_api_init(&a) || r5_lut_directory_acquire(&d,&a,scratch,sizeof(scratch)))return -1;
    rc=r5_filter_selection_save(&d,n);if(r5_lut_directory_release(&d))return -1;
    if(rc)return -1;saved=n;saved_valid=1;return 0;
}
static int select_send(unsigned n){
    struct r5_filter_select_request request;uint8_t packet[32],ack[32];uint64_t start,last,t;
    clock_fn clock=(clock_fn)r5_stage411_dlsym(0,"clock_gettime");sleep_fn sleep=(sleep_fn)r5_stage411_dlsym(0,"nanosleep");
    const struct time423 pause={0,10000000};uint32_t old;unsigned i,poll;int status=-1;
    if(!clock || !sleep || now(clock,&start) || select_sequence==0xffffffffu)return -1;
    old=LOAD(&inbox_state);do{if(old==1)return -1;}while(!__atomic_compare_exchange_n(&inbox_state,&old,3,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE));
    request.sequence=++select_sequence;request.selected=n;request.payload_crc=bank_crc;request.alias=alias;expected=request;
    STORE(&inbox_state,0);if(!r5_filter_select_encode(&request,packet))goto done;
    if(r5_native_ap_send(0,packet,sizeof(packet)))goto done;last=start;
    for(poll=0;poll<101;poll++) {
        if(!current() || now(clock,&t) || t<last || t<start || t-start>=1000)goto done;last=t;
        if(LOAD(&inbox_state)==2){
            for(i=0;i<32;i++)ack[i]=inbox[i];
            status=r5_filter_select_ack(&request,ack,sizeof(ack));
            if(status==1)goto done;
            /* A valid but late ACK for an earlier serial is ignored. */
            if(status!=-256)goto done;STORE(&inbox_state,0);
        }
        if(poll==100 || sleep(&pause,0))goto done;
    }
done:
    old=LOAD(&inbox_state);while(old!=1 && !__atomic_compare_exchange_n(&inbox_state,&old,3,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)){}
    return status==1?0:-1;
}
void r5_filter_service(void){
    uint64_t want;unsigned n;
    if(!current())return;want=LOAD(&desired);n=(uint32_t)want;
    if(n>12 || (n && !(mask&(1u<<(n-1)))))return;
    if(!LOAD(&dirty) && want==LOAD(&handled))return;
    if(attempted_command!=want || attempted_alias!=alias){attempted_command=want;attempted_alias=alias;attempts=0;}
    if(attempts>=3)return;attempts++;
    if(!saved_valid || saved!=n)if(save(n))return;
    if(!current() || select_send(n) || !current())return;
    STORE(&applied,n);STORE(&dirty,0);STORE(&handled,want);
    {uint32_t request[8]={0};request[1]=1;r5_native_creative_sequence_request(request);}
}
