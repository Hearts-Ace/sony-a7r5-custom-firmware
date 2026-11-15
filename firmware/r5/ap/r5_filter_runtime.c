/* One AP worker owns file I/O, commands, and recovery. A prepared cookie is
 * attached to one native color task; only its native CP acceptance commits. */
#include "r5_filter_runtime.h"
#include "r5_filter_store.h"
#include "r5_runtime_session.h"
#include "job.h"
extern void *r5_stage411_dlsym(void *,const char *);
extern int r5_native_ap_send(void *,const uint8_t *,size_t);
extern uint32_t r5_osal_msg_size(const void *);
extern void r5_native_creative_sequence_request(const void *);
extern void r5_native_refresh_construct425(void *,const void *);
extern void r5_native_refresh_execute425(void *);
extern void r5_native_serialize_color(uint32_t,uint32_t,uint8_t *);
#define LOAD(p) __atomic_load_n((p),__ATOMIC_ACQUIRE)
#define STORE(p,v) __atomic_store_n((p),(v),__ATOMIC_RELEASE)
#define CAS(p,e,v) __atomic_compare_exchange_n((p),(e),(v),0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)
#define JOB_RUNNING 0x01000000u
#define JOB_FINISHED 0x02000000u
#define ACK_FINISHED 0x80000000u
#define CP_QUEUE 0x90030001u
#define ACK_OK 0u
#define ACK_BUSY 1u
#define ACK_STALE 2u
#define ACK_ACCEPTED 6u
struct key {uint32_t epoch,seq,slot,digest;};
struct reply {uint32_t status,detail;};
struct time_value {int64_t sec,ns;};
typedef int (*clock_fn)(int,struct time_value *);
typedef int (*sleep_fn)(const void *,void *);
static const struct time_value pause={0,10000000};
static struct r5f_index catalog;
static uint32_t published,ready,applied,dirty,service_busy,command_state,command_sequence;
static uint64_t desired,handled;
static uint32_t saved,saved_valid,sequence,token,synced,attempts;
static uint64_t retry_at,attempted,collect_at;
static uint32_t collect_pending;
/* PREPARE, ABORT or COLLECT responses use the synchronous worker mailbox.
 * An unsolicited ACCEPT can arrive while the native task is still running. */
static uint32_t inbox_state;
static uint8_t inbox[40];
static uint64_t accept_stamp;
static uint32_t accept_epoch,accept_slot,accept_digest;
static const uint32_t job_request[8]={0,1};
static uint32_t job_state;
static uintptr_t job_object;
/* If ABORT times out, keep the key (never the payload). Reconcile it before
 * any later file read or PREPARE; the old operation might already be active. */
