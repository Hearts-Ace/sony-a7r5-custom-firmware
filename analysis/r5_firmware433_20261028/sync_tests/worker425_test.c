/* Actual worker source; native clocks, IO, transport and executor are fixtures. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "../import/r5_filter_runtime423.c"
static char events[2048];static unsigned event_count,send_count,save_count,exec_count;
static int mode,alive=1,queued,delay;static uint64_t ms;
static unsigned char command[64],foreign[64];
static void ev(char e){assert(event_count+1<sizeof events);events[event_count++]=e;events[event_count]=0;}
int r5_session_current(void){return alive;}
uint32_t r5_filter_available_mask(void){return mask;}
static int fake_clock(int id,struct time423 *t){assert(id==1);t->sec=ms/1000;t->ns=(ms%1000)*1000000;return 0;}
static int fake_sleep(const void *a,void *b){
 (void)a;(void)b;ms+=10;delay++;
 if(mode==10 && queued)alive=0;
 if(queued && mode!=2 && (mode!=11 || ms>=12000) && delay>=2){
  if(mode==1 && delay==2){r5_filter_refresh_execute425(foreign);assert(!LOAD(&refresh_done));}
  else {queued=0;r5_filter_refresh_execute425(command);}
 }
 return 0;
}
void *r5_stage411_dlsym(void *a,const char *n){(void)a;if(!strcmp(n,"clock_gettime"))return (void *)fake_clock;if(!strcmp(n,"nanosleep"))return (void *)fake_sleep;return 0;}
void r5_native_refresh_construct425(void *a,const void *b){(void)a;(void)b;}
void r5_native_refresh_execute425(void *a){(void)a;exec_count++;ev('E');}
void r5_native_creative_sequence_request(const void *a){
 assert(a==refresh_request);ev('Q');queued=1;delay=0;r5_filter_refresh_construct425(command,(const uint32_t *)a+4);
}
uint32_t r5_osal_msg_size(const void *p){(void)p;return 32;}
int r5_filter_select_is_envelope(const uint8_t *p,size_t n){return n==32 && p[0]==0xea;}
int r5_filter_select_encode(const struct r5_filter_select_request *r,uint8_t p[32]){memset(p,0,32);p[0]=0xea;p[2]=1;memcpy(p+8,r,sizeof *r);return 1;}
int r5_filter_select_ack(const struct r5_filter_select_request *r,const uint8_t *p,size_t n){if(n!=32||p[2]!=0x81||memcmp(r,p+8,sizeof *r))return -256;return p[24]?-(int)p[24]:1;}
int r5_native_ap_send(void *a,const uint8_t *p,size_t n){uint8_t reply[32];(void)a;assert(n==32);send_count++;ev('S');
 if((mode==6 || mode==12 || mode==14) && send_count==1)return 0;
 if(mode==13)return 0;
 if(mode==7 && send_count==2)return 0;
 memcpy(reply,p,32);reply[2]=0x81;
 if(mode==8 && send_count==1)reply[8]^=1;
 assert(r5_filter_inbound(reply,0x90030001)==1);return 0;}
int r5_filter_selection_load(struct r5_lut_directory *d,unsigned *n){(void)d;*n=0;return R5_IMPORTED;}
int r5_native_lut_directory_api_init(struct r5_lut_directory_api *a){memset(a,0,sizeof *a);return 0;}
int r5_lut_directory_acquire(struct r5_lut_directory *d,const struct r5_lut_directory_api *a,uint8_t *b,size_t n){(void)a;(void)b;(void)n;d->phase=2;return 0;}
int r5_lut_directory_release(struct r5_lut_directory *d){(void)d;return 0;}
int r5_filter_selection_save(struct r5_lut_directory *d,unsigned n){(void)d;assert(LOAD(&refresh_done));save_count++;ev('P');if(mode==3 && n==2)return -1;return 0;}
int r5_stage425_reload(void){ev('R');if(mode==4)return -1;if(mode==5 || mode==9)r5_filter_bank_ready(112,223,0);return 0;}
int main(int argc,char **argv){
 mode=argc>1?atoi(argv[1]):0;initialized=1;mask_ready=1;alias=111;bank_crc=222;mask=4095;saved_valid=1;
 if(mode>=11){
  desired=2;dirty=1;saved=2;
  r5_filter_service();
  assert(r5_filter_selected()==0 && dirty && attempts==1 && command_state==0);
  unsigned sends=send_count;
  for(unsigned i=0;i<10;i++){ms+=10;r5_filter_service();}
  assert(send_count==sends && attempts==1); /* backoff does not consume retries */
  if(mode==14){
   assert(!r5_filter_request(3));r5_filter_service();
   assert(r5_filter_selected()==3 && command_state==2); /* UI bypasses boot backoff */
  }else if(mode==13){
   for(unsigned i=0;i<40;i++){ms+=1000;r5_filter_service();}
   assert(attempts==30 && r5_filter_selected()==0 && command_state==0);
   sends=send_count;ms+=10000;r5_filter_service();assert(sends==send_count);
   mode=0;assert(!r5_filter_request(3));r5_filter_service();assert(r5_filter_selected()==3);
  }else{
   for(unsigned i=0;i<40 && dirty;i++){ms+=1000;r5_filter_service();}
   assert(!dirty && r5_filter_selected()==2 && saved==2 && command_state==0);
   assert(attempts>1 && attempts<=30); /* native readiness recovers on this boot */
  }
  printf("{\"mode\":%d,\"boot_recovery\":true,\"attempts\":%u,\"selected\":%u}\n",argc>1?atoi(argv[1]):0,attempts,r5_filter_selected());return 0;
 }
 if(mode==9){applied=12;saved=12;}
 if(mode==4 || mode==5 || mode==9)assert(!r5_filter_reload_request());else assert(!r5_filter_request(2));
 assert(r5_filter_command_state()==1);assert(r5_filter_request(3)==-1);assert(save_count==0);
 r5_filter_service();
 if(mode==2||mode==3||mode==4||mode==6||mode==7||mode==8||mode==10){assert(r5_filter_command_state()==3);assert(r5_filter_selected()==0);}
 else {assert(r5_filter_command_state()==2);assert(r5_filter_selected()==((mode==5||mode==9)?0:2));}
 if(mode==2){assert(save_count==0);assert(ms>=10000);}
 if(mode==4){assert(send_count==0&&save_count==0&&!strcmp(events,"R"));}
 if(mode==0){assert(!strcmp(events,"SQESP"));assert(save_count==1);}
 if(mode==1){assert(!strcmp(events,"SQEESP"));assert(save_count==1);}
 if(mode==3){assert(!strcmp(events,"SQESPSQESP"));assert(save_count==2);}
 if(mode==2 || mode==3 || mode==4 || mode==6 || mode==7 || mode==8 || mode==10){unsigned old=event_count;r5_filter_service();assert(event_count==old);}
 if(mode==2){r5_filter_refresh_execute425(command);assert(LOAD(&refresh_done)==0);}
 if(mode==6 || mode==8 || mode==10)assert(save_count==0);
 if(mode==7)assert(save_count==1 && saved==0);
 if(mode==9)assert(save_count==1 && saved==0 && r5_filter_selected()==0);
 printf("{\"mode\":%d,\"events\":\"%s\",\"state\":%u,\"selected\":%u,\"ms\":%llu}\n",mode,events,r5_filter_command_state(),r5_filter_selected(),(unsigned long long)ms);
 return 0;
}
