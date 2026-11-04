/* Read-only original-state observations and completion-guarded retirement.
 * Filter resource24 is unrelated to the native SYSND actor lock, so a bare
 * zero snapshot cannot certify retirement. No code here writes native state,
 * calls Stop, frees DMM, or publishes sound. */
#include "r5_sound_snapshot_wire.h"
#include "r5_sound_completion.h"
#include "r5_sound_gain.h"
typedef unsigned char u8;
typedef unsigned int u32;
#ifndef R5SS_SNAPSHOT_HOST
/* Clang emits this EABI helper for aligned zero initializers. Keep it local to
 * this payload; it needs no unknown stock ABI and owns no mutable storage. */
void __aeabi_memclr8(void *p,u32 n){
 volatile u8 *out=(volatile u8 *)p;
 for(u32 i=0;i<n;i++)out[i]=0;
}
#endif
typedef struct {u32 address,byte;} field;
static const field fields[R5SS_SNAPSHOT_FIELD_COUNT]={
 {0x111782c,0},{0x1117830,0},{0x1117860,0},{0x1117878,0},
 {0x16a5ab0,0},{0x16a5ac8,0},
 {0x10a66e0,1},{0x10a6700,1},{0x10a6720,1},{0x10a6740,1},
 {0x16a5b2c,1},{0x16a5acc,1},
 {0x198ad88,1},{0x198ad89,1},{0x198ad8a,1},
 {0x198ad8b,1},{0x198ad8c,1},{0x198ad8d,1},
 /* Additional native current / deferred packets. Opcode is their validity
  * marker; do not interpret stale kind/gain bytes after opcode was cleared. */
 {0x16a5aec,1},{0x16a5b0c,1},
 /* Original hardware gettersB35584/B3559C. Masked exactly as stock. */
 {0xf48a1c1c,0},{0xf48a1c34,0}
};
static u32 rd32(const u8 *p){return p[0]|(u32)p[1]<<8|(u32)p[2]<<16|(u32)p[3]<<24;}
static void wr32(u8 *p,u32 x){for(u32 i=0;i<4;i++)p[i]=(u8)(x>>(8*i));}
u32 r5ss_snapshot_crc(const u8 *p,u32 n){
 u32 c=0xffffffffu;
 for(u32 i=0;i<n;i++)if(i<28||i>=32){
  c^=p[i];for(u32 j=0;j<8;j++)c=(c>>1)^(0xedb88320u&-(c&1u));
 }
 return ~c;
}
#ifdef R5SS_SNAPSHOT_HOST
extern u32 r5ss_snapshot_test_read(u32,u32);
extern u32 r5ss_snapshot_test_exists(void);
extern u32 r5ss_snapshot_test_lookup(u32 *);
extern u32 r5ss_snapshot_test_registry_constructed(void);
#define READ(a,b) r5ss_snapshot_test_read(a,b)
#define BARRIER() __atomic_thread_fence(__ATOMIC_SEQ_CST)
#else
#define READ(a,b) ((b)?*(volatile const u8 *)(a):*(volatile const u32 *)(a))
#define BARRIER() __asm__ volatile("dmb sy":::"memory")
#endif
static u32 registry_constructed(void){
#ifdef R5SS_SNAPSHOT_HOST
 return r5ss_snapshot_test_registry_constructed();
#else
 /* Original constructor6566E2 writes this vtable before clearing its records.
  * Original Register does not require focus4 or Start's playback pathmask.
  * Construction is only one condition: stable absent17 and idle ownership
  * observations below remain mandatory, and native Start keeps its policy. */
 return READ(0x11bd7a0u,0)==0x00cd2a6cu;
#endif
}
static u32 lookup17(u32 *out,u32 *exists){
#ifdef R5SS_SNAPSHOT_HOST
 *exists=r5ss_snapshot_test_exists();
 return r5ss_snapshot_test_lookup(out);
#else
 *exists=((u32(*)(void *,u32))0x65660bu)((void *)0x11bd7a0u,17);
 return ((u32(*)(void *,u32,void *))0x65669du)((void *)0x11bd7a0u,17,out);
#endif
}
static u32 read_field(u32 i){
 u32 v=READ(fields[i].address,fields[i].byte);
 return i==20?(v&3u):i==21?(v&7u):v;
}
static u32 owned_pending(void){
 static const u32 packet[]={0x10a66e0,0x10a6700,0x10a6720,0x10a6740,
  0x16a5b2c,0x16a5acc,0x16a5aec,0x16a5b0c};
 u32 mask=0;
 for(u32 i=0;i<sizeof(packet)/sizeof(packet[0]);i++)
  if(READ(packet[i],1)&&READ(packet[i]+2,1)==17)mask|=1u<<i;
 if(READ(0x198ad8c,1)==17)mask|=1u<<8;
 if(READ(0x198ad8d,1)==17)mask|=1u<<9;
 return mask;
}
int r5ss_cp_snapshot_make_reply(const u8 *p,u32 n,u32 source,u8 *out){
 if(!p||n<8||p[0]!=R5SS_SNAPSHOT_CLASS||rd32(p+4)!=R5SS_SNAPSHOT_MAGIC)return 0;
 if(!out)return -1;
 if(n!=32||source!=R5SS_SNAPSHOT_AP_QUEUE||p[1]!=1||(p[2]!=1&&p[2]!=2&&p[2]!=3)||p[3]!=32||
    !rd32(p+8)||(p[2]==1&&rd32(p+16))||
    (p[2]!=3&&(rd32(p+20)||rd32(p+24)))||rd32(p+28)!=r5ss_snapshot_crc(p,n))return -1;
 u32 before[R5SS_SNAPSHOT_FIELD_COUNT],after[R5SS_SNAPSHOT_FIELD_COUNT];
 u32 descriptor_before[9] __attribute__((aligned(8)))={0};
 u32 descriptor_after[9] __attribute__((aligned(8)))={0};
 u32 exists_before=0,exists_after=0;
 u32 ready_before=registry_constructed();
 u32 lookup_before=lookup17(descriptor_before,&exists_before);
 struct r5ss_completion *state=r5ss_cp_completion_state();
 u32 sequence_before=state?__atomic_load_n(&state->sequence,__ATOMIC_ACQUIRE):0;
 BARRIER();
 for(u32 i=0;i<R5SS_SNAPSHOT_FIELD_COUNT;i++)before[i]=read_field(i);
 u32 pending_before=owned_pending();
 BARRIER();
 for(u32 i=0;i<R5SS_SNAPSHOT_FIELD_COUNT;i++)after[i]=read_field(i);
 u32 pending_after=owned_pending();
 BARRIER();
 u32 sequence_after=state?__atomic_load_n(&state->sequence,__ATOMIC_ACQUIRE):0;
 u32 lookup_after=lookup17(descriptor_after,&exists_after);
 u32 ready_after=registry_constructed();
 u32 descriptor_stable=exists_before==exists_after&&lookup_before==lookup_after;
 if(!lookup_before&&!lookup_after)for(u32 i=0;i<9;i++)
  if(descriptor_before[i]!=descriptor_after[i])descriptor_stable=0;
 for(u32 i=0;i<R5SS_SNAPSHOT_REPLY_BYTES;i++)out[i]=0;
 for(u32 i=0;i<16;i++)out[i]=p[i];
 out[2]=R5SS_SNAPSHOT_ACK;out[3]=R5SS_SNAPSHOT_REPLY_BYTES;
 u32 busy=0,changed=0;
 for(u32 i=0;i<R5SS_SNAPSHOT_FIELD_COUNT;i++){
  if(before[i]||after[i])busy|=1u<<i;
  if(before[i]!=after[i])changed|=1u<<i;
  wr32(out+64+4*i,after[i]);
 }
 wr32(out+32,busy);wr32(out+36,changed);wr32(out+40,!changed&&descriptor_stable);
 wr32(out+44,!busy&&!changed);
 u32 retirement=R5SS_RETIREMENT_UNKNOWN;
 /* A new completion for this sole outstanding private kind proves that its
  * native request progressed to final cleanup. Actor fields must retire after
  * that callback, and no captured native pending packet may still own kind17.
  * Independent focus/menu sounds can delay this gate but do not advance it. */
 if(p[2]==2&&descriptor_stable&&state&&state->observed&&sequence_before==sequence_after&&
    sequence_after!=rd32(p+16)&&(int)(sequence_after-rd32(p+16))>0){
  retirement=R5SS_RETIREMENT_RETIRED;
  for(u32 i=0;i<4;i++)if(before[i]||after[i])retirement=R5SS_RETIREMENT_BUSY;
  for(u32 i=20;i<22;i++)if(before[i]||after[i])retirement=R5SS_RETIREMENT_BUSY;
  if(pending_before||pending_after)retirement=R5SS_RETIREMENT_BUSY;
 }
 wr32(out+48,retirement);
 /* No boot witness: offset52 now reports initial-registration rejection. */
 wr32(out+56,R5SS_SNAPSHOT_FIELD_COUNT);
 wr32(out+60,exists_after);
 wr32(out+152,sequence_after);wr32(out+156,state?state->last_native_result:0xffffffffu);
 u32 descriptor_valid=descriptor_stable&&exists_after==2&&!lookup_after;
 if(descriptor_valid){
  wr32(out+160,descriptor_after[0]);wr32(out+164,descriptor_after[1]);
  wr32(out+168,descriptor_after[2]);wr32(out+172,descriptor_after[8]);
 }
 wr32(out+176,pending_before);wr32(out+180,pending_after);
 u32 rejects=(!ready_before?R5SS_INITIAL_REGISTRY_BEFORE:0)|
  (!ready_after?R5SS_INITIAL_REGISTRY_AFTER:0)|
  (!descriptor_stable?R5SS_INITIAL_DESCRIPTOR:0)|
  (exists_before!=1||exists_after!=1?R5SS_INITIAL_EXISTS17:0)|
  (lookup_before!=0xe002u||lookup_after!=0xe002u?R5SS_INITIAL_LOOKUP17:0)|
  (pending_before||pending_after?R5SS_INITIAL_PENDING17:0);
 for(u32 i=0;i<4;i++)if(before[i]||after[i])rejects|=R5SS_INITIAL_ACTOR;
 for(u32 i=20;i<22;i++)if(before[i]||after[i])rejects|=R5SS_INITIAL_MMIO;
 wr32(out+52,rejects);wr32(out+184,!rejects);wr32(out+188,descriptor_valid);
 if(p[2]==3){
  u32 allowed=ready_before&&ready_after&&descriptor_valid&&!pending_before&&!pending_after;
  for(u32 i=0;i<4;i++)if(before[i]||after[i])allowed=0;
  for(u32 i=20;i<22;i++)if(before[i]||after[i])allowed=0;
  wr32(out+184,r5ss_cp_gain_bind(p,descriptor_after,allowed));
 }
 wr32(out+28,r5ss_snapshot_crc(out,R5SS_SNAPSHOT_REPLY_BYTES));
 return 1;
}
#ifndef R5SS_SNAPSHOT_HOST
/* Receiver integration: call this BEFORE r5_cp_stage413_consume using the
 * existing49604A gateway, or call it first inside the existing consumer.
 * Original message ownership/unlock/free are left to that native gateway. */
int r5ss_cp_snapshot_consume(const u8 *p,u32 source){
 if(source!=R5SS_SNAPSHOT_AP_QUEUE||!p)return 0;
 u32 n=((u32(*)(const void *))0xbaad0du)(p);
 u8 reply[R5SS_SNAPSHOT_REPLY_BYTES];int rc=r5ss_cp_snapshot_make_reply(p,n,source,reply);
 if(!rc)return 0;
 if(rc<0)return 1;
 void *allocation=0;
 if(((int(*)(u32,void **,u32,u32))0x53c221u)(source,&allocation,R5SS_SNAPSHOT_REPLY_BYTES,0)||!allocation)return 1;
 ((void(*)(void *,u32))0xbaaaa1u)(allocation,R5SS_SNAPSHOT_CP_QUEUE);
 for(u32 i=0;i<R5SS_SNAPSHOT_REPLY_BYTES;i++)((u8 *)allocation)[i]=reply[i];
 if(((int(*)(u32,void *))0x53bb55u)(source,allocation))
  (void)((int(*)(u32,void *))0x53c31du)(source,allocation);
 return 1;
}
#endif
