#include "r5_scan_gate.h"
#define LOAD(p) __atomic_load_n((p),__ATOMIC_ACQUIRE)
#define STORE(p,v) __atomic_store_n((p),(v),__ATOMIC_RELEASE)
int r5_scan_gate_initial(struct r5_scan_gate *s,uint32_t a,uint32_t b) {
    uint32_t expected=0;
    /* This notification is emitted once. A weak CAS may fail solely because
     * an exclusive reservation was lost, dropping the only initial event.
     * Strong CAS retries that hardware failure, while still refusing an
     * event already claimed by another publisher. */
    if (!s || !__atomic_compare_exchange_n(&s->initial_phase,&expected,1,0,
                                          __ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)) return 0;
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
