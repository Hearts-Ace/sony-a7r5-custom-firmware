#include "r5_shutter_bridge_native.h"
#include "r5_sound_snapshot_wire.h"
#include "r5_runtime_session.h"
extern void *r5_stage411_dlsym(void *,const char *);
extern int r5_native_ap_send(void *,const uint8_t *,size_t);
extern uint32_t r5_osal_msg_size(const void *);
extern int *r5_ap_posix_errno(void);
extern void r5ss_original_pending(const void *,uint32_t *);
#define LOAD(p) __atomic_load_n((p),__ATOMIC_ACQUIRE)
#define STORE(p,v) __atomic_store_n((p),(v),__ATOMIC_RELEASE)
struct time437 {int64_t sec,ns;};
typedef int (*sleep_fn)(const void *,void *);
typedef int (*clock_fn)(int,struct time437 *);
static uint32_t phase,serial,tag,power,owner_power,owner_epoch,active,baseline,stop_ready;
static uint32_t arm_power,arm_epoch,arm_physical_lo,arm_physical_hi,arm_bytes;
static uint8_t inbox[R5SS_SNAPSHOT_REPLY_BYTES];
static uint32_t diag[R5SS_BRIDGE_DIAG_WORDS];
void r5ss_bridge_diagnostics(uint32_t out[R5SS_BRIDGE_DIAG_WORDS]){
 if(!out)return;out[0]=1;
 for(unsigned i=1;i<18;i++)out[i]=LOAD(&diag[i]);
 out[18]=LOAD(&phase);out[19]=LOAD(&serial);out[20]=LOAD(&tag);
}
static void reason(uint32_t value){STORE(&diag[1],value);}
/* Keep the21-word diagnostic wire layout. Only RPC attempts need a counter;
 * diag17 reports CP initial-registration rejects, not a CP boot witness.
 * Optional ACK/error counters stay zero. Admission, CRC/serial validation,
 * epoch checks and retirement decisions are independent of these diagnostics. */
