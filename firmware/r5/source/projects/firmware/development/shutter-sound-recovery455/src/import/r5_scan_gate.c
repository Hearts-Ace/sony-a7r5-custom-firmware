#include "r5_scan_gate.h"
#define LOAD(p) __atomic_load_n((p),__ATOMIC_ACQUIRE)
#define STORE(p,v) __atomic_store_n((p),(v),__ATOMIC_RELEASE)
int r5_scan_gate_initial(struct r5_scan_gate *s,uint32_t a,uint32_t b) {
    uint32_t expected;
    if(!s)return 0;
    expected=LOAD(&s->initial_phase);
    do {if(expected==1)return 0;}
    while(!__atomic_compare_exchange_n(&s->initial_phase,&expected,1,0,
                                       __ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE));
    /* Initial notifications may repeat after resume. Retain completed flags:
     * completion may precede this callback, and file open/read still validate. */
    STORE(&s->initial_status[0],a);STORE(&s->initial_status[1],b);
    STORE(&s->initial_phase,2);return 1;
}
int r5_scan_gate_completed(struct r5_scan_gate *s,uint32_t slot) {
    if (!s || slot>1) return 0;
    STORE(&s->completed[slot],1);return 1;
}
int r5_scan_gate_ready(const struct r5_scan_gate *s) {
    uint32_t a,b;
    if (!s || LOAD(&s->initial_phase)!=2) return 0;
    a=LOAD(&s->initial_status[0]);b=LOAD(&s->initial_status[1]);
    return ((a-1)>1 || LOAD(&s->completed[0])) &&
           ((b-1)>1 || LOAD(&s->completed[1]));
}
