/* One filesystem worker, shared with the 4.36 filter service. Event callbacks
 * only publish atomic metadata. Import never calls any audio/CP interface. */
#include "r5sound_runtime.h"
#include "r5sound_catalog.h"
#include "r5sound_store.h"
#include "r5sound_scan.h"
#include "r5_shutter_backend.h"
#include "r5_shutter_bridge_native.h"
#include "r5_shutter_ap.h"
#include "r5_runtime_session.h"
#include "r5sound_package.h"
#include <string.h>
extern void *r5_stage411_dlsym(void *,const char *);
extern int r5_native_fsys_open(const char *,uint32_t,uint64_t *);
extern int r5_native_fsys_read(uint64_t,void *,uint64_t,uint64_t *);
extern int r5_native_fsys_close(uint64_t);
extern int r5_native_fsys_find_first(const char *,void *);
extern int r5_native_fsys_find_next(void *);
extern uint32_t r5_osal_msg_size(const void *);
extern void r5sound_menu_catalog_changed(void);
#define LOAD(p) __atomic_load_n((p),__ATOMIC_ACQUIRE)
#define STORE(p,v) __atomic_store_n((p),(v),__ATOMIC_RELEASE)
static struct {
 r5sound_catalog catalog;
 uint32_t published,selected,request,status,initial[2],completed[2],media[2];
 uint32_t epoch,token,desired,changing,attempts,retry,generation,fault,volume,last_start,last_stop,logged_play,logged_stop,step,target_step,revision,volume_request,logged_done,seen_exposures,logged_gate,persisted,resuming,restoring;
 void *(*alloc)(size_t);void (*free)(void *);
 uint8_t *audio;uint32_t encoded_bytes;
 r5ss_scheduler scheduler;r5ss_native_backend backend;
} run;
enum {S_READY,S_SCAN,S_SCAN_ERROR,S_REQUEST,S_LOADING,S_ACTIVE,S_OFF,S_QUERY,S_REGISTER,S_SAVE_ERROR,S_BOOT_ERROR,S_POLICY,S_PLAY_ERROR};
unsigned r5sound_volume_get(void){unsigned s=LOAD(&run.step);return s?s:5;}
unsigned r5sound_revision(void){return LOAD(&run.revision);}
int r5sound_volume_blocked(void){return !LOAD(&run.published)||!LOAD(&run.selected)||LOAD(&run.request)||LOAD(&run.resuming)||run.fault;}
int r5sound_volume_enqueue(unsigned step){
 if(step<1||step>10||r5sound_volume_blocked())return -1;
 uint32_t z=0;if(!__atomic_compare_exchange_n(&run.request,&z,0x100u|step,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))return 1;
 return 0;
}
unsigned r5sound_count(void){return LOAD(&run.published)?run.catalog.count:0;}
const char*r5sound_name(unsigned i){return i&&i<=r5sound_count()?run.catalog.entries[i-1].name:0;}
unsigned r5sound_selected(void){return LOAD(&run.selected);}
const char*r5sound_status(void){
 if(LOAD(&run.request)||LOAD(&run.resuming))return "正在启用";
 switch(LOAD(&run.status)){
 case S_SCAN:return "正在导入声音包";
 
 case S_REQUEST:case S_LOADING:return "正在启用";
 case S_ACTIVE:return "已启用";
 case S_OFF:return "已关闭";
 case S_SCAN_ERROR:case S_QUERY:case S_REGISTER:case S_SAVE_ERROR:case S_BOOT_ERROR:case S_POLICY:case S_PLAY_ERROR:return "失败：详见R5SOUND.LOG";
 
 
 
 
 
 
 default:return "冷启动导入声音包";
 }
}
int r5sound_request(unsigned i){
 if(LOAD(&run.resuming))return 1;
 if(!LOAD(&run.published)||i>run.catalog.count||run.fault)return -1;
 uint32_t z=0;if(!__atomic_compare_exchange_n(&run.request,&z,i+1,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))return 1;
 return 0;
}
void r5sound_initial(uint32_t a,uint32_t b){STORE(&run.initial[0],a);STORE(&run.initial[1],b);}
void r5sound_completed(uint32_t slot){if(slot<2)STORE(&run.completed[slot],1);}
void r5sound_media(uint32_t slot,uint32_t status,uint32_t drive){if(slot<2)STORE(&run.media[slot],!status&&drive>='A'&&drive<='Z'?0x100u|drive:0);}
void r5sound_power(const uint32_t*m){if(m&&(m[0]==0x920143u||m[0]==0x92015au))r5ss_bridge_power();}
void r5sound_inbound(const uint8_t*p,uint32_t source){
 if(!run.token||run.fault||!r5_session_current())return;
 r5ss_exposure e;if(r5ss_parse_exposure(p,r5_osal_msg_size(p),source,&e)){__atomic_add_fetch(&run.seen_exposures,1,__ATOMIC_RELEASE);(void)r5ss_expose(&run.scheduler,e);}
}
static unsigned drive(void){for(unsigned i=0;i<2;i++){uint32_t v=LOAD(&run.media[i]);if(v&0x100u)return v&255u;}return 0;}
static void logit(const char*stage,const char*name,int rc,const uint32_t*v,unsigned n){r5sound_log(drive(),stage,name,rc,v,n);}
static void storage_log(void*c,const char*stage,const char*name,int rc,uint32_t a,uint32_t b){(void)c;uint32_t v[2]={a,b};logit(stage,name,rc,v,2);}
static int directory(struct r5_lut_directory*d,r5sound_storage*s){
 struct r5_lut_directory_api a;memset(d,0,sizeof(*d));
 /* The unchanged 4.36 mount verifier needs a complete <=64KiB snapshot.
  * It is temporary metadata storage, never a whole sound-bank buffer. */
 uint8_t*scratch=run.alloc(65537);if(!scratch)return -1;
 int rc=r5_native_lut_directory_api_init(&a);
 if(!rc)rc=r5_lut_directory_acquire(d,&a,scratch,65537);
 run.free(scratch);if(rc){if(d->phase==2)(void)r5_lut_directory_release(d);return -1;}
 r5sound_storage_bind(s,d);uintptr_t log=(uintptr_t)storage_log;__asm__ volatile("" : "+r"(log));s->log=(void*)log;return 0;
}
struct scan_context {r5sound_storage*s;r5sound_catalog**c;unsigned card;uint32_t media;};
static int scan_current(void*p){struct scan_context*c=p;return r5_session_current()&&LOAD(&run.media[c->card])==c->media;}
static int visit(void*p,const char*name,size_t nb,uint64_t expected,uint8_t attr){
 struct scan_context*c=p;(void)attr;uint32_t info[2]={(uint32_t)expected,c->card};logit("PACKAGE_FOUND",name,0,info,2);
 int rc=0;uint8_t*package=0;
 if(!scan_current(c)||!ss_valid_name(name,nb))return R5SOUND_IO;
 if(expected<R5SOUND_PACKAGE_HEADER_BYTES+320u||expected>R5SOUND_PACKAGE_MAX_BYTES){logit("PACKAGE_SIZE_REJECT",name,-1,info,2);goto done;}
 package=run.alloc((size_t)expected);if(!package){logit("PACKAGE_ALLOC_FAILED",name,-1,info,2);rc=R5SOUND_IO;goto done;}
 char path[260];path[0]=(char)(c->media&255u);path[1]=':';path[2]='/';memcpy(path+3,name,nb);path[nb+3]=0;
 uint64_t h=0;rc=r5_native_fsys_open(path,1,&h);size_t used=0;
 if(rc){logit("PACKAGE_OPEN_FAILED",name,rc,info,2);rc=R5SOUND_IO;goto done;}
 while(used<(size_t)expected){uint64_t got=0;size_t n=(size_t)expected-used;if(n>65536)n=65536;
  rc=r5_native_fsys_read(h,package+used,n,&got);if(rc||got>n||!scan_current(c)){rc=-1;break;}used+=(size_t)got;if(!got)break;}
 if(!rc&&used==(size_t)expected){uint8_t tail;uint64_t got=0;rc=r5_native_fsys_read(h,&tail,1,&got);if(got||!scan_current(c))rc=-1;}
 if(r5_native_fsys_close(h))rc=-1;
 if(rc||used!=(size_t)expected){logit("PACKAGE_READ_FAILED",name,rc?rc:-1,info,2);rc=R5SOUND_IO;goto done;}
 if(!*c->c){*c->c=run.alloc(sizeof(**c->c));if(!*c->c){rc=R5SOUND_IO;goto done;}memset(*c->c,0,sizeof(**c->c));}
 rc=r5sound_catalog_add(c->s,*c->c,c->card,name,nb,package,used);
 if(rc==R5SOUND_BAD){logit("PACKAGE_FORMAT_REJECT",name,rc,info,2);rc=0;}
done:
 if(package)run.free(package);
 if(!r5sound_worker_yield()||!scan_current(c))return R5SOUND_IO;
 return rc;
}
void r5sound_boot(void){
 /* Called after filter startup in the same filesystem worker. No audio
  * service call, conversion or playback allocation occurs in this function. */
 if(!r5_session_current())return;
 if(!run.alloc){run.alloc=(void*)r5_stage411_dlsym(0,"malloc");run.free=(void*)r5_stage411_dlsym(0,"free");}
 if(!run.alloc||!run.free){STORE(&run.status,S_BOOT_ERROR);return;}
 if(LOAD(&run.published))return; /* retained resume: never scan/rewrite SD */
 uint8_t scratch[R5SOUND_INDEX_BYTES];r5sound_catalog*c=0;
 struct r5_lut_directory d;r5sound_storage s;int rc=-1;unsigned selected=0;
 if(directory(&d,&s))goto done;
 logit("BUILD_R5S441_REPAINT",0,0,0,0);
 rc=r5sound_catalog_load(&s,&run.catalog,scratch,sizeof scratch);
 if(rc<0){logit("CATALOG_LOAD_FAILED",0,rc,0,0);memset(&run.catalog,0,sizeof run.catalog);}
 if(r5_session_cold_start()){
  STORE(&run.status,S_SCAN);int failed=0,scanned=0;
  for(unsigned card=0;card<2;card++){
   uint32_t media=LOAD(&run.media[card]);if(!(media&0x100u)){if(LOAD(&run.initial[card])-1u<2u){failed=1;logit("CARD_NOT_READY",0,-1,&card,1);}continue;}
   /* Only source-bound completed media can be scanned. A late/unready slot
    * prevents a partial replacement, while the previous catalog stays usable. */
   if(!LOAD(&run.completed[card])){failed=1;logit("CARD_SCAN_NOT_READY",0,-1,&card,1);continue;}
   struct scan_context ctx={&s,&c,card,media};uint64_t fileinfo[512];struct r5sound_scan_result result;
   uintptr_t a=(uintptr_t)r5_native_fsys_find_first,b=(uintptr_t)r5_native_fsys_find_next,x=(uintptr_t)scan_current;
   __asm__ volatile("" : "+r"(a),"+r"(b),"+r"(x));struct r5sound_scan_api api={(void*)a,(void*)b,(void*)x,&ctx};
   logit("SCAN_BEGIN",0,0,&card,1);int scan=r5sound_scan_root(&api,(char)(media&255u),fileinfo,sizeof fileinfo,visit,&ctx,&result);
   uint32_t values[7]={card,result.entries,result.packages,result.unsafe,(uint32_t)result.native_status,(uint32_t)result.visitor_status,c?c->count:0};logit("SCAN_END",0,scan,values,7);scanned++;
   if(scan)failed=1;
  }
  if(!failed&&scanned&&c&&c->count&&r5_session_current()){rc=r5sound_catalog_publish(&s,c,&run.catalog,scratch,sizeof scratch);if(!rc)run.catalog=*c;else failed=1;}
  if(failed)STORE(&run.status,S_SCAN_ERROR);else STORE(&run.status,S_READY);
  logit(failed?"IMPORT_KEEP_PREVIOUS":"IMPORT_COMPLETE",0,failed,&run.catalog.count,1);
 }
 if(!r5_session_current()){(void)r5_lut_directory_release(&d);rc=-1;goto done;}
 unsigned step=5;int vol=r5sound_volume_load(&s,&step);STORE(&run.step,step);logit("VOLUME_LOAD",0,vol,&step,1);
 int sel=r5sound_selection_load(&s,&run.catalog,&selected);if(sel)logit("SELECTION_LOAD_FAILED",0,sel,0,0);
 if(r5_lut_directory_release(&d)){rc=-1;goto done;}
 /* The first published library already belongs to this admitted session.
  * A menu request before the worker's first service tick must not be erased
  * by treating a nonzero initial power epoch as a retained resume. */
 run.epoch=r5_session_epoch();
 STORE(&run.published,1);r5sound_menu_catalog_changed();rc=0;
 if(selected)(void)r5sound_request(selected);
done:
 if(c)run.free(c);
 if(rc<0)STORE(&run.status,S_BOOT_ERROR);
}
static void diagnostic(const char*stage,int rc){
 uint32_t v[R5SS_BRIDGE_DIAG_WORDS];r5ss_bridge_diagnostics(v);
 logit(stage,run.desired?r5sound_name(run.desired):0,rc,v,R5SS_BRIDGE_DIAG_WORDS);
 /* Preserve the existing bridge wire format. Its successful last snapshot
  * does not identify a later allocator, copy or table-registration failure. */
 const uint32_t backend[]={1,run.backend.fault,run.backend.last_native,
  run.backend.cleanup_fault,run.backend.cleanup_native,
  run.backend.registered,run.backend.cp_owned,run.backend.ap_owned,run.backend.mapped,
  (uint32_t)run.backend.cp.handle,(uint32_t)run.backend.ap.handle,
  run.epoch,r5_session_epoch()};
 logit("BACKEND_STATE",0,rc,backend,sizeof backend/sizeof backend[0]);
}
static void end_request(unsigned status,int fault){
 STORE(&run.status,status);STORE(&run.request,0);run.changing=run.restoring=0;
 if(fault||status==S_POLICY||status==S_PLAY_ERROR){STORE(&run.selected,0);(void)r5ss_configure(&run.scheduler,0,0);}
 if(fault)run.fault=1;
 if(!fault&&run.selected&&run.backend.registered){
  r5ss_native_policy policy;
  if(run.backend.volume_step==r5sound_volume_get()&&!r5ss_native_gate(&policy))
   (void)r5ss_configure(&run.scheduler,run.backend.installed_generation,policy.audible);
  else {STORE(&run.selected,0);(void)r5ss_configure(&run.scheduler,0,0);}
 }
 __atomic_add_fetch(&run.revision,1,__ATOMIC_RELEASE);
 if(run.audio&&!run.backend.mapped&&!run.backend.ap_owned){run.free(run.audio);run.audio=0;run.backend.encoded=0;}
}
static int load_selected(uint32_t volume){
 const r5sound_entry*e=&run.catalog.entries[run.desired-1];
 if(e->bytes<R5SOUND_PACKAGE_HEADER_BYTES+320u||e->bytes>R5SOUND_PACKAGE_MAX_BYTES)return -1;
 struct r5_lut_directory d;r5sound_storage s;size_t n=0;int rc=directory(&d,&s);
 if(rc)return -1;
 run.audio=run.alloc(R5SOUND_STAGING_BYTES);
 if(!run.audio)rc=-1;else rc=r5sound_catalog_audio(&s,e,volume,run.audio,R5SOUND_STAGING_BYTES,&n);
 if(r5_lut_directory_release(&d))rc=-1;
 if(!r5_session_current())rc=-1;
 if(!rc)run.encoded_bytes=(uint32_t)n;
 if(!r5_session_current())rc=-1;logit("AUDIO_PREPARE",r5sound_name(run.desired),rc,&volume,1);return rc;
}
static int save_config(unsigned index,unsigned step){
 struct r5_lut_directory d;r5sound_storage s;int rc=directory(&d,&s);
 if(!rc){rc=step?r5sound_volume_save(&s,step):r5sound_selection_save(&s,&run.catalog,index);if(r5_lut_directory_release(&d))rc=-1;}return rc;
}
static int resume_config(void){
 struct r5_lut_directory d;r5sound_storage s;unsigned step=5,selected=0;
 if(directory(&d,&s))return -1;
 int vol=r5sound_volume_load(&s,&step);
 int sel=r5sound_selection_load(&s,&run.catalog,&selected);
 int close=r5_lut_directory_release(&d);
 if(vol<0||sel<0||close||!r5_session_current())return -1;
 STORE(&run.step,step);run.restoring=1;
 STORE(&run.request,selected+1);return 0;
}
int r5sound_service(void){
 if(!r5_session_current()||!LOAD(&run.published))return 0;
 uint32_t epoch=r5_session_epoch();
 if(run.epoch!=epoch){
  if(r5ss_configure(&run.scheduler,0,0))return 1;
  run.epoch=epoch;STORE(&run.resuming,1);STORE(&run.selected,0);
  STORE(&run.request,0);run.changing=run.restoring=run.retry=0;
  __atomic_add_fetch(&run.revision,1,__ATOMIC_RELEASE);
  if(r5ss_bridge_bind_epoch(epoch)){STORE(&run.resuming,0);end_request(S_QUERY,1);return 0;}
 }
 if(LOAD(&run.resuming)){
  /* The backend queries original DMM ownership and drains native playback.
   * An AP power epoch alone never permits reuse/free of a numeric handle. */
  int rc=r5ss_backend_resume(&run.backend);
  if(rc>0)return 1;
  if(rc<0){diagnostic("RESUME_RESOURCE_FAILED",rc);STORE(&run.resuming,0);end_request(S_REGISTER,1);return 0;}
  rc=r5ss_reset_retired(&run.scheduler);if(rc>0)return 1;
  if(rc<0){STORE(&run.resuming,0);end_request(S_REGISTER,1);return 0;}
  if(run.audio){run.free(run.audio);run.audio=0;run.backend.encoded=0;}
  run.fault=0;
  if(resume_config()){STORE(&run.resuming,0);end_request(S_BOOT_ERROR,0);return 0;}
  STORE(&run.resuming,0);logit("RESUME_RELOAD",0,0,&epoch,1);
 }
 if(run.fault)return 0;
 if(run.retry){run.retry--;return 1;}
 uint32_t request=LOAD(&run.request);
 r5ss_native_policy policy;
 if((request||run.selected)&&r5ss_native_gate(&policy)){logit("POLICY_FAILED",0,-1,0,0);end_request(S_POLICY,run.token!=0);return 0;}
 
 if(request){
  if(!run.changing){
   if(r5ss_configure(&run.scheduler,0,0))return 1;
   run.volume_request=!!(request&0x100u);run.desired=run.volume_request?LOAD(&run.selected):request-1;run.target_step=run.volume_request?(request&255u):r5sound_volume_get();run.changing=1;run.attempts=run.persisted=0;STORE(&run.status,S_LOADING);
   logit("SELECT_BEGIN",run.desired?r5sound_name(run.desired):0,0,&run.desired,1);
  }
  if(run.desired&&!run.token){
   if(r5ss_bridge_bind_epoch(epoch))return 1;
   uint32_t token=0;int rc=r5ss_native_first_owner17(&token);
   if(rc){diagnostic("INITIAL_QUERY",rc);run.attempts++;if(rc<0||run.attempts>=30){end_request(S_QUERY,0);return 0;}run.retry=99;return 1;}
   if(r5ss_backend_first_authorize(&run.backend,token)){diagnostic("INITIAL_AUTHORIZE_FAILED",-1);end_request(S_REGISTER,1);return 0;}run.token=token;
  }
  if(run.backend.registered||r5ss_bridge_active()){
   r5ss_ops ops=r5ss_backend_ops(&run.backend);int rc=r5ss_tick(&run.scheduler,&ops);
   if(rc<0){diagnostic("RETIRE_FAILED",rc);end_request(S_REGISTER,1);return 0;}
   if(rc||r5ss_bridge_active())return 1;
  }
  if(!run.desired){
   int rc=0;
   if(!run.persisted&&!run.restoring){rc=save_config(0,0);logit("SELECT_OFF_SAVE",0,rc,0,0);if(rc){end_request(S_SAVE_ERROR,0);return 0;}run.persisted=1;}
   if(!r5_session_current()){end_request(S_OFF,0);return 0;}
   rc=run.token?r5ss_backend_unload(&run.backend):0;if(rc>0)return 1;if(rc<0){diagnostic("UNLOAD_FAILED",rc);end_request(S_REGISTER,1);return 0;}
   STORE(&run.selected,0);logit("SELECT_OFF",0,0,0,0);end_request(rc?S_SAVE_ERROR:S_OFF,0);return 0;
  }
  if(!run.audio){
   if(run.generation==UINT32_MAX||load_selected(run.target_step)){
    end_request(S_REGISTER,0);return 0;
   }
   /* Persist the independent volume before changing CP audio. A failed write
    * leaves the previous bank untouched. Native uncertainty later disables
    * playback and pins its lease; it is never called a successful rollback. */
   if(!run.restoring){
    int saved=save_config(run.desired,run.volume_request?run.target_step:0);
    logit(run.volume_request?"VOLUME_SAVE":"SELECTION_SAVE",0,saved,run.volume_request?&run.target_step:&run.desired,1);
    if(saved){end_request(S_SAVE_ERROR,0);return 0;}
    if(run.volume_request)STORE(&run.step,run.target_step);
   }
   if(!r5_session_current()){end_request(S_READY,0);return 0;}
   run.generation++;run.volume=run.target_step;
   int rc=r5ss_backend_stage(&run.backend,run.generation,run.audio,run.encoded_bytes,run.encoded_bytes+R5SOUND_F0_GUARD,run.volume);
   if(rc){diagnostic("STAGE_FAILED",rc);end_request(S_REGISTER,0);return 0;}
  }
  int rc=r5ss_backend_install(&run.backend,run.generation);
  if(rc>0)return 1;
  if(rc<0){diagnostic("REGISTER_FAILED",rc);end_request(S_REGISTER,1);return 0;}
  logit("REGISTER_OK",r5sound_name(run.desired),0,&run.backend.installed_bytes,1);
  run.free(run.audio);run.audio=0;run.backend.encoded=0;
  run.last_start=run.scheduler.starts;run.last_stop=run.scheduler.stops;run.logged_play=run.logged_stop=run.logged_done=run.logged_gate=0;STORE(&run.selected,run.desired);
  rc=0;
  uint32_t applied[2]={run.generation,run.volume};logit("GAIN_BIND_OK",r5sound_name(run.desired),0,applied,2);
  end_request(rc?S_SAVE_ERROR:S_ACTIVE,0);
  (void)r5ss_configure(&run.scheduler,run.generation,policy.audible);return 1;
 }
 if(!run.selected)return 0;
 if(!run.logged_gate&&LOAD(&run.seen_exposures)){uint32_t gate[3]={policy.silent_raw,run.volume,policy.audible};logit("SHUTTER_POLICY",r5sound_name(run.selected),0,gate,3);run.logged_gate=1;}
 if(r5ss_configure(&run.scheduler,run.backend.installed_generation,policy.audible))return 1;
 if(LOAD(&run.scheduler.serial)!=LOAD(&run.scheduler.consumed)||r5ss_bridge_active()){
  unsigned active=r5ss_bridge_active();r5ss_ops ops=r5ss_backend_ops(&run.backend);int rc=r5ss_tick(&run.scheduler,&ops);
  if(active&&!r5ss_bridge_active()&&!run.logged_done){logit("PLAY_COMPLETE",r5sound_name(run.selected),0,0,0);run.logged_done=1;}
  if(rc<0){diagnostic("PLAY_FAILED",rc);end_request(S_PLAY_ERROR,1);return 0;}
  /* Native async Start returns after enqueue. Completion and retirement are
   * observed separately; this event does not prove CP admission or sound. */
  if(!run.logged_play&&run.scheduler.starts!=run.last_start){logit("PLAY_QUEUED",r5sound_name(run.selected),0,&run.scheduler.starts,1);run.logged_play=1;}
  if(!run.logged_stop&&run.scheduler.stops!=run.last_stop){logit("STOP_ACCEPTED",r5sound_name(run.selected),0,&run.scheduler.stops,1);run.logged_stop=1;}
 }
 return 1;
}