static struct {struct key key;uint64_t want;uint32_t cookie,executed,accepted,explicit_command;} recovery;
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
static uint32_t wire_crc(const uint8_t *p,size_t n){uint32_t c=~0u;for(size_t i=0;i<n;i++){c^=(i>=28&&i<32)?0:p[i];for(unsigned b=0;b<8;b++)c=(c>>1)^(0xedb88320u&(0u-(c&1u)));}return ~c;}
static int current(void){return LOAD(&ready)&&r5_session_current();}
static clock_fn clock_source(void){return (clock_fn)r5_stage411_dlsym(0,"clock_gettime");}
static sleep_fn sleep_source(void){return (sleep_fn)r5_stage411_dlsym(0,"nanosleep");}
static int now(clock_fn f,uint64_t *out){struct time_value t;
    if(!f||f(1,&t)||t.sec<0||t.ns<0||t.ns>=1000000000||(uint64_t)t.sec>(UINT64_MAX-10000)/1000)return -1;
    *out=(uint64_t)t.sec*1000+(uint64_t)t.ns/1000000;return 0;
}
unsigned r5_filter_selected(void){return LOAD(&applied);}
unsigned r5_filter_pending(void){return LOAD(&desired)!=LOAD(&handled)||LOAD(&dirty);}
unsigned r5_filter_command_state(void){return LOAD(&command_state);}
unsigned r5_filter_command_sequence(void){return LOAD(&command_sequence);}
uint32_t r5_filter_available_mask(void){return LOAD(&published)?catalog.mask:0;}
const char *r5_filter_short_name(unsigned n){return n&&n<=12&&(r5_filter_available_mask()&(1u<<(n-1)))?catalog.entry[n-1].short_name:0;}
const char *r5_filter_full_name(unsigned n){return n&&n<=12&&(r5_filter_available_mask()&(1u<<(n-1)))?catalog.entry[n-1].full_name:0;}
int r5_filter_catalog_ready(const struct r5f_index *index,unsigned selected,unsigned persisted){
    if(!index||index->mask&~4095u||selected>12)return -1;
    if(LOAD(&published)){
        const uint8_t *a=(const uint8_t *)&catalog,*b=(const uint8_t *)index;
        for(size_t i=0;i<sizeof(catalog);i++)if(a[i]!=b[i])return -1;
    }else{catalog=*index;STORE(&published,1);}
    if(selected&&!(catalog.mask&(1u<<(selected-1)))){selected=0;persisted=0;}
    /* Accepted UI request, including one interrupted by power, wins over the
     * boot snapshot. A new epoch's PREPARE invalidates an old pending key. */
    {uint64_t old=LOAD(&desired);if(!(old>>32))(void)CAS(&desired,&old,selected);}
    saved=selected;saved_valid=persisted;synced=0;attempted=UINT64_MAX;attempts=0;retry_at=0;
    recovery.key.seq=0;STORE(&accept_stamp,0);STORE(&job_state,0);STORE(&job_object,0);
    token=r5_session_epoch()+1;collect_pending=1;collect_at=0;
    if(LOAD(&command_state)==3)STORE(&command_state,0);STORE(&dirty,1);STORE(&ready,1);return 0;
}
int r5_filter_request(unsigned n){
    uint32_t state=LOAD(&command_state),serial;uint64_t old;
    if(n>12||!current()||(n&&!(r5_filter_available_mask()&(1u<<(n-1)))))return -1;
    do{if(state==1||state==4)return -1;}while(!CAS(&command_state,&state,4));
    old=LOAD(&desired);serial=(uint32_t)(old>>32);if(serial==UINT32_MAX){STORE(&command_state,3);return -1;}
    serial++;STORE(&command_sequence,serial);STORE(&desired,((uint64_t)serial<<32)|n);STORE(&command_state,1);return 0;
}
void r5_filter_refresh_construct425(void *object,const void *params){
    uint32_t state=LOAD(&job_state);
    r5_native_refresh_construct425(object,params);
    /* Native request calls the constructor synchronously with argument+16;
     * ordinary E4 parameters can never identify the worker-owned request. */
    if(params==job_request+4&&state&&!(state&~R5S_COOKIE_MAX)&&state==LOAD(&job_state))STORE(&job_object,(uintptr_t)object);
}
void r5_filter_refresh_execute425(void *object){
    struct r5j_object copy;uint32_t state=LOAD(&job_state),running=state|JOB_RUNNING;
    if(state&&!(state&~R5S_COOKIE_MAX)&&current()&&(uintptr_t)object==LOAD(&job_object)&&CAS(&job_state,&state,running)){
        if(!r5j_copy(&copy,object,state)){
            r5_native_refresh_execute425(&copy);
            (void)CAS(&job_state,&running,state|JOB_FINISHED);return;
        }
        /* Unknown selector representation: keep stock semantics, send no tag,
         * and let the worker ABORT its still-unaccepted preparation. */
        (void)CAS(&job_state,&running,0);
    }
    r5_native_refresh_execute425(object);
}
void r5_filter_serialize_color(uint32_t mode,uint32_t look,uint8_t out[4]){
    r5j_serialize_color(mode,look,out,r5_native_serialize_color);
}
static int same_key(const uint8_t *p,const struct key *key){
    return get32(p+8)==key->epoch&&get32(p+12)==key->seq&&get32(p+16)==key->slot&&get32(p+20)==key->digest;
}
static int ack_format(const uint8_t *p){return p[1]==1&&!p[3]&&get32(p+24)==8&&wire_crc(p,40)==get32(p+28);}
int r5_filter_inbound(const uint8_t *p,uint32_t source){
    uint32_t n,zero=0;if(!p||source!=CP_QUEUE)return 0;n=r5_osal_msg_size(p);
    if(n<8||p[0]!=0xe7||get32(p+4)!=R5S_MAGIC)return 0;
    if(n!=40||!ack_format(p))return 1;
    if(p[2]==(R5S_ACCEPT|0x80)){
        uint64_t stamp=LOAD(&accept_stamp);uint32_t cookie=get32(p+36);
        struct key k={LOAD(&accept_epoch),(uint32_t)(stamp>>32),LOAD(&accept_slot),LOAD(&accept_digest)};
        if(cookie&&(uint32_t)stamp==cookie&&same_key(p,&k)&&get32(p+32)==ACK_OK)
            (void)CAS(&accept_stamp,&stamp,stamp|ACK_FINISHED);
        return 1;
    }
    if(!CAS(&inbox_state,&zero,1))return 1;
    for(unsigned i=0;i<40;i++)inbox[i]=p[i];STORE(&inbox_state,2);return 1;
}
static void header(uint8_t *p,unsigned op,const struct key *key){
    for(unsigned i=0;i<32;i++)p[i]=0;p[0]=0xe7;p[1]=1;p[2]=(uint8_t)op;
    put32(p+4,R5S_MAGIC);put32(p+8,key->epoch);put32(p+12,key->seq);put32(p+16,key->slot);
    put32(p+20,key->digest);put32(p+24,op==R5S_PREPARE&&key->slot?R5F_COMPACT:0);
}
static int exchange(uint8_t *packet,size_t length,const struct key *key,unsigned budget,struct reply *reply){
    clock_fn clock=clock_source();sleep_fn sleep=sleep_source();uint64_t start,last,t;uint32_t old;
    if(!sleep||now(clock,&start))return -1;last=start;
    /* Never erase a callback that owns the mail slot while it copies bytes. */
    for(unsigned poll=0;;poll++){
        old=LOAD(&inbox_state);if(old!=1&&CAS(&inbox_state,&old,3))break;
        if(poll==10||sleep(&pause,0))return -1;
    }
    STORE(&inbox_state,0);put32(packet+28,wire_crc(packet,length));
    for(unsigned poll=0;poll<=budget/10;poll++){
        if(!current()||now(clock,&t)||t<last||t-start>=budget)return -1;last=t;
        if(poll%10==0&&r5_native_ap_send(0,packet,length))return -1;
        if(LOAD(&inbox_state)==2){
            if(inbox[2]==(packet[2]|0x80)&&same_key(inbox,key)&&get32(inbox+32)<=ACK_ACCEPTED){
                reply->status=get32(inbox+32);reply->detail=get32(inbox+36);STORE(&inbox_state,0);
                if(reply->status!=ACK_BUSY)return 0;
            }else STORE(&inbox_state,0);
        }
        if(sleep(&pause,0))return -1;
    }return -1;
}
static void native_submit(const struct key *key,uint32_t cookie,uint32_t *executed,uint32_t *accepted){
    uint64_t start,last,t,stamp=((uint64_t)key->seq<<32)|cookie;
    clock_fn clock=clock_source();sleep_fn sleep=sleep_source();
    *executed=*accepted=0;
    if(!current()||!sleep||now(clock,&start))return;last=start;
    STORE(&accept_epoch,key->epoch);STORE(&accept_slot,key->slot);STORE(&accept_digest,key->digest);STORE(&accept_stamp,stamp);
    STORE(&job_object,0);STORE(&job_state,cookie);
    r5_native_creative_sequence_request(job_request);
    for(unsigned poll=0;poll<501;poll++){
        uint32_t state=LOAD(&job_state);
        *executed=(state==(cookie|JOB_FINISHED));*accepted=(LOAD(&accept_stamp)==(stamp|ACK_FINISHED));
        if((*executed&&*accepted)||!state||!current()||now(clock,&t)||t<last||t-start>=5000)break;last=t;
        if(sleep(&pause,0))break;
    }
    *executed=(__atomic_exchange_n(&job_state,0,__ATOMIC_ACQ_REL)==(cookie|JOB_FINISHED));STORE(&job_object,0);
    *accepted=(__atomic_exchange_n(&accept_stamp,0,__ATOMIC_ACQ_REL)==(stamp|ACK_FINISHED));
}
static int save(unsigned n){unsigned v=n;if(r5_filter_store_selection(&v,1))return -1;saved=n;saved_valid=1;return 0;}
static void finish(uint64_t want,unsigned n,unsigned explicit_command,int active,int complete,uint64_t t){
    if(!current())return;
    if(active){
        synced=1;STORE(&applied,n);STORE(&dirty,0);
        if(complete&&(!saved_valid||saved!=n)&&save(n))complete=0;
    }
    if(!current())return;
    if(complete){STORE(&handled,want);if(explicit_command)STORE(&command_state,2);return;}
    if(!explicit_command){retry_at=t+1000;return;}
    want=(want&0xffffffff00000000ull)|r5_filter_selected();STORE(&desired,want);STORE(&handled,want);STORE(&command_state,3);
}
static void recover(uint64_t t){
    struct reply r;uint8_t packet[32];struct key key=recovery.key;
    if(t<retry_at)return;
    header(packet,R5S_ABORT,&key);
    if(exchange(packet,sizeof(packet),&key,350,&r)){retry_at=t+500;return;}
    if(r.status==ACK_ACCEPTED&&recovery.cookie&&r.detail==recovery.cookie)recovery.accepted=1;
    else if(r.status!=ACK_OK&&r.status!=ACK_STALE){retry_at=t+500;return;}
    if(!current())return;
    finish(recovery.want,key.slot,recovery.explicit_command,recovery.accepted,recovery.accepted&&recovery.executed,t);
    recovery.key.seq=0;collect_pending=1;collect_at=0;
}
static void collect(uint64_t t){
    struct reply r;uint8_t packet[32];struct key key={token,0,0,0};
    if(!collect_pending||t<collect_at||sequence==UINT32_MAX)return;collect_at=t+1000;
    key.seq=++sequence;header(packet,R5S_COLLECT,&key);
    if(!exchange(packet,sizeof(packet),&key,40,&r)&&r.status==ACK_OK&&!r.detail)collect_pending=0;
}
static void prepare(uint64_t want,unsigned n,unsigned explicit_command,uint64_t t){
    uint8_t packet[32+R5F_COMPACT];struct key key={token,0,n,0};struct reply r;uint32_t executed=0,accepted=0,cookie=0;
    if(sequence==UINT32_MAX||(n&&r5_filter_store_read(&catalog,n,packet+32))){finish(want,n,explicit_command,0,0,t);return;}
    key.seq=++sequence;if(n)key.digest=r5f_crc(packet+32,R5F_COMPACT);
    header(packet,R5S_PREPARE,&key);
    if(!exchange(packet,n?sizeof(packet):32,&key,1350,&r)){
        if((r.status==ACK_OK||r.status==ACK_ACCEPTED)&&r.detail&&r.detail<=R5S_COOKIE_MAX){
            cookie=r.detail;
            if(r.status==ACK_OK)native_submit(&key,cookie,&executed,&accepted);
            else accepted=1;
        }else if(r.status!=ACK_OK&&r.status!=ACK_ACCEPTED){
            finish(want,n,explicit_command,0,0,t);collect_pending=1;collect_at=0;return;
        }
    }
    if(!current())return;
    if(executed&&accepted){finish(want,n,explicit_command,1,1,t);collect_pending=1;collect_at=0;return;}
    recovery.key=key;recovery.want=want;recovery.cookie=cookie;recovery.executed=executed;recovery.accepted=accepted;
    recovery.explicit_command=explicit_command;retry_at=0;recover(t);
}
void r5_filter_service(void){
    uint64_t want,t;unsigned n,state,explicit_command;uint32_t busy=0;
    if(!current()||!CAS(&service_busy,&busy,1))return;
    if(now(clock_source(),&t))goto done;
    if(recovery.key.seq){recover(t);goto done;}
    state=LOAD(&command_state);if(state==4)goto done;
    want=LOAD(&desired);n=(unsigned)want;explicit_command=state==1;
    if(state==3||(!LOAD(&dirty)&&want==LOAD(&handled))){collect(t);goto done;}
    if(n>12||(n&&!(catalog.mask&(1u<<(n-1))))){finish(want,n,explicit_command,0,0,t);goto done;}
    if(attempted!=want){attempted=want;attempts=0;retry_at=0;}
    if(t<retry_at||attempts>=30){collect(t);goto done;}
    attempts++;
    if(synced&&n==r5_filter_selected())finish(want,n,explicit_command,1,1,t);
    else prepare(want,n,explicit_command,t);
done:STORE(&service_busy,0);
}
