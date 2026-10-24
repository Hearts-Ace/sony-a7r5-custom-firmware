/* 4.20: cold-start full SD replacement, empty-file clear, atomic file save.
 * Adds one metadata-only CP probe after the file worker. No color activation. Native Fsys duration is
 * not bounded by the caller's 15-second polling deadline. */
#include <stdint.h>
#include <stddef.h>
#include "r5_fsys_adapter.h"
#include "r5_scan_gate.h"
#include "r5_runtime_session.h"
#include "r5_filter_runtime423.h"
#include "r5_native_lut_directory.h"
extern void r5_stage411_probe_run(uint32_t,uint32_t);
extern int r5_log420_emit(unsigned,const char *,const uint32_t *,unsigned);
extern void r5_grid420_watch(unsigned,uint32_t);
extern void r5_transfer420_log(unsigned);
extern void r5_probe420_log(unsigned);
extern void r5_stage413_transfer_run(const struct r5_look_set *);
extern void *r5_stage411_dlsym(void *, const char *);
extern int r5_native_fsys_open(const char *, uint32_t, uint64_t *);
extern int r5_native_fsys_read(uint64_t, void *, uint64_t, uint64_t *);
extern int r5_native_fsys_close(uint64_t);
#define LOAD(p) __atomic_load_n((p), __ATOMIC_ACQUIRE)
#define STORE(p,v) __atomic_store_n((p), (v), __ATOMIC_RELEASE)
struct r5_stage411_diagnostics {
    uint32_t once, launch_phase, entered, exited, child_phase;
    int32_t status, attr_destroy_status;
    uint32_t resolved;
    uintptr_t thread;
    uint32_t result, attempts, selected_slot, selected_drive;
    uint32_t bytes_read, read_calls, decoded_mask, terminal;
    int32_t close_status, last_native_status;
    struct r5_scan_gate scan;
    uint32_t media[2];
    struct r5_look_set parsed;
    uint8_t scratch[R5_LOOK_MAX+1];
    struct r5_look_set current;
    int32_t directory_status, load_status, stage_status, publish_status, release_status;
    uint32_t loaded_mask, saved_mask, unchanged, mount_attempts;
};
__attribute__((aligned(16))) struct r5_stage411_diagnostics r5_stage411_state;
static uint64_t media_snapshot[2];
static uint32_t manual_reload425;
static int activation425;
_Static_assert(offsetof(struct r5_stage411_diagnostics, result)==40,"408 prefix");
void *memset(void *dst,int value,size_t n) {
    uint8_t *p=dst;size_t i;for(i=0;i<n;i++)p[i]=(uint8_t)value;return dst;
}
void *memcpy(void *dst,const void *src,size_t n) {
    uint8_t *d=dst;const uint8_t *p=src;size_t i;for(i=0;i<n;i++)d[i]=p[i];return dst;
}
struct timespec64 { int64_t seconds, nanoseconds; };
typedef int (*clock_fn)(int, struct timespec64 *);
typedef int (*sleep_fn)(const struct timespec64 *, struct timespec64 *);
static int now_ms(clock_fn clock, uint64_t *out) {
    struct timespec64 t;
    if (clock(1,&t) || t.seconds<0 || t.nanoseconds<0 || t.nanoseconds>=1000000000 ||
        (uint64_t)t.seconds>(UINT64_MAX-999u)/1000u) return -1;
    *out=(uint64_t)t.seconds*1000u+(uint64_t)t.nanoseconds/1000000u;return 0;
}
static int within(clock_fn clock,uint64_t start,uint64_t *last) {
    uint64_t now;
    if(!r5_session_current()||now_ms(clock,&now)||now<*last||now<start||now-start>=15000u)return 0;
    *last=now;return 1;
}
void r5_stage411_initial(uint32_t a,uint32_t b) {
    (void)r5_scan_gate_initial(&r5_stage411_state.scan,a,b);
}
void r5_stage411_completed(uint32_t slot) {
    (void)r5_scan_gate_completed(&r5_stage411_state.scan,slot);
}
void r5_stage411_media(uint32_t slot,uint32_t status,uint32_t drive) {
    uint32_t value=0x80000000u;
    if(slot>1)return;
    if(!status&&drive>='A'&&drive<='Z')value|=0x40000000u|drive;
    STORE(&r5_stage411_state.media[slot],value);
    STORE(&media_snapshot[slot],((uint64_t)r5_session_event_epoch()<<32)|value);
}
/* Only after SD scan/close: no retained directory fd across event waits.
 * Cold startup only. Native unmount/suspend concurrency remains unproven. */
