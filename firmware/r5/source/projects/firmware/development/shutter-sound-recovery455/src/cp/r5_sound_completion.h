#ifndef R5_SOUND_COMPLETION_H
#define R5_SOUND_COMPLETION_H
typedef unsigned int r5ss_u32;
/* Zeroed retained allocation supplied by integration. A local sequence is not
 * a cold-boot witness. No fixed BSS/page-table location is selected here. */
struct r5ss_completion {
 volatile r5ss_u32 sequence;
 r5ss_u32 last_native_result;
 r5ss_u32 last_request_word4;
 r5ss_u32 observed;
};
struct r5ss_completion *r5ss_cp_completion_state(void);
r5ss_u32 r5ss_cp_completion_hook(void *,r5ss_u32);
r5ss_u32 r5ss_cp_completion_original(void *,r5ss_u32);
#endif
