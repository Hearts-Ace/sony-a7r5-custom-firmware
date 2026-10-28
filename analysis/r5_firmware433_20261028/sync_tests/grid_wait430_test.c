/* Real diagnostic source, with native clocks, CP reply and selection-service
 * boundary fixtures. The actual selection worker has its own execution tests. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#undef memset
#include "../import/r5_grid420_log.c"
static uint64_t ms;
static unsigned mode,selected=1,queries,services,completed_at=~0u;
static uint32_t generation=1;
static int alive=1,pending;
static uint8_t reply[128];
int r5_session_current(void){return alive;}
uint32_t r5_session_epoch(void){return 1;}
uint32_t r5_session_token(uint32_t salt){return generation^salt;}
unsigned r5_filter_selected(void){return selected;}
void r5_filter_service(void){
 services++;
 if(mode && mode!=6 && ms>=100 && completed_at==~0u){selected=2;completed_at=(unsigned)ms;}
 if(mode==3 && ms>=100)alive=0;
 if(mode==4 && ms>=100)generation++;
}
static int clock430(int id,struct log_time *t){assert(id==1);t->sec=ms/1000;t->nsec=ms%1000*1000000;return 0;}
static int sleep430(const struct log_time *t,struct log_time *unused){
 assert(!unused && t->sec==0 && t->nsec==100000000);ms+=100;
 if(pending && mode!=2){pending=0;assert(r5_grid420_inbound(reply,0x90030001)==1);}
 return 0;
}
static int flush430(uint64_t h){assert(h==1);return 0;}
void *r5_stage411_dlsym(void *a,const char *n){
 assert(!a);
 if(!strcmp(n,"clock_gettime"))return (void *)clock430;
 if(!strcmp(n,"nanosleep"))return (void *)sleep430;
 if(!strcmp(n,"Fsys_Flush"))return (void *)flush430;
 abort();
}
int r5_native_fsys_open(const char *p,uint32_t f,uint64_t *h){assert(!strcmp(p,"C:/R5IMPORT.LOG") && (f==14 || f==22));*h=1;return 0;}
int r5_native_fsys_write(uint64_t h,const void *p,uint64_t n){assert(h==1 && p && n);return 0;}
int r5_native_fsys_close(uint64_t h){assert(h==1);return 0;}
uint32_t r5_osal_msg_size(const void *p){assert(p==reply);return 128;}
int r5_native_ap_send(void *a,const uint8_t *p,size_t n){
 assert(!a && n==32 && r5_diag_envelope(p,n));queries++;
 memset(reply,0,sizeof reply);memcpy(reply,p,32);reply[2]=0x81;reply[3]=128;
 r5_diag_put(reply+12,0x420);r5_diag_put(reply+32,4095);
 /* Only the filter active for this query is observed, never the whole bank. */
 r5_diag_put(reply+32+3*4,mode==5?0:1u<<(selected-1));
 r5_diag_put(reply+28,r5_diag_crc(reply,128));
 if(!mode)assert(r5_grid420_inbound(reply,0x90030001)==1);else pending=1;
 return 0;
}
int main(int argc,char **argv){
 mode=argc>1?(unsigned)atoi(argv[1]):0;if(mode==6)selected=0;
 r5_grid420_watch('C',4095);
 assert(!r5_log420_state.active);
 if(!mode){assert(queries==1 && ms==0);}
 else if(mode==6){assert(!queries && !services && !ms);}
 else{
  assert(selected==2 && completed_at<=100 && services>1);
  if(mode==1)assert(queries==2 && ms<1000);
  if(mode==2)assert(ms==1000 && queries==1);
  if(mode==3 || mode==4)assert(ms<=100 && queries==1);
  if(mode==5)assert(queries==30 && services>=150);
 }
 printf("{\"mode\":%u,\"queries\":%u,\"selection_completed_ms\":%u,\"service_calls\":%u,\"elapsed_fixture_ms\":%llu}\n",mode,queries,completed_at,services,(unsigned long long)ms);
 return 0;
}
