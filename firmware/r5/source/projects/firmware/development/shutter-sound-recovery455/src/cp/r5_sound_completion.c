/* Candidate single original-cleanup observer, 6549DC. It preserves the full
 * native cleanup and records only private kind17. Native focus4 never changes
 * the added state. Sequence advancement is COMPLETION OBSERVED, not DMA idle:
 * the native AbbSysnd finish callback runs before actor descriptor clearing.
 * Integration must wait for actor retirement after the witness advances. */
#include "r5_sound_completion.h"
typedef unsigned char u8;
#ifdef R5SS_COMPLETION_HOST
extern unsigned r5ss_completion_read(unsigned,unsigned);
#define READ(a,b) r5ss_completion_read(a,b)
#else
#define READ(a,b) ((b)?*(volatile const u8 *)(a):*(volatile const unsigned *)(a))
#endif
r5ss_u32 r5ss_cp_completion_hook(void *object,r5ss_u32 result){
 /* Capture the current native packet before654A2E clears it. Do not use any
  * native pointer after original cleanup, nor retain packet pointers. */
 unsigned mine=READ(0x10a66e0u,1)&&READ(0x10a66e2u,1)==17u&&result!=0xe003u;
 unsigned request_word4=mine?READ(0x10a66e4u,0):0;
 unsigned out=r5ss_cp_completion_original(object,result);
 struct r5ss_completion *s=r5ss_cp_completion_state();
 if(mine&&s){
  s->last_native_result=result;s->last_request_word4=request_word4;s->observed=1;
  __atomic_fetch_add(&s->sequence,1,__ATOMIC_RELEASE);
 }
 return out;
}
