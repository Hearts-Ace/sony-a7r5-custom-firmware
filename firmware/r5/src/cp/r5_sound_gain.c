/* M4 gain policy adapted to R5 native APP/PIN/CLIP descriptor contracts.
 * Private PCM already contains its independent user scale. Only an explicit
 * authenticated OP3 binds an exact native kind17 physical/length identity.
 * Every rejection returns the original scalar; no original state is changed. */
#include "r5_sound_gain.h"
typedef unsigned char u8;
typedef r5ss_gain_u32 u32;
_Static_assert(sizeof(struct r5ss_gain_binding)==32,"gain binding32");
#ifdef R5SS_GAIN_HOST
extern struct r5ss_gain_binding *r5ss_gain_test_state(void);
extern u32 r5ss_gain_test_path(void);
#define STATE() r5ss_gain_test_state()
#define PATH() r5ss_gain_test_path()
#else
#define STATE() ((struct r5ss_gain_binding *)0x1a39478u)
#define PATH() (*(volatile const u32 *)0x109942cu)
#endif
static u32 rd(const u8 *p){return p[0]|(u32)p[1]<<8|(u32)p[2]<<16|(u32)p[3]<<24;}
static int descriptor(const volatile u32 *d,u32 lo,u32 hi,u32 bytes){
 return d&&d[0]==lo&&d[1]==hi&&d[2]==bytes&&d[3]==0x00010611u&&d[8]==lo;
}
int r5ss_cp_gain_bind(const u8 *p,const u32 *d,u32 allowed){
 struct r5ss_gain_binding *s=STATE();
 u32 tag=rd(p+12),serial=rd(p+8),lo=rd(p+16),hi=rd(p+20),bytes=rd(p+24);
 if(!allowed||!tag||!serial||!lo||(lo&63u)||!bytes||bytes>49568u||(bytes&31u)||
    !descriptor(d,lo,hi,bytes))return 0;
 u32 before=__atomic_load_n(&s->version,__ATOMIC_ACQUIRE);
 if((before&1u)||before>0xfffffffcu||
    (s->valid&&s->tag==tag&&serial<=s->serial))return 0;
 __atomic_store_n(&s->version,before+1,__ATOMIC_RELEASE);
 __atomic_thread_fence(__ATOMIC_RELEASE);
 s->tag=tag;s->serial=serial;s->lo=lo;s->hi=hi;s->bytes=bytes;s->valid=1;s->reserved=0;
 __atomic_store_n(&s->version,before+2,__ATOMIC_RELEASE);return 1;
}
u32 r5ss_cp_gain_scalar(u32 original,u32 kind,const volatile u32 *d,u32 caller){
 if(kind!=17||original>7||
    (caller!=0x6550fbu&&caller!=0x655541u&&caller!=0x656079u)||!(PATH()&2u))return original;
 const struct r5ss_gain_binding *s=STATE();
 u32 before=__atomic_load_n(&s->version,__ATOMIC_ACQUIRE);
 if(!before||(before&1u)||!s->valid||!s->tag||!s->serial||
    !descriptor(d,s->lo,s->hi,s->bytes))return original;
 __atomic_thread_fence(__ATOMIC_ACQUIRE);
 return before==__atomic_load_n(&s->version,__ATOMIC_RELAXED)?7u:original;
}