static int r5_stage411_persist(struct r5_stage411_diagnostics *s,clock_fn clock,sleep_fn sleep,int result) {
    struct r5_lut_directory directory={0};
    struct r5_lut_directory_api directory_api;
    struct r5_persist_ops persist;struct r5_stage_ops stage;
    uint8_t mount_scratch[65537];
    unsigned internal_ready=0;
    uint64_t start,last;unsigned poll;
    const struct timespec64 delay={0,100000000};
    if(now_ms(clock,&start))return R5_IO_ERROR;last=start;
    /* This object and retained fd belong only to this one finite worker.
     * A failed acquire consumes its object; reset before each NEW attempt. */
    if(r5_native_lut_directory_api_init(&directory_api))goto release;
    for(poll=0;poll<151;poll++) {
        s->mount_attempts=poll+1;
        if(!within(clock,start,&last))goto release;
        memset(&directory,0,sizeof(directory));
        s->directory_status=r5_lut_directory_acquire(&directory,&directory_api,mount_scratch,sizeof(mount_scratch));
        if(!s->directory_status){internal_ready=1;break;}
        if(poll==150||sleep(&delay,0))goto release;
    }
    if(!internal_ready||r5_lut_directory_bind_storage(&directory,&persist,&stage))goto release;
    r5_filter_load_selection(&directory);
    /* A validated SD candidate replaces the whole file, even if the old
     * file is corrupt. Only load the previous file when SD import failed/absent. */
    if(result!=R5_IMPORTED) {
        s->load_status=r5_load_persisted_look(&persist,&s->current,s->scratch,sizeof(s->scratch));
        s->loaded_mask=s->current.valid_mask;
        goto release;
    }
    s->load_status=R5_ABSENT;
    s->decoded_mask=s->parsed.valid_mask;
    /* This worker owns .NEW before any stage handle opens. Recover a stale
     * interrupted stage; never truncate the active .BIN. */
    if(stage.unlink_file(stage.context,R5_LOOK_PENDING)){result=R5_COMMIT_ERROR;goto release;}
    if(!within(clock,start,&last)){result=R5_IO_ERROR;goto release;}
    STORE(&s->child_phase,5);
    s->stage_status=r5_stage_look_store(&stage,&s->parsed,s->scratch,sizeof(s->scratch));
    if(s->stage_status!=R5_STAGE_READY){result=R5_COMMIT_ERROR;goto release;}
    if(!within(clock,start,&last)){result=R5_COMMIT_ERROR;goto release;}
    s->publish_status=r5_publish_staged_look(&persist,&s->parsed,s->scratch,sizeof(s->scratch));
    if(s->publish_status!=R5_PUBLISHED&&s->publish_status!=R5_PUBLISHED_CLOSE_ERROR){result=R5_COMMIT_ERROR;goto release;}
    memcpy(&s->current,&s->parsed,sizeof(s->current));s->saved_mask=s->current.valid_mask;
    if(s->publish_status==R5_PUBLISHED_CLOSE_ERROR)result=R5_COMMIT_ERROR;
release:
    if(internal_ready&&result!=R5_IMPORTED&&s->load_status==R5_ABSENT&&!s->current.valid_mask)
        s->load_status=r5_load_persisted_look(&persist,&s->current,s->scratch,sizeof(s->scratch));
    if(internal_ready)s->release_status=r5_lut_directory_release(&directory);
    if(internal_ready&&s->release_status)return R5_IO_ERROR;
    if(s->directory_status||(s->load_status!=R5_IMPORTED&&s->load_status!=R5_ABSENT))return R5_IO_ERROR;
    return result;
}