static void count(unsigned ix){if(ix==4)__atomic_add_fetch(&diag[4],1,__ATOMIC_RELAXED);}
int r5ss_bridge_active(void){return active!=0;}
static uint32_t bridge_get(const uint8_t*p){return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void bridge_put(uint8_t*p,uint32_t x){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(x>>(i*8));}
/* Same CRC wire contract as CP; no CP implementation object is linked in AP. */
static uint32_t crc(const uint8_t*p,uint32_t n){uint32_t c=~0u;for(uint32_t i=0;i<n;i++)if(i<28||i>=32){c^=p[i];for(unsigned j=0;j<8;j++)c=(c>>1)^(0xedb88320u&-(c&1u));}return ~c;}
static int bridge_current(void){return LOAD(&power)==owner_power&&r5_session_current()&&r5_session_epoch()==owner_epoch;}
int r5ss_bridge_stop_ready(void){return stop_ready&&bridge_current();}
void r5ss_bridge_power(void){__atomic_add_fetch(&power,1,__ATOMIC_RELEASE);}
int r5ss_bridge_bind_epoch(uint32_t epoch){
 /* Rebinding keeps audio ownership, active/completion baseline and mailboxes.
  * The backend must subsequently verify its exact original registry extent. */
 if(!r5_session_current()||r5_session_epoch()!=epoch)return -1;
 owner_power=LOAD(&power);owner_epoch=epoch;stop_ready=0;return 0;
}
int r5ss_snapshot_inbound(const uint8_t*p,uint32_t source){
 if(!p)return 0;
 uint32_t n=r5_osal_msg_size(p);
 if(n<8||p[0]!=R5SS_SNAPSHOT_CLASS||bridge_get(p+4)!=R5SS_SNAPSHOT_MAGIC)return 0;
 if(source!=R5SS_SNAPSHOT_CP_QUEUE){count(8);return 0;}
 /* Consume every private envelope, including late/malformed ACKs. */
 uint32_t expected=0;
 if(!__atomic_compare_exchange_n(&phase,&expected,1,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)){count(7);return 1;}
 /* Holding phase1 prevents the worker replacing expected serial/tag between
  * validation and mailbox publication. A stale ACK cannot claim a new RPC. */
 if(n!=R5SS_SNAPSHOT_REPLY_BYTES||p[1]!=1||p[2]!=R5SS_SNAPSHOT_ACK||p[3]!=n||bridge_get(p+28)!=crc(p,n)){count(6);STORE(&phase,0);return 1;}
 if(bridge_get(p+8)!=LOAD(&serial)||bridge_get(p+12)!=LOAD(&tag)){count(7);STORE(&phase,0);return 1;}
 count(5);
 for(uint32_t i=0;i<n;i++)inbox[i]=p[i];
 STORE(&phase,2);return 1;
}
static int stamp(clock_fn clock,uint64_t*out){struct time437 t;if(clock(1,&t)||t.sec<0||t.ns<0||t.ns>=1000000000||(uint64_t)t.sec>(UINT64_MAX-999999999u)/1000000000u)return -1;*out=(uint64_t)t.sec*1000000000u+(uint64_t)t.ns;return 0;}
static int query(unsigned op,uint8_t*out,uint64_t physical,uint32_t bytes){
 clock_fn clock=(clock_fn)r5_stage411_dlsym(0,"clock_gettime");
 sleep_fn sleep=(sleep_fn)r5_stage411_dlsym(0,"nanosleep");
 uint64_t start,last,now;uint8_t p[32]={0};const struct time437 delay={0,1000000};
 STORE(&diag[2],op);STORE(&diag[3],0);STORE(&diag[15],0);count(4);
 if(!bridge_current()){reason(R5SS_Q_EPOCH);return -1;}
 if(!clock||!sleep){reason(R5SS_Q_SYMBOLS);return -1;}
 if(stamp(clock,&start)){reason(R5SS_Q_CLOCK);return -1;}
 uint32_t old=LOAD(&phase);do{if(old==1){reason(R5SS_Q_MAILBOX);return -1;}}while(!__atomic_compare_exchange_n(&phase,&old,3,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE));
 /* First RPC gets a 64-bit monotonic-clock-derived tag/serial; each later
  * RPC increments without wrap. Power epochs also invalidate a waiting RPC. */
 if(!LOAD(&tag)){uint32_t next=(uint32_t)(start>>32)^owner_power^0x53535731u;STORE(&tag,next?next:1);STORE(&serial,(uint32_t)start==UINT32_MAX?0:(uint32_t)start);}
 if(serial==UINT32_MAX){reason(R5SS_Q_SERIAL);return -1;}
 STORE(&serial,serial+1);p[0]=R5SS_SNAPSHOT_CLASS;p[1]=1;p[2]=(uint8_t)op;p[3]=32;
 bridge_put(p+4,R5SS_SNAPSHOT_MAGIC);bridge_put(p+8,serial);bridge_put(p+12,LOAD(&tag));if(op==2)bridge_put(p+16,baseline);if(op==3){bridge_put(p+16,(uint32_t)physical);bridge_put(p+20,(uint32_t)(physical>>32));bridge_put(p+24,bytes);}bridge_put(p+28,crc(p,32));
 STORE(&phase,0);last=start;
 int sent=r5_native_ap_send(0,p,32);STORE(&diag[3],(uint32_t)sent);
 if(sent){reason(R5SS_Q_SEND);goto fail;}
 for(unsigned i=0;i<201;i++){
  if(!bridge_current()){reason(R5SS_Q_EPOCH);goto fail;}
  if(stamp(clock,&now)||now<last||now<start){reason(R5SS_Q_CLOCK_CHANGED);goto fail;}
  STORE(&diag[15],(uint32_t)((now-start)/1000000u));
  if(now-start>=200000000u){count(9);reason(R5SS_Q_TIMEOUT);goto fail;}last=now;
  if(LOAD(&phase)==2){
   for(unsigned j=0;j<R5SS_SNAPSHOT_REPLY_BYTES;j++)out[j]=inbox[j];STORE(&phase,3);
   static const uint8_t fields[7][2]={{10,60},{11,184},{12,32},{13,176},{14,180},{16,56},{17,52}};
   for(unsigned j=0;j<7;j++)STORE(&diag[fields[j][0]],bridge_get(out+fields[j][1]));
   if(!bridge_current()){reason(R5SS_Q_EPOCH);return -1;}
   if(bridge_get(out+56)!=R5SS_SNAPSHOT_FIELD_COUNT){reason(R5SS_Q_FIELDS);return -1;}
   reason(R5SS_Q_OK);return 0;
  }
  if(i==200){count(9);reason(R5SS_Q_TIMEOUT);goto fail;}
  if(sleep(&delay,0)){int *error=r5_ap_posix_errno();if(!error||*error!=4){reason(R5SS_Q_SLEEP);goto fail;}}
 }
fail:
 old=LOAD(&phase);while(old!=1&&!__atomic_compare_exchange_n(&phase,&old,3,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)){}
 return -1;
}
int r5ss_native_first_owner17(uint32_t*token){
 uint8_t p[R5SS_SNAPSHOT_REPLY_BYTES];if(!token||active){reason(R5SS_Q_ACTIVE);return -1;}
 /* Only this read-only, unowned first query may be retried. Later owner,
  * Start and retirement queries retain their conservative negative result. */
 if(query(1,p,0,0))return 2;
 if(bridge_get(p+60)!=1){count(17);reason(R5SS_Q_REGISTRY);return -1;}
 if(bridge_get(p+184)!=1){reason(R5SS_Q_BUSY);return 1;}
 *token=LOAD(&tag);return 0;
}
int r5ss_native_owner_check17(uint64_t physical,uint32_t bytes){
 uint8_t p[R5SS_SNAPSHOT_REPLY_BYTES];if(!physical||!bytes||query(1,p,0,0))return -1;
 uint64_t actual=(uint64_t)bridge_get(p+160)|((uint64_t)bridge_get(p+164)<<32);
 return bridge_get(p+60)==2&&bridge_get(p+188)==1&&actual==physical&&bridge_get(p+168)==bytes?0:-1;
}
int r5ss_native_start_arm17(void){
 uint8_t p[R5SS_SNAPSHOT_REPLY_BYTES];if(active)return 1;if(query(1,p,0,0))return -1;
 /* Only our worker can submit kind17; no original beeplist entry uses it. */
 /* Native actor/admission words, valid packet opcodes, specific Stop kinds
  * and MMIO must be idle. 198AD88..8B include persistent native mode bytes;
  * those are not pending work and must not permanently block admission. */
 if((bridge_get(p+32)&0x003f0fffu)||bridge_get(p+176)||bridge_get(p+180))return 1;
 if(bridge_get(p+60)!=2||bridge_get(p+188)!=1)return -1;
 arm_power=owner_power;arm_epoch=owner_epoch;
 arm_physical_lo=bridge_get(p+160);arm_physical_hi=bridge_get(p+164);arm_bytes=bridge_get(p+168);
 baseline=bridge_get(p+152);stop_ready=0;active=1;return 0;
}
int r5ss_native_retirement_poll(uint32_t kind){
 stop_ready=0;
 if(kind!=17||!bridge_current())return -1;
 if(!active)return 0;
 uint32_t pending_before=~0u,pending_after=~0u;
 r5ss_original_pending(0,&pending_before);
 uint8_t p[R5SS_SNAPSHOT_REPLY_BYTES];if(query(2,p,0,0))return -1;
 r5ss_original_pending(0,&pending_after);
 if(!bridge_current())return -1;
 if(bridge_get(p+48)==R5SS_RETIREMENT_RETIRED){active=0;return 0;}
 /* Async Start increments the original pending counter before enqueue. The
  * original public1329 collector decrements it only after the native reply,
  * including admission rejection (which has no kind17 cleanup witness).
  * Zero on both sides of a stable, completely idle CP observation proves all
  * native async work drained. Never infer this from CP zeros alone, or reuse
  * a possibly reset counter after a power/session change. Persistent native
  * mode bytes are excluded exactly as in Start admission above. */
 if(arm_power==owner_power&&arm_epoch==owner_epoch&&!pending_before&&!pending_after&&
    !(bridge_get(p+32)&0x003f0fffu)&&!bridge_get(p+36)&&bridge_get(p+40)==1&&
    !bridge_get(p+176)&&!bridge_get(p+180)&&bridge_get(p+60)==2&&bridge_get(p+188)==1&&
    bridge_get(p+160)==arm_physical_lo&&bridge_get(p+164)==arm_physical_hi&&
    bridge_get(p+168)==arm_bytes){active=0;return 0;}
 /* Queued/deferred cancellation can bypass native common cleanup. Stop only
  * after both snapshots show our kind17 as the actual bridge_current sound. Pending
  * packets wait for native admission or completion without forced removal. */
 stop_ready=(bridge_get(p+176)&bridge_get(p+180)&1u)!=0;
 /* Unknown with no later completion is expected while the sound is active. */
 return 1;
}

int r5ss_native_gain_bind17(uint64_t physical,uint32_t bytes){
 uint8_t p[R5SS_SNAPSHOT_REPLY_BYTES];if(!physical||!bytes||active||query(3,p,physical,bytes))return -1;
 uint64_t actual=(uint64_t)bridge_get(p+160)|((uint64_t)bridge_get(p+164)<<32);
 return bridge_get(p+184)==1&&bridge_get(p+188)==1&&bridge_get(p+60)==2&&actual==physical&&bridge_get(p+168)==bytes?0:-1;
}

int r5ss_native_resume_check17(uint64_t physical,uint32_t bytes,uint32_t *registered){
 extern void r5ss_original_pending(const void *,uint32_t *);
 uint32_t before=~0u,after=~0u;uint8_t p[R5SS_SNAPSHOT_REPLY_BYTES];
 if(!registered||!bridge_current())return -1;
 /* A CP-empty snapshot is not proof that an old AP async Start completed.
  * Preserve that baseline, including across power/epoch rebind. */
 if(active){int state=r5ss_native_retirement_poll(17);if(state)return state;}
 r5ss_original_pending(0,&before);if(before)return 1;
 if(query(1,p,0,0))return -1;
 r5ss_original_pending(0,&after);if(!bridge_current())return -1;
 if(after||bridge_get(p+40)!=1||(bridge_get(p+32)&0x003f0fffu)||
    bridge_get(p+176)||bridge_get(p+180))return 1;
 if(bridge_get(p+52)&7u)return -1;
 if(bridge_get(p+60)==1&&bridge_get(p+184)==1){*registered=0;return 0;}
 uint64_t actual=(uint64_t)bridge_get(p+160)|((uint64_t)bridge_get(p+164)<<32);
 if(!physical||!bytes||bridge_get(p+60)!=2||bridge_get(p+188)!=1||
    actual!=physical||bridge_get(p+168)!=bytes)return -1;
 *registered=1;return 0;
}
