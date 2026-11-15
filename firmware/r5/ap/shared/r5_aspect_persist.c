/* Internal setting record, matching the upstream schema and atomic publication.
 * This is a separate feature file, not a BIN/BAK personal-setting modification.
 * POSIX functions are resolved through the already-used R5 dlsym PLT entry. */
#include "r5_aspect_state.h"
#include <stddef.h>
extern void *r5_stage411_dlsym(void *,const char *);
static uint32_t restore_claim;
static uint32_t save_claim;
int32_t r5_aspect_persist_status;
struct api {
    int (*open)(const char *,int,unsigned);
    int (*openat)(int,const char *,int,unsigned);
    intptr_t (*read)(int,void *,size_t);
    intptr_t (*write)(int,const void *,size_t);
    int (*close)(int);
    int (*fsync)(int);
    int (*renameat)(int,const char *,int,const char *);
    int (*unlinkat)(int,const char *,int);
};
#define RFLAGS (0x8000|0x20000|0x80000|0x800)
#define DFLAGS (RFLAGS|0x10000)
#define WFLAGS (RFLAGS|1|0x40|0x80)
static int resolve(struct api *a) {
#define GET(name) a->name=(void *)r5_stage411_dlsym(0,#name);if(!a->name)return 0
    GET(open);GET(openat);GET(read);GET(write);GET(close);GET(fsync);
    GET(renameat);GET(unlinkat);
#undef GET
    return 1;
}
void r5_aspect_restore_once(void) {
    uint32_t expected=0;
    if (!__atomic_compare_exchange_n(&restore_claim,&expected,1,0,
             __ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)) return;
    uint32_t token=r5_aspect_token();struct api a;uint8_t bytes[17];size_t n=0;
    /* Any explicit browse/cancel/commit already advanced the epoch. */
    if(token) {r5_aspect_persist_status=2;return;}
    if (!resolve(&a)) {r5_aspect_persist_status=-1;return;}
    int directory=a.open("/setting",DFLAGS,0);
    if(directory<0) {r5_aspect_persist_status=-2;return;}
    int fd=a.openat(directory,"custom_aspect_v2.dat",RFLAGS,0);
    if(fd<0) {a.close(directory);r5_aspect_persist_status=-3;return;}
    int rc=0;
    while(n<sizeof bytes) {
        intptr_t got=a.read(fd,bytes+n,sizeof bytes-n);
        if(got<0 || (size_t)got>sizeof bytes-n) {rc=-1;break;}
        if(!got)break;
        n+=(size_t)got;
    }
    if(a.close(fd))rc=-1;
    if(a.close(directory))rc=-1;
    if(!rc && r5_aspect_restore_record(bytes,(uint32_t)n,token))
        r5_aspect_persist_status=1;
    else r5_aspect_persist_status=-4;
}
static int save_record(uint32_t choice) {
    struct api a;uint32_t record[4];int rc=0;size_t used=0;
    /* Explicit user choice must supersede an unfinished or future restore. */
    __atomic_store_n(&restore_claim,1,__ATOMIC_RELEASE);
    if(!resolve(&a))return r5_aspect_persist_status=-1;
    int directory=a.open("/setting",DFLAGS,0);
    if(directory<0)return r5_aspect_persist_status=-2;
    /* The staging filename belongs exclusively to this feature. */
    (void)a.unlinkat(directory,"custom_aspect_v2.tmp",0);
    int fd=a.openat(directory,"custom_aspect_v2.tmp",WFLAGS,0600);
    if(fd<0) {a.close(directory);return r5_aspect_persist_status=-5;}
    r5_aspect_make_record(choice,record);
    while(used<sizeof record) {
        intptr_t n=a.write(fd,(const uint8_t *)record+used,sizeof record-used);
        if(n<=0 || (size_t)n>sizeof record-used) {rc=-1;break;}
        used+=(size_t)n;
    }
    if(!rc && a.fsync(fd))rc=-1;
    if(a.close(fd))rc=-1;
    if(!rc && a.renameat(directory,"custom_aspect_v2.tmp",directory,
                         "custom_aspect_v2.dat"))rc=-1;
    if(!rc && a.fsync(directory))rc=-1;
    if(a.close(directory))rc=-1;
    r5_aspect_persist_status=rc?-6:1;
    return rc;
}
int r5_aspect_save(uint32_t choice) {
    uint32_t expected=0;
    if(!__atomic_compare_exchange_n(&save_claim,&expected,1,0,
             __ATOMIC_ACQUIRE,__ATOMIC_RELAXED))return -7;
    int rc=save_record(choice);
    __atomic_store_n(&save_claim,0,__ATOMIC_RELEASE);
    return rc;
}