/* Both startup and SD replacement use the same complete parameter publication.
 * A failed storage read is never treated as an intentional empty configuration. */
static void activate(struct r5_stage411_diagnostics *s,int watch){
 activation425=-1;
 if(s->load_status!=R5_IMPORTED&&s->load_status!=R5_ABSENT&&
    s->publish_status!=R5_PUBLISHED&&s->publish_status!=R5_PUBLISHED_CLOSE_ERROR)return;
    /* Probe the currently loaded/published set, never a failed candidate.
     * No set = zero mask/hash diagnostic. Reply does not activate anything. */
    if(r5_session_current()&&r5_session_new_transfer()) {
        uint32_t digest=0,mask=s->current.valid_mask;
        if(mask) {
            size_t encoded=r5_encode_look_file(&s->current,s->scratch,sizeof(s->scratch));
            if(encoded)digest=(uint32_t)s->scratch[112]|(uint32_t)s->scratch[113]<<8|
                (uint32_t)s->scratch[114]<<16|(uint32_t)s->scratch[115]<<24;
            else mask=0;
        }
        r5_stage411_probe_run(mask,digest);
        r5_probe420_log(s->selected_drive);
        r5_stage413_transfer_run(&s->current);
        r5_transfer420_log(s->selected_drive);
        {extern int r5_stage421_parameters_ready(void);extern int r5_stage421_transfer_matched(void);
         if(r5_session_current()&&r5_stage421_transfer_matched()){
          int names=r5_stage421_parameters_ready();
          if(names>=0)activation425=0;
          if(names<0){uint32_t error=16;r5_log420_emit(s->selected_drive,"NAME_GENERATION_LIMIT",&error,1);}
          uint32_t v[2]={r5_session_epoch(),mask};
          r5_log420_emit(s->selected_drive,"CUSTOM_FILTER_SELECTION_QUEUED",v,2);
         }}
        {uint32_t grid=0;for(unsigned i=0;i<12;i++)if(mask&(1u<<i))grid|=1u<<i;
         if(watch&&grid)r5_grid420_watch(s->selected_drive,grid);}

    }
}

