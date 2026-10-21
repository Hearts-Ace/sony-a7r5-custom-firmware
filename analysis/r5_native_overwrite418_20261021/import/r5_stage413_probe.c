/* Stage5c one-shot bank-capacity probe. Retains411 RAM/hook ABI. No menu/color activation. */
#include <stdint.h>
#include <stddef.h>
extern int r5_stage413_inbound(const uint8_t *,uint32_t);
extern void *r5_stage411_dlsym(void *,const char *);
extern int r5_native_ap_send(void *,const uint8_t *,size_t);
extern uint32_t r5_osal_msg_size(const void *);
#define LOAD(p) __atomic_load_n((p),__ATOMIC_ACQUIRE)
#define STORE(p,v) __atomic_store_n((p),(v),__ATOMIC_RELEASE)
struct r5_stage411_probe_diagnostics {
    uint32_t once,phase,result,token,config_crc,mask,polls,inbox_state;
    int32_t send_status;
    uint32_t matched,late_or_duplicate;
    uint8_t inbox[32];
};
__attribute__((aligned(16))) struct r5_stage411_probe_diagnostics r5_stage411_probe_state;
struct probe_time {int64_t seconds,nanoseconds;};
typedef int (*clock_fn)(int,struct probe_time *);
typedef int (*sleep_fn)(const struct probe_time *,struct probe_time *);
static uint32_t get32(const uint8_t *p) {
    return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;
}
static void put32(uint8_t *p,uint32_t v) {
    p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);p[2]=(uint8_t)(v>>16);p[3]=(uint8_t)(v>>24);
}
static uint32_t crc28(const uint8_t *p) {
    uint32_t c=~0u;unsigned i,k;
    for(i=0;i<28;i++){c^=p[i];for(k=0;k<8;k++)c=(c>>1)^((0u-(c&1u))&0xedb88320u);}
    return ~c;
}
static int envelope(const uint8_t *p,uint32_t n) {
    return p&&n>=8&&p[0]==0xe8&&p[4]=='R'&&p[5]=='5'&&p[6]=='P'&&p[7]=='2';
}
static int transition(uint32_t *p,uint32_t from,uint32_t to) {
    return __atomic_compare_exchange_n(p,&from,to,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);
}
/* Native AP receiver owns and frees packet on both branches. Copy only.
 * Late/duplicate probe traffic is consumed, never sent into native dispatch. */
int r5_stage411_inbound(const uint8_t *p,uint32_t source) {
    struct r5_stage411_probe_diagnostics *s=&r5_stage411_probe_state;
    uint32_t n,state;unsigned i;
    if(r5_stage413_inbound(p,source))return 1;
    if(source!=0x90030001u||!LOAD(&s->once))return 0;
    n=r5_osal_msg_size(p);
    if(!envelope(p,n))return 0;
    state=LOAD(&s->inbox_state);
    if(state==5){__atomic_fetch_add(&s->late_or_duplicate,1,__ATOMIC_RELAXED);return 1;}
    if(n!=32||!transition(&s->inbox_state,0,1)) {
        state=LOAD(&s->inbox_state);
        while(state!=5&&state!=4&&!__atomic_compare_exchange_n(&s->inbox_state,&state,4,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)){}
        return 1;
    }
    for(i=0;i<32;i++)s->inbox[i]=p[i];
    (void)transition(&s->inbox_state,1,2);return 1;
}
static int now_ms(clock_fn clock,uint64_t *out) {
    struct probe_time t;
    if(clock(1,&t)||t.seconds<0||t.nanoseconds<0||t.nanoseconds>=1000000000||
       (uint64_t)t.seconds>(UINT64_MAX-999u)/1000u)return -1;
    *out=(uint64_t)t.seconds*1000u+(uint64_t)t.nanoseconds/1000000u;return 0;
}
void r5_stage411_probe_run(uint32_t mask,uint32_t digest) {
    struct r5_stage411_probe_diagnostics *s=&r5_stage411_probe_state;
    uint32_t expected=0,state;uint64_t start,last,now;
    clock_fn clock;sleep_fn sleep;uint8_t p[32]={0};unsigned i,poll;
    const struct probe_time delay={0,100000000};
    if(mask&~4095u||!__atomic_compare_exchange_n(&s->once,&expected,1,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))return;
    STORE(&s->phase,1);s->result=1;
    clock=(clock_fn)r5_stage411_dlsym(0,"clock_gettime");
    sleep=(sleep_fn)r5_stage411_dlsym(0,"nanosleep");
    if(!clock||!sleep||now_ms(clock,&start))goto done;
    last=start;s->token=(uint32_t)start^(uint32_t)(start>>32)^0x41105231u;
    if(!s->token)s->token=1;
    s->mask=mask;s->config_crc=digest;
    p[0]=0xe8;p[1]=1;p[2]=1;p[3]=32;p[4]='R';p[5]='5';p[6]='P';p[7]='2';
    put32(p+8,s->token);put32(p+12,digest);put32(p+16,mask);put32(p+28,crc28(p));
    STORE(&s->phase,2);
    s->send_status=r5_native_ap_send(0,p,sizeof(p));
    if(s->send_status){s->result=2;goto done;}
    for(poll=0;poll<11;poll++) {
        s->polls=poll+1;
        if(now_ms(clock,&now)||now<last||now<start||now-start>=1000u){s->result=3;goto done;}
        last=now;state=LOAD(&s->inbox_state);
        if(state==4){s->result=4;goto done;}
        if(state==2&&transition(&s->inbox_state,2,3)) {
            for(i=0;i<32;i++)p[i]=s->inbox[i];
            if(p[1]!=1||p[2]!=0x81||p[3]!=32||get32(p+8)!=s->token||
               get32(p+12)!=digest||get32(p+16)!=mask||
               get32(p+24)!=0x418||get32(p+28)!=crc28(p)){s->result=5;goto done;}
            /* CP reports a reserved, zeroed bank, not accepted color data. */
            if(!get32(p+20)){s->result=6;goto done;}
            if(get32(p+20)!=14128u){s->result=5;goto done;}
            if(!transition(&s->inbox_state,3,5)){s->result=4;goto done;}
            s->matched=1;s->result=0;goto done;
        }
        if(poll==10||sleep(&delay,0)){s->result=3;goto done;}
    }
done:
    state=LOAD(&s->inbox_state);
    while(state!=5&&!__atomic_compare_exchange_n(&s->inbox_state,&state,5,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)){}
    STORE(&s->phase,3);
}

int r5_stage413_capacity_ready(void) {return __atomic_load_n(&r5_stage411_probe_state.matched,__ATOMIC_ACQUIRE)==1;}
