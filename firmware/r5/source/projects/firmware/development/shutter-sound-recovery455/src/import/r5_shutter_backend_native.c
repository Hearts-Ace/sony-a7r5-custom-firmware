#include "r5_shutter_backend.h"
#include "r5_shutter_ap.h"
#include "r5sound_runtime.h"
extern int r5ss_native_gain_bind17(uint64_t,uint32_t);
extern uint32_t r5ss_native_signals_get(void);

/* Required real transport bridge, supplied by the AP importer. It must read
 * the CP agent's complete native actor/queue/SYSND snapshot after synchronous
 * START ACK. 033D alone has NOT been proven to cover queued/stopping states.
 * 0=verified retired; 1=pending/queued/active/stopping; negative=unknown. */
extern int r5ss_native_retirement_poll(uint32_t kind);
/* Real op1 snapshot ACK, captured immediately before synchronous START.
 * It records completion baseline and arms localactive before native admission.
 * 0=armed; 1=RPC pending/unaccepted; negative=unknown. */
extern int r5ss_native_start_arm17(void);
extern int r5ss_bridge_stop_ready(void);
/* Warm registry physical+bytes must still match our owned lease. Real ACK:
 * 0=match;1=pending;negative=absent/mismatch/unknown (including CP reset). */
extern int r5ss_native_owner_check17(uint64_t physical,uint32_t encoded_bytes);
extern int r5ss_native_resume_check17(uint64_t,uint32_t,uint32_t *);

static int bad(r5ss_native_backend *b,uint32_t why){
 b->fault=why;return R5SS_NATIVE;
}
static int extent(const r5ss_dmm_extent *e,uint32_t side){
 return e->status==0&&e->id==0x70817u&&e->handle>=0&&
        !!((uint32_t)e->handle&0x8000u)==!!side&&e->physical!=0&&
        e->bytes==R5SS_NATIVE_CAPACITY&&!e->reserved&&
        e->physical<=UINT64_MAX-e->bytes;
}
static int drop_ap(r5ss_native_backend *b){
 uint32_t status=~0u;
 if(b->mapped){
  const r5ss_mem_unmap_request r={b->map.map_base,b->map.map_bytes,b->map.fd};
  r5ss_native_mem_unmap(&r,&status);b->last_native=status;
  if(status){b->cleanup_fault=0x31u;b->cleanup_native=status;return bad(b,0x31u);}
  b->mapped=0;
 }
 if(b->ap_owned){
  const r5ss_dmm_release_request r={(uint32_t)b->ap.handle};status=~0u;
  r5ss_native_dmm_release(&r,&status);b->last_native=status;
  if(status){b->cleanup_fault=0x32u;b->cleanup_native=status;return bad(b,0x32u);}
  b->ap_owned=0;
 }
 return R5SS_OK;
}
static int fail_import(r5ss_native_backend *b,uint32_t why){
 /* CP lease is deliberately retained. An ACK failure must never free data
  * that a native registry/transfer could still reference. Cleanup has a
  * separate diagnostic: successful unmap/release must not erase the first
  * native failure, and a cleanup failure must not replace its identity. */
 uint32_t native=b->last_native;
 (void)drop_ap(b);b->last_native=native;return bad(b,why);
}
int r5ss_backend_session(r5ss_native_backend *b,uint32_t witness){
 if(!b||!witness)return R5SS_INVALID;
 if(b->session_witness==witness)return b->fault?R5SS_NATIVE:R5SS_OK;
 uint32_t abandoned=b->abandoned+(b->cp_owned||b->ap_owned||b->mapped||b->registered);
 *b=(r5ss_native_backend){0};
 b->session_witness=witness;b->abandoned=abandoned;
 return R5SS_OK;
}
int r5ss_backend_first_authorize(r5ss_native_backend *b,uint32_t token){
 if(!b||!token||b->session_witness||b->cp_owned||b->ap_owned||b->registered||b->mapped)
  return R5SS_INVALID;
 b->session_witness=token;return R5SS_OK;
}
/* Original AP352135C is a generic synchronous IPC wrapper. CP DMM cmd28
 * GetUnitInfo and cmd2A Open(mode1001) only observe; no Share/Open/Close or
 * stale numeric Release occurs. Both replies must describe the same lease.
 * Return1 only when BOTH stock queries report unused/stale generation. */