void *r5_stage411_child(void *argument) {
    struct r5_stage411_diagnostics *s=argument;
    uint32_t slot,media[2],epochs[2],required,selected=2;
    clock_fn clock=0;sleep_fn sleep=0;
    int (*schedule)(int,int,const void *);int priority=0;
    uint64_t start,last;unsigned poll;
    struct r5_fsys_reader reader={0};
    struct r5_fsys_api api;
    uintptr_t handle=0;size_t used=0,got;int result=R5_IO_ERROR;
    const struct timespec64 delay={0,100000000};
    if(s!=&r5_stage411_state||!r5_session_current())return 0;
    STORE(&s->entered,1);STORE(&s->terminal,0);STORE(&s->exited,0);
    memset(&s->parsed,0,sizeof(s->parsed));memset(&s->current,0,sizeof(s->current));
    s->bytes_read=s->read_calls=s->decoded_mask=s->loaded_mask=s->saved_mask=0;
    s->selected_drive=0;
    STORE(&s->child_phase,1);s->selected_slot=UINT32_MAX;
    s->directory_status=s->load_status=s->stage_status=s->publish_status=s->release_status=-99;
    schedule=(int (*)(int,int,const void *))r5_stage411_dlsym(0,"sched_setscheduler");
    if(!schedule||schedule(0,0,&priority))goto done;
    clock=(clock_fn)r5_stage411_dlsym(0,"clock_gettime");
    sleep=(sleep_fn)r5_stage411_dlsym(0,"nanosleep");
    if(!clock||!sleep||now_ms(clock,&start))goto done;
    /* Load/refresh saved parameters before waiting for SD discovery. The SD
     * candidate then fully replaces this generation, including a valid clear. */
    if(!manual_reload425){(void)r5_stage411_persist(s,clock,sleep,R5_ABSENT);
    activate(s,0);}
    if(!r5_session_current()||now_ms(clock,&start))goto done;
    last=start;
    for(poll=0;poll<151;poll++) {
        s->attempts=poll+1;
        if(!within(clock,start,&last))goto done;
        /* Prefer fresh media callbacks on resume; if native emits no repeat,
         * reopen the retained drive after one second, validating the full file. */
        if(r5_scan_gate_ready(&s->scan)) {
            required=0;
            for(slot=0;slot<2;slot++) {
                uint32_t state=LOAD(&s->scan.initial_status[slot]);
                if(state-1u<2u)required|=1u<<slot;
                uint64_t snapshot=LOAD(&media_snapshot[slot]);
                media[slot]=(uint32_t)snapshot;epochs[slot]=(uint32_t)(snapshot>>32);
            }
            if((!(required&1u)||(media[0]&0x80000000u))&&
               (!(required&2u)||(media[1]&0x80000000u))) {
                for(slot=0;slot<2;slot++)if((required&(1u<<slot))&&
                     (media[slot]&0x40000000u)&&
                     (epochs[slot]==r5_session_epoch()||poll>=10)){selected=slot;break;}
                if(selected==2){if(poll>=149){result=R5_ABSENT;goto done;}}
                else break;
            }
        }
        if(poll==150||sleep(&delay,0))goto done;
    }
    if(selected==2)goto done;
    s->selected_slot=selected;s->selected_drive=media[selected]&255u;
    {uint32_t v[2]={0x421,selected};r5_log420_emit(s->selected_drive,"BOOT421_SD_SELECTED",v,2);}
    /* Runtime ADRP/ADD callback pointers; no absolute PIE relocations. */
    api.open=r5_native_fsys_open;api.read=r5_native_fsys_read;api.close=r5_native_fsys_close;
    if(r5_fsys_reader_init(&reader,&api,(char)s->selected_drive))goto done;
    STORE(&s->child_phase,2);
    /* Retry open failures only before reading; never call unknown errors absent.
     * Every attempt is read-only. At most 3 attempts and 15s polling budget. */
    for(poll=0;poll<3;poll++) {
        if(!within(clock,start,&last))goto done;
        if(!r5_fsys_open_file(&reader,R5_LOOK_SD_FILE,&handle))break;
        s->last_native_status=reader.last_native_status;
        if(poll==2||sleep(&delay,0))goto done;
    }
    while(used<R5_LOOK_MAX+1) {
        if(!within(clock,start,&last))goto close;
        got=0;
        if(r5_fsys_read_file(&reader,handle,s->scratch+used,R5_LOOK_MAX+1-used,&got))goto close;
        used+=got;
        if(!got){result=R5_IMPORTED;break;}
    }
    if(used>R5_LOOK_MAX)result=R5_INVALID;
close:
    s->bytes_read=(uint32_t)used;s->read_calls=64u-reader.calls_remaining;
    s->last_native_status=reader.last_native_status;
    s->close_status=r5_fsys_close_file(&reader,handle);
    if(s->close_status||!within(clock,start,&last))result=R5_IO_ERROR;
    if(result==R5_IMPORTED) {
        STORE(&s->child_phase,3);
        if(!used){memset(&s->parsed,0,sizeof(s->parsed));result=R5_IMPORTED;}
        else result=r5_decode_look_file(s->scratch,used,&s->parsed);
        if(result==R5_IMPORTED)s->decoded_mask=s->parsed.valid_mask;
    }
done:
    if(clock&&sleep&&r5_session_current())result=r5_stage411_persist(s,clock,sleep,result);
    s->result=(uint32_t)result;
    {uint32_t v[13]={(uint32_t)result,s->bytes_read,s->decoded_mask,s->current.valid_mask,(uint32_t)s->last_native_status,(uint32_t)s->close_status,(uint32_t)s->directory_status,(uint32_t)s->load_status,(uint32_t)s->stage_status,(uint32_t)s->publish_status,(uint32_t)s->release_status,s->saved_mask,s->selected_slot};
     r5_log420_emit(s->selected_drive,result==R5_IMPORTED?"IMPORT_REPLACED_OR_CLEARED":"IMPORT_KEPT_OR_FAILED",v,13);}
    if(clock&&sleep&&(!manual_reload425||result==R5_IMPORTED))activate(s,manual_reload425?0:1);
    s->result=(uint32_t)result;
    STORE(&s->terminal,1);STORE(&s->exited,1);STORE(&s->child_phase,4);
    return 0;
}

