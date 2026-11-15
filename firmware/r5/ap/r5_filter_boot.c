/* Whole-package SD import is confined to cold boot. Only the immutable file
 * index survives; every later selection reads one record from eMMC. */
#include <stdint.h>
#include <stddef.h>
#include "r5_fsys_adapter.h"
#include "r5_scan_gate.h"
#include "r5_runtime_session.h"
#include "r5_filter_runtime.h"
#include "r5_filter_store.h"
#include "r5sound_runtime.h"
extern void *r5_stage411_dlsym(void *,const char *);
extern int r5_native_fsys_open(const char *,uint32_t,uint64_t *);
extern int r5_native_fsys_read(uint64_t,void *,uint64_t,uint64_t *);
extern int r5_native_fsys_close(uint64_t);
#define LOAD(p) __atomic_load_n((p),__ATOMIC_ACQUIRE)
#define STORE(p,v) __atomic_store_n((p),(v),__ATOMIC_RELEASE)
struct r5_stage411_diagnostics {
    uint32_t once,launch_phase,entered,exited,child_phase;
    int32_t status,attr_destroy_status;uint32_t resolved;uintptr_t thread;
    uint32_t result,attempts,selected_slot,selected_drive;
    uint32_t bytes_read,read_calls,decoded_mask,terminal;
    int32_t close_status,last_native_status;
    struct r5_scan_gate scan;uint32_t media[2];
};
__attribute__((aligned(16))) struct r5_stage411_diagnostics r5_stage411_state;
_Static_assert(offsetof(struct r5_stage411_diagnostics,result)==40,"native diagnostics prefix");
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
static int within(clock_fn clock,uint64_t start,uint64_t *last,uint32_t budget) {
    uint64_t now;
    if(!r5_session_current()||now_ms(clock,&now)||now<*last||now<start||now-start>=budget)return 0;
    *last=now;return 1;
}
void r5_stage411_initial(uint32_t a,uint32_t b) {
    (void)r5_scan_gate_initial(&r5_stage411_state.scan,a,b);r5sound_initial(a,b);
}
void r5_stage411_completed(uint32_t slot) {
    (void)r5_scan_gate_completed(&r5_stage411_state.scan,slot);r5sound_completed(slot);
}
void r5_stage411_media(uint32_t slot,uint32_t status,uint32_t drive) {
    uint32_t value=0x80000000u;
    if(slot>1)return;
    if(!status&&drive>='A'&&drive<='Z')value|=0x40000000u|drive;
    STORE(&r5_stage411_state.media[slot],value);r5sound_media(slot,status,drive);
}
void *r5_stage411_child(void *argument){
    struct r5_stage411_diagnostics *s=argument;struct r5f_index index;
    uint32_t slot,media[2],required,selected=2,tried=0;unsigned poll;
    clock_fn clock=0;sleep_fn sleep=0;uint64_t start,last,discovery;
    struct r5_fsys_reader reader={0};struct r5_fsys_api api;
    uintptr_t handle=0;size_t used=0,got;int result=R5_IO_ERROR,cold;
    int (*schedule)(int,int,const void *);int priority=0;
    void *(*allocate)(size_t)=0;void (*release)(void *)=0;uint8_t *bytes=0;
    const struct timespec64 delay={0,100000000};
    unsigned selected_filter=0,persisted=0;
    if(s!=&r5_stage411_state||!r5_session_current())return 0;
    cold=r5_session_cold_start();STORE(&s->entered,1);STORE(&s->exited,0);STORE(&s->terminal,0);
    s->bytes_read=s->read_calls=s->decoded_mask=0;s->attempts=0;s->selected_drive=0;
    s->selected_slot=UINT32_MAX;STORE(&s->child_phase,1);
    schedule=(void *)r5_stage411_dlsym(0,"sched_setscheduler");if(!schedule||schedule(0,0,&priority))goto complete;
    clock=(void *)r5_stage411_dlsym(0,"clock_gettime");sleep=(void *)r5_stage411_dlsym(0,"nanosleep");
    if(!clock||!sleep||now_ms(clock,&start))goto complete;
    if(!cold){result=R5_ABSENT;goto done;}
    allocate=(void *)r5_stage411_dlsym(0,"malloc");release=(void *)r5_stage411_dlsym(0,"free");
    if(!allocate||!release||(bytes=allocate(R5F_MAX+1))==0)goto done;
    /* Select and persist exactly one package before any CP activation. */
    if(!r5_session_current()||now_ms(clock,&start))goto done;
    last=start;discovery=start;
scan:
    for(poll=0;poll<301;poll++) {
        s->attempts=poll+1;
        r5_filter_service();
        if(!within(clock,start,&last,30000u))goto done;
        if(LOAD(&s->scan.initial_phase)==2) {
            required=0;
            for(slot=0;slot<2;slot++) {
                uint32_t state=LOAD(&s->scan.initial_status[slot]);
                if(state-1u<2u)required|=1u<<slot;
                media[slot]=LOAD(&s->media[slot]);
            }
            {
                /* A slow/failed second slot must not hold a ready first slot.
                 * Each candidate still requires its own scan completion. */
                for(slot=0;slot<2;slot++)if((required&(1u<<slot))&&!(tried&(1u<<slot))&&LOAD(&s->scan.completed[slot])&&
                     (media[slot]&0x40000000u)){selected=slot;break;}
                if(selected==2){if((!required||poll>=299) && r5_scan_gate_ready(&s->scan) &&
                    (!(required&1u)||(media[0]&0x80000000u)) &&
                    (!(required&2u)||(media[1]&0x80000000u))){result=R5_ABSENT;goto done;}}
                else break;
            }
        }
        if(poll==300||sleep(&delay,0))goto done;
    }
    if(selected==2)goto done;
    s->selected_slot=selected;s->selected_drive=media[selected]&255u;
    /* Runtime ADRP/ADD callback pointers; no absolute PIE relocations. */
    api.open=r5_native_fsys_open;api.read=r5_native_fsys_read;api.close=r5_native_fsys_close;
    if(r5_fsys_reader_init(&reader,&api,(char)s->selected_drive))goto done;
    /* Card discovery has its own budget. A late ready callback leaves the
     * complete read/close/validation budget available in this same boot. */
    if(now_ms(clock,&start))goto done;last=start;
    STORE(&s->child_phase,2);
    /* Retry open failures only before reading; never call unknown errors absent.
     * Every attempt is read-only. At most 3 attempts and 15s polling budget. */
    for(poll=0;poll<3;poll++) {
        r5_filter_service();
        if(!within(clock,start,&last,15000u))goto done;
        if(!r5_fsys_open_file(&reader,"R5NATIVE.BIN",&handle))break;
        s->last_native_status=reader.last_native_status;
        if(poll==2)goto other_card;
        if(sleep(&delay,0))goto done;
    }
    while(used<R5F_MAX+1) {
        if(!within(clock,start,&last,15000u))goto close;
        got=0;
        if(r5_fsys_read_file(&reader,handle,bytes+used,R5F_MAX+1-used,&got))goto close;
        used+=got;
        if(!got){result=R5_IMPORTED;break;}
    }
    if(used>R5F_MAX)result=R5_INVALID;
close:
    s->bytes_read=(uint32_t)used;s->read_calls=64u-reader.calls_remaining;
    s->last_native_status=reader.last_native_status;
    s->close_status=r5_fsys_close_file(&reader,handle);
    if(s->close_status||!within(clock,start,&last,15000u))result=R5_IO_ERROR;
    if(result==R5_IMPORTED) {
        STORE(&s->child_phase,3);
        if(!used){r5f_empty(bytes);used=R5F_HEADER;}
        result=r5f_index_bytes(bytes,used,&index)?R5_INVALID:R5_IMPORTED;
        if(result==R5_IMPORTED)s->decoded_mask=index.mask;
    }
other_card:
    /* A ready card with no usable BIN must not hide a later-ready other card.
     * At most one closed read (three open attempts) per physical slot. */
    if(result!=R5_IMPORTED && selected<2 && r5_session_current()){
        tried|=1u<<selected;
        required=0;for(slot=0;slot<2;slot++)if(LOAD(&s->scan.initial_status[slot])-1u<2u)required|=1u<<slot;
        if(required&~tried){
            selected=2;used=0;result=R5_IO_ERROR;start=discovery;
            if(now_ms(clock,&last))goto done;
            goto scan;
        }
    }
done:
    if(r5_session_current()){
        /* Publish the complete validated SD package before reading any CP data.
         * Any uncertain/failed publish rereads the actual active eMMC file. */
        /* Wait for internal mount readiness by read-only attempts. Publish is
         * attempted exactly once: uncertain rename/fsync is never blindly retried. */
        {int rc=-1;
         if(now_ms(clock,&start))goto complete;last=start;
         for(poll=0;poll<151;poll++){
             if(!within(clock,start,&last,15000u))goto complete;
             rc=r5_filter_store_available();if(!rc)break;
             if(poll==150||sleep(&delay,0))goto complete;
         }
         if(result==R5_IMPORTED){
             if(r5_filter_store_publish(bytes,used,&index)){
                 result=R5_COMMIT_ERROR;rc=r5_filter_store_index(&index);
                 if(rc)goto complete;
             }
         }else{
             rc=r5_filter_store_index(&index);
             if(rc==1){uint8_t empty[R5F_HEADER];r5f_empty(empty);if(r5f_index_bytes(empty,sizeof(empty),&index))goto complete;}
             else if(rc)goto complete;
         }
        }
        /* No complete package survives into selection/transport/E4 waits. */
        if(bytes){release(bytes);bytes=0;}
        persisted=r5_filter_store_selection(&selected_filter,0)==R5_IMPORTED;
        if(!persisted)selected_filter=0;
        if(r5_session_current()&&!r5_filter_catalog_ready(&index,selected_filter,persisted))r5_filter_service();
    }
complete:
    if(bytes&&release)release(bytes);s->result=(uint32_t)result;
    STORE(&s->terminal,1);STORE(&s->exited,1);STORE(&s->child_phase,4);
    return (void *)(uintptr_t)(clock&&sleep);
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
