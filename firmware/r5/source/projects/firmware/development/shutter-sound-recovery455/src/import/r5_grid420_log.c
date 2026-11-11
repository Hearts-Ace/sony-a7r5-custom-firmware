/* Finite filesystem worker only. Never runs SD I/O in CP/render callbacks. */
#include "r5_grid_diagnostics.h"
#include "r5_runtime_session.h"
#include "r5_filter_runtime423.h"
extern int r5_native_fsys_open(const char *,uint32_t,uint64_t *);
extern int r5_native_fsys_write(uint64_t,const void *,uint64_t);
extern int r5_native_fsys_close(uint64_t);
extern void *r5_stage411_dlsym(void *,const char *);
extern int r5_native_ap_send(void *,const uint8_t *,size_t);
extern uint32_t r5_osal_msg_size(const void *);
struct r5_log420_state {int32_t open,write,flush,close;uint32_t records,failures,active,inbox_state,token,late;uint8_t inbox[128];};
__attribute__((aligned(16))) struct r5_log420_state r5_log420_state;
static char *hex(char *p,uint32_t x){static const char digits[]="0123456789abcdef";int i;for(i=7;i>=0;i--)*p++=digits[(x>>(4*i))&15];return p;}
int r5_log420_emit(unsigned drive,const char *stage,const uint32_t *values,unsigned n){
 char path[]="A:/R5IMPORT.LOG",buf[1024],*p=buf;unsigned i;uint64_t handle=0;int rc;
 struct r5_log420_state *s=&r5_log420_state;int (*flush)(uint64_t);
 if(drive<'A'||drive>'Z'||!stage||n>64)return -1;path[0]=(char)drive;
 flush=(int (*)(uint64_t))r5_stage411_dlsym(0,"Fsys_Flush");
 for(i=0;i<40&&stage[i];i++)*p++=stage[i];
 for(i=0;i<n;i++){*p++=' ';p=hex(p,values[i]);}*p++='\n';
 /* Create+truncate on first log of this boot, then create+append. */
 s->open=r5_native_fsys_open(path,s->records?0x16u:0x0eu,&handle);
 if(s->open){s->failures++;return -1;}
 s->write=r5_native_fsys_write(handle,buf,(uint64_t)(p-buf));
 s->flush=flush?flush(handle):-1;s->close=r5_native_fsys_close(handle);
 rc=s->write||s->flush||s->close;s->records++;if(rc)s->failures++;
 return rc?-1:0;
}
int r5_grid420_inbound(const uint8_t *p,uint32_t source){
 struct r5_log420_state *s=&r5_log420_state;uint32_t n,expected=0;unsigned i;
 if(source!=0x90030001u)return 0;n=r5_osal_msg_size(p);
 if(!r5_diag_envelope(p,n))return 0;
 if(n!=128||p[1]!=1||p[2]!=0x81||p[3]!=128||r5_diag_get(p+12)!=0x420||r5_diag_get(p+8)!=__atomic_load_n(&s->token,__ATOMIC_ACQUIRE)||r5_diag_get(p+28)!=r5_diag_crc(p,n)||!__atomic_load_n(&s->active,__ATOMIC_ACQUIRE)){s->late++;return 1;}
 if(!__atomic_compare_exchange_n(&s->inbox_state,&expected,1,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)){s->late++;return 1;}
 for(i=0;i<128;i++)s->inbox[i]=p[i];__atomic_store_n(&s->inbox_state,2,__ATOMIC_RELEASE);return 1;
}
struct log_time {int64_t sec,nsec;};
typedef int (*sleep_fn)(const struct log_time *,struct log_time *);
typedef int (*clock_fn)(int,struct log_time *);
static int now(clock_fn clock,uint64_t *ms){struct log_time t;if(!clock||clock(1,&t)||t.sec<0||t.nsec<0||t.nsec>=1000000000||(uint64_t)t.sec>(UINT64_MAX-999)/1000)return -1;*ms=(uint64_t)t.sec*1000+(uint64_t)t.nsec/1000000;return 0;}
void r5_grid420_watch(unsigned drive,uint32_t expected_grid){
 struct r5_log420_state *s=&r5_log420_state;uint8_t packet[32];uint32_t previous[13]={0},values[13],token=0;unsigned query,poll,i,changed;int status;
 uint64_t start,last,stamp;sleep_fn sleep=(sleep_fn)r5_stage411_dlsym(0,"nanosleep");clock_fn clock=(clock_fn)r5_stage411_dlsym(0,"clock_gettime");
 const struct log_time delay={0,100000000};
 uint32_t bank=r5_session_token(0x430d1a60u),selected=r5_filter_selected();
 expected_grid&=selected&&selected<=12?1u<<(selected-1):0;
 if(!expected_grid)return;
 if(!sleep||now(clock,&start)){values[0]=1;r5_log420_emit(drive,"GRID_QUERY_CLOCK_FAILED",values,1);return;}last=start;
 for(query=0;query<30&&r5_session_current();query++) {
  r5_filter_service();
  if(bank!=r5_session_token(0x430d1a60u))goto finish;
  for(i=0;i<32;i++)packet[i]=0;packet[0]=0xe9;packet[1]=1;packet[2]=1;packet[3]=32;r5_diag_put(packet+4,R5_DIAG_MAGIC);
  extern uint32_t r5_session_epoch(void);token=0x42000000u+(r5_session_epoch()<<8)+query+1;__atomic_store_n(&s->token,token,__ATOMIC_RELEASE);__atomic_store_n(&s->inbox_state,0,__ATOMIC_RELEASE);__atomic_store_n(&s->active,1,__ATOMIC_RELEASE);
  r5_diag_put(packet+8,token);r5_diag_put(packet+28,r5_diag_crc(packet,32));status=r5_native_ap_send(0,packet,32);
  if(status){values[0]=(uint32_t)status;r5_log420_emit(drive,"GRID_QUERY_SEND_FAILED",values,1);break;}
  for(poll=0;poll<10;poll++) {
   /* Same worker, no live filesystem descriptor. A diagnostic ACK wait must
    * never hold up an accepted menu selection or its durable completion. */
   r5_filter_service();
   if(bank!=r5_session_token(0x430d1a60u))goto finish;
   if(!r5_session_current()||now(clock,&stamp)||stamp<last||stamp<start||stamp-start>=30000u)goto finish;last=stamp;
   if(__atomic_load_n(&s->inbox_state,__ATOMIC_ACQUIRE)==2)break;
   if(sleep(&delay,0))goto finish;
  }
  if(__atomic_load_n(&s->inbox_state,__ATOMIC_ACQUIRE)!=2){values[0]=token;r5_log420_emit(drive,"GRID_QUERY_TIMEOUT",values,1);break;}
  /* enabled,selected,built,upload_returned,reason,selection/build/upload calls,last slot */
  changed=0;for(i=0;i<13;i++){values[i]=r5_diag_get(s->inbox+32+i*4);if(values[i]!=previous[i])changed=1;previous[i]=values[i];}
  if(!query||changed)r5_log420_emit(drive,"GRID_STATUS",values,13);
  selected=r5_filter_selected();
  expected_grid=selected&&selected<=12?1u<<(selected-1):0;
  if(((values[3]|values[9])&expected_grid)==expected_grid)goto finish;
  for(i=0;i<5;i++){
   r5_filter_service();
   if(bank!=r5_session_token(0x430d1a60u)||!r5_session_current()||sleep(&delay,0))goto finish;
  }
 }
finish:
 __atomic_store_n(&s->active,0,__ATOMIC_RELEASE);
 values[0]=expected_grid;values[1]=previous[0];values[2]=previous[1];values[3]=previous[2];values[4]=previous[3];values[5]=expected_grid&~(previous[3]|previous[9]);
 r5_log420_emit(drive,values[5]?"GRID_NOT_OBSERVED_OR_FAILED":"GRID_UPLOAD_RETURNED",values,6);
}

void r5_stage421_log_reset(void){extern void *memset(void *,int,size_t);uint32_t records=r5_log420_state.records,failures=r5_log420_state.failures;memset(&r5_log420_state,0,sizeof(r5_log420_state));r5_log420_state.records=records;r5_log420_state.failures=failures;}