/* Called only by the existing sole worker. Retains original bounded read,
 * validation, atomic store, complete transfer and 4.22 publication paths.
 * An absent/bad SD candidate is a visible failure and keeps current runtime. */
int r5_stage425_reload(void){
    struct r5_stage411_diagnostics *s=&r5_stage411_state;
    extern int r5_stage421_transfer_matched(void);
    if(!r5_session_current() || manual_reload425)return -1;
    manual_reload425=1;activation425=-1;r5_stage411_child(s);manual_reload425=0;
    return s->terminal && s->result==R5_IMPORTED && activation425==0 && r5_stage421_transfer_matched()?0:-1;
}

int r5_stage411_startup(void) {
    struct r5_stage411_diagnostics *s = &r5_stage411_state;
    uint32_t expected = 0;
    uint64_t attributes[8] = {0};
    int rc;
    int (*attr_init)(void *);
    int (*attr_detach)(void *, int);
    int (*attr_stack)(void *, size_t);
    int (*create)(uintptr_t *, const void *, void *(*)(void *), void *);
    int (*attr_destroy)(void *);
    if (!__atomic_compare_exchange_n(&s->once, &expected, 1, 0,
                                    __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE))
        return 0;
    __atomic_store_n(&s->launch_phase, 1, __ATOMIC_RELEASE);
#define LOOKUP(field, name, type) do { \
    field = (type)r5_stage411_dlsym(0, name); \
    if (!field) { rc = -1; goto refused; } \
    ++s->resolved; \
} while (0)
    LOOKUP(attr_init, "pthread_attr_init", int (*)(void *));
    LOOKUP(attr_detach, "pthread_attr_setdetachstate", int (*)(void *, int));
    LOOKUP(attr_stack, "pthread_attr_setstacksize", int (*)(void *, size_t));
    LOOKUP(create, "pthread_create", int (*)(uintptr_t *, const void *, void *(*)(void *), void *));
    LOOKUP(attr_destroy, "pthread_attr_destroy", int (*)(void *));
#undef LOOKUP
    __atomic_store_n(&s->launch_phase, 2, __ATOMIC_RELEASE);
    rc = attr_init(attributes);
    if (rc) goto refused;
    rc = attr_detach(attributes, 1);
    if (!rc) rc = attr_stack(attributes, 262144u);
    if (rc) {
        s->attr_destroy_status = attr_destroy(attributes);
        goto refused;
    }
    __atomic_store_n(&s->launch_phase, 3, __ATOMIC_RELEASE);
    r5_session_cold();
    rc = create(&s->thread, attributes, r5_stage421_loop, s);
    s->attr_destroy_status = attr_destroy(attributes);
    s->status = rc;
    /* Child may have already returned. Never overwrite its phase/counters. */
    __atomic_store_n(&s->launch_phase, rc ? 5u : 4u, __ATOMIC_RELEASE);
    return rc;
refused:
    s->status = rc;
    __atomic_store_n(&s->launch_phase, 5, __ATOMIC_RELEASE);
    return rc;
}
