#ifndef R5_DIRECT_PTHREAD_H
#define R5_DIRECT_PTHREAD_H
#include <stdint.h>
#include <stddef.h>
/* Exact native R5 libpthread attr size. Object must outlive detached child. */
#define R5_DIRECT_STACK_BYTES 262144u
enum { R5_DIRECT_NEW, R5_DIRECT_CREATING, R5_DIRECT_ACCEPTED, R5_DIRECT_REFUSED };
enum { R5_DIRECT_WAITING, R5_DIRECT_ENTERED, R5_DIRECT_RUNNING, R5_DIRECT_DONE, R5_DIRECT_FAILED };
struct r5_direct_api {
    int (*attr_init)(void *);
    int (*attr_detached)(void *,int);
    int (*attr_stacksize)(void *,size_t);
    int (*create)(uintptr_t *,const void *,void *(*)(void *),void *);
    int (*attr_destroy)(void *);
    /* Native libc ABI; child calls pid=0, SCHED_OTHER=0, priority=0. */
    int (*sched_setscheduler)(int,int,const void *);
    int (*run)(void *);
};
struct r5_direct_pthread {
    uint32_t prepared,launch,phase;
    int setup_status,create_status,cleanup_status,schedule_status,run_status;
    uintptr_t thread;
    uint64_t attributes[8];
    struct r5_direct_api api;
    void *argument;
};
/* Fresh zero object; preparation is single-owner and before any launch. */
int r5_direct_prepare(struct r5_direct_pthread *,const struct r5_direct_api *,void *);
/* No custom startup handshake, join or child-progress wait; libc may block. */
int r5_direct_launch_once(struct r5_direct_pthread *);
void *r5_direct_entry(void *);
#endif
