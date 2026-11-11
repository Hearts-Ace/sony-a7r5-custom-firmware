#include <stdint.h>

extern uint64_t r5_filter_pt_desired;
extern uint32_t r5_filter_pt_command_state, r5_filter_pt_command_kind;
extern unsigned r5_filter_pt_native_get(void);
extern void r5_filter_pt_native_set(unsigned);
extern void r5_native_creative_sequence_request(const void *);

/* Called only by the existing filter worker's refresh425, after its first
 * exact CP selection ACK. Keep the original E4 request and completion witness.
 * Automatic bank restoration/reload and Off do not change Creative Look.
 * Native PID690 value1 is Portrait/PT; this is not the ISP style index3.
 * No extra IO, upload, sleep, polling loop or per-frame hook is introduced.
 * A later transaction failure uses the original filter rollback; PT remains
 * the chosen native Look once the accepted selection reaches this refresh. */
void r5_filter_pt_sequence_request(const void *params)
{
    uint64_t desired = __atomic_load_n(&r5_filter_pt_desired, __ATOMIC_ACQUIRE);
    unsigned selected = (unsigned)desired;
    if (__atomic_load_n(&r5_filter_pt_command_state, __ATOMIC_ACQUIRE) == 1 &&
        __atomic_load_n(&r5_filter_pt_command_kind, __ATOMIC_ACQUIRE) == 1 &&
        selected >= 1 && selected <= 12 && r5_filter_pt_native_get() != 1)
        r5_filter_pt_native_set(1);
    r5_native_creative_sequence_request(params);
}