static int resume_lease(r5ss_native_backend *b){
 int stale=0;
 for(uint32_t command=0x28u;command<=0x2au;command+=2){
  uint32_t request[10]={0},reply[10]={0};
  request[0]=command;request[2]=(uint32_t)b->cp.handle;
  r5ss_native_sysnd_command(0x9061003cu,request,sizeof request,reply,
                           command==0x28u?24u:40u);
  int status=(int16_t)(reply[0]>>16);
  if((reply[0]&0xffffu)!=(command|0x8000u)||(reply[1]>>16))return -1;
  if(status){
   b->last_native=(uint32_t)status;
   if(status!=-5&&status!=-1)return -1;
   if(command==0x28u)stale=status;
   else if(stale!=status)return -1;
  }else{
   if(stale||(reply[2]&0xffffu)!=1u)return -1;
   if(command==0x28u){
    if(!(reply[2]>>16)||(reply[2]>>16)>255u||!(reply[3]&0xffffu)||
       (reply[3]&0xffffu)>255u||reply[4]!=R5SS_NATIVE_CAPACITY||reply[5]!=0x70817u)return -1;
   }else if(reply[3]!=(uint32_t)b->cp.handle||reply[6]!=(uint32_t)b->cp.physical||
       reply[7]!=(uint32_t)(b->cp.physical>>32)||reply[8]!=R5SS_NATIVE_CAPACITY)return -1;
  }
 }
 return stale?1:0;
}
int r5ss_backend_resume(r5ss_native_backend *b){
 if(!b)return R5SS_INVALID;
 if(!b->session_witness){
  if(b->cp_owned||b->ap_owned||b->mapped||b->registered||b->fault)return R5SS_INVALID;
  uint32_t registered=0;return r5ss_native_resume_check17(0,0,&registered);
 }
 /* A failed AP unmap/release needs independent ownership evidence. Retained
  * pointers and an AP epoch cannot authorize retrying those old operations. */
 if(b->mapped||b->ap_owned||b->cleanup_fault)return bad(b,0x81u);
 if(b->cp_owned&&!extent(&b->cp,1))return bad(b,0x82u);
 uint32_t registered=0;
 int state=r5ss_native_resume_check17(b->cp_owned?b->cp.physical:0,
                                     b->installed_bytes,&registered);
 if(state)return state<0?bad(b,0x83u):state;
 int stale=b->cp_owned?resume_lease(b):0;
 if(stale<0)return bad(b,0x82u);
 /* Queries can block across a power notification. Recheck current epoch,
  * pending requests and exact registry immediately before any mutation. */
 state=r5ss_native_resume_check17(b->cp_owned?b->cp.physical:0,
                                 b->installed_bytes,&registered);
 if(state)return state<0?bad(b,0x83u):state;
 if(registered){
  r5ss_table_request remove={0};uint32_t status=~0u;remove.kind=R5SS_NATIVE_KIND;
  r5ss_native_set_table(&remove,&status);b->last_native=status;
  if(status)return bad(b,0x84u);
 }
 b->registered=0;b->installed_generation=0;b->installed_bytes=0;
 if(stale){b->cp_owned=0;b->cp=(r5ss_dmm_extent){0};b->abandoned++;}
 b->encoded=0;b->offered_generation=0;b->encoded_bytes=0;b->padded_bytes=0;
 b->fault=0;b->last_native=0;return R5SS_OK;
}
int r5ss_backend_stage(r5ss_native_backend *b,uint32_t generation,
                       const uint8_t *encoded,uint32_t bytes,uint32_t padded,
                       uint32_t volume){
 if(!b||!generation||!encoded||!bytes||bytes>R5SS_NATIVE_MAX_ENCODED||
    padded!=bytes+R5SS_NATIVE_GUARD||padded>R5SS_NATIVE_CAPACITY||(volume<1u||volume>10u))
  return R5SS_INVALID;
 if(!b->session_witness||b->fault)return R5SS_NATIVE;
 if((uintptr_t)encoded>UINTPTR_MAX-padded)return R5SS_INVALID;
 for(uint32_t i=bytes;i<padded;i++)if(encoded[i])return R5SS_INVALID;
 b->offered_generation=generation;b->encoded=encoded;
 b->encoded_bytes=bytes;b->padded_bytes=padded;b->volume_step=volume;
 return R5SS_OK;
}
int r5ss_backend_poll(void *ctx){
 r5ss_native_backend *b=ctx;
 if(!b||!b->session_witness||b->fault)return R5SS_NATIVE;
 /* A proven fresh CP session has no custom kind17 yet. Afterwards use the
  * real native-state snapshot, even when our table has been unregistered. */
 if(!b->cp_owned&&!b->registered)return 0;
 if(b->registered){
  int owner=r5ss_native_owner_check17(b->cp.physical,b->installed_bytes);
  if(owner)return owner<0?R5SS_NATIVE:1;
 }
 int r=r5ss_native_retirement_poll(R5SS_NATIVE_KIND);
 return r<0?R5SS_NATIVE:r?1:0;
}
int r5ss_backend_stop(void *ctx){
 r5ss_native_backend *b=ctx;
 if(!b||!b->session_witness||b->fault)return R5SS_NATIVE;
 if(!b->registered)return R5SS_OK;
 if(!r5ss_bridge_stop_ready())return R5SS_BUSY;
 /* Same public0329 route as native Start, operation2 for Stop. Public032A
  * is per-kind gain, not Stop: its successful ACK never retires playback.
  * Derive this packet from the original Start wrapper; keep its synchronous
  * RPC/return conversion and leave CP admission/cleanup entirely native. */
 const uint8_t request[16]={0x0d,0x20,0x29,0x03,0x10,0,1,0x80,
                            2,0,R5SS_NATIVE_KIND,0,0,0,0,0};
 uint32_t reply[3]={0};
 r5ss_native_sysnd_command(0x92840747u,request,sizeof request,reply,sizeof reply);
 uint32_t status=r5ss_native_sysnd_result(reply[2]);b->last_native=status;
 if(status)return bad(b,0x41u);
 b->stops++;
 /* This is the synchronous STOP-command ACK; retirement still requires
  * poll. In particular do not release the CP lease here. */
 return R5SS_OK;
}
int r5ss_backend_install(void *ctx,uint32_t generation){
 r5ss_native_backend *b=ctx;
 if(!b||!b->session_witness||b->fault)return R5SS_NATIVE;
 if(b->installed_generation==generation&&b->registered)return R5SS_OK;
 if(generation!=b->offered_generation||!b->encoded)return R5SS_INVALID;
 int state=r5ss_backend_poll(b);
 if(state)return state<0?state:R5SS_BUSY;
 uint32_t status=~0u;
 if(b->registered){
  r5ss_table_request remove={0};remove.kind=R5SS_NATIVE_KIND;
  r5ss_native_set_table(&remove,&status);b->last_native=status;
  if(status)return bad(b,0x51u);
  b->registered=0;b->installed_generation=0;b->installed_bytes=0;
 }
 r5ss_dmm_claim_request claim={0x70817u,0};
 r5ss_native_dmm_claim(&claim,&b->ap);b->last_native=b->ap.status;
 if(!extent(&b->ap,0))return bad(b,0x52u);
 b->ap_owned=1;
 if(!b->cp_owned){
  claim.side=1;
  r5ss_native_dmm_claim(&claim,&b->cp);b->last_native=b->cp.status;
  if(!extent(&b->cp,1))return fail_import(b,0x53u);
  b->cp_owned=1;
 }
 const r5ss_mem_map_request map={"/dev/mem",b->ap.physical,b->ap.bytes,0,{0,0,0}};
 r5ss_native_mem_map(&map,&b->map);b->last_native=b->map.status;
 b->mapped=!b->map.status&&b->map.fd>=0;
 if(b->map.status||b->map.fd<0||!b->map.view||!b->map.map_base||
    b->map.view==(void *)(uintptr_t)UINTPTR_MAX||
    b->map.map_base==(void *)(uintptr_t)UINTPTR_MAX||
    b->map.view_bytes<b->padded_bytes||!b->map.map_bytes)
  return fail_import(b,0x54u);
 uintptr_t start=(uintptr_t)b->map.map_base,view=(uintptr_t)b->map.view;
 if(start>UINTPTR_MAX-b->map.map_bytes||view<start||
    view>start+b->map.map_bytes||b->padded_bytes>start+b->map.map_bytes-view)
  return fail_import(b,0x55u);
 /* Root owns and pins the immutable staging; only AP temporary DMM mapping
  * is written. Native copy uses actual handles and no fixed physical base. */
 volatile uint8_t *dst=(volatile uint8_t *)b->map.view;
 for(uint32_t i=0;i<b->padded_bytes;i++)dst[i]=b->encoded[i];
 const r5ss_native_copy_request copy={(uint32_t)b->ap.handle,0,
                                     (uint32_t)b->cp.handle,0,b->padded_bytes};
 status=~0u;r5ss_native_copy(&copy,&status);b->last_native=status;
 if(status)return fail_import(b,0x56u);
 if(drop_ap(b))return R5SS_NATIVE;
 r5ss_table_request table={0};table.enabled=1;table.kind=R5SS_NATIVE_KIND;
 table.physical=b->cp.physical;table.bytes=b->encoded_bytes;table.priority=6;
 status=~0u;r5ss_native_set_table(&table,&status);b->last_native=status;
 if(status)return bad(b,0x57u);
 b->registered=1;b->installed_generation=generation;
 b->installed_bytes=b->encoded_bytes;
 /* Register ACK alone is insufficient: bind the exact descriptor to the
  * CP's guarded gain adapter before any native Start may use this bank. */
 if(r5ss_native_gain_bind17(b->cp.physical,b->installed_bytes))return bad(b,0x58u);
 b->imports++;
 /* Native copy and table registration are complete. Playback retains only
  * the owned CP extent, never AP conversion malloc storage. */
 b->encoded=0;
 return R5SS_OK;
}
int r5ss_backend_unload(r5ss_native_backend *b){
 if(!b||!b->session_witness||b->fault)return R5SS_NATIVE;
 /* poll authenticates exact registry physical/length before any remove.
  * The bridge proves native completion or async reply drain together with
  * actor/pending/MMIO retirement before releasing the extent.
  * Unknown/failed native state retains the lease; no forced free. */
 int state=r5ss_backend_poll(b);if(state)return state<0?state:R5SS_BUSY;
 uint32_t status=~0u;
 if(b->registered){
  r5ss_table_request remove={0};remove.kind=R5SS_NATIVE_KIND;
  r5ss_native_set_table(&remove,&status);b->last_native=status;
  if(status)return bad(b,0x71u);
  b->registered=0;b->installed_generation=0;b->installed_bytes=0;
 }
 if(drop_ap(b))return R5SS_NATIVE;
 if(b->cp_owned){
  const r5ss_dmm_release_request r={(uint32_t)b->cp.handle};status=~0u;
  r5ss_native_dmm_release(&r,&status);b->last_native=status;
  if(status)return bad(b,0x72u);
  b->cp_owned=0;b->cp=(r5ss_dmm_extent){0};
 }
 b->encoded=0;b->offered_generation=0;b->encoded_bytes=0;b->padded_bytes=0;
 return R5SS_OK;
}
int r5ss_backend_start(void *ctx,uint32_t generation,uint32_t serial){
 r5ss_native_backend *b=ctx;(void)serial;
 if(!b||!b->session_witness||b->fault||!b->registered||
    b->installed_generation!=generation)return R5SS_NATIVE;
 /* Recheck the same worker policy immediately before native admission. This
  * shares the mute/volume guard and catches signals-off after authorize. */
 int allowed=r5ss_backend_authorize(b);
 if(allowed<0)return allowed;
 if(!allowed)return R5SS_BUSY;
 int state=r5ss_backend_poll(b);
 if(state)return state<0?state:R5SS_BUSY;
 int armed=r5ss_native_start_arm17();
 if(armed)return armed<0?bad(b,0x62u):R5SS_BUSY;
 /* The original synchronous Start replies from native completion, not
  * admission. Waiting here prevents this same worker from sending Stop for
  * the next exposure. Use the original one-shot async branch (byte9=0).
  * Its return proves enqueue only: the armed bridge retains ownership until
  * native completion or reply drain and actor/packet/MMIO checks pass. */
 const uint32_t request[3]={R5SS_NATIVE_KIND,0,0};
 int32_t status=-1;r5ss_native_sysnd_start(request,&status);
 b->last_native=(uint32_t)status;
 if(status)return bad(b,0x61u);
 b->starts++;return R5SS_OK;
}
int r5ss_backend_authorize(void *ctx){
 r5ss_native_backend *b=ctx;r5ss_native_policy policy;
 if(!b||!b->session_witness||b->fault||r5ss_native_gate(&policy))return R5SS_NATIVE;
 return policy.audible&&r5ss_native_signals_get()<3u&&
        r5sound_volume_get()==b->volume_step?1:0;
}
r5ss_ops r5ss_backend_ops(r5ss_native_backend *b){
 return (r5ss_ops){b,r5ss_backend_poll,r5ss_backend_stop,
                   r5ss_backend_authorize,r5ss_backend_install,r5ss_backend_start};
}
