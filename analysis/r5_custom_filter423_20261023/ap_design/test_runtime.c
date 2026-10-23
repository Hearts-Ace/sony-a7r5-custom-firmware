#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "r5_filter_runtime423.h"
#include "r5_filter_selection423.h"
#include "r5_filter423.h"
#include "r5_runtime_session.h"
#include "r5_native_lut_directory.h"
static unsigned clock_ms,refreshes,sends,send_fail,inject_new,inject_late,store_fail,inject_power,last_sequence;
static uint8_t saved_file[24],pending_file[24];static unsigned saved_len,pending_len,pos,reading_stage;static int error_no;
struct time423 {int64_t sec,ns;};
static uint32_t get32(const uint8_t*p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t*p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
static uint32_t crc(uint8_t*p){uint32_t c=~0u;for(unsigned i=0;i<32;i++){c^=i>=28?0:p[i];for(unsigned j=0;j<8;j++)c=(c>>1)^((0u-(c&1u))&0xedb88320u);}return ~c;}
static int sleep_fixture(const void*p,void*x){(void)x;const struct time423*t=p;clock_ms+=(unsigned)(t->sec*1000+t->ns/1000000);return 0;}
static int clock_fixture(int n,struct time423*t){assert(n==1);t->sec=clock_ms/1000;t->ns=(clock_ms%1000)*1000000;return 0;}
void *r5_stage411_dlsym(void*p,const char*n){(void)p;if(!strcmp(n,"nanosleep"))return (void*)sleep_fixture;if(!strcmp(n,"clock_gettime"))return(void*)clock_fixture;return 0;}
void *r5_stage411_child(void*p){return p;}void r5_stage421_probe_reset(void){}void r5_stage421_transfer_reset(void){}void r5_stage421_log_reset(void){}
void r5_native_creative_sequence_request(const void*p){assert(((const uint32_t*)p)[1]==1);refreshes++;}
uint32_t r5_osal_msg_size(const void*p){(void)p;return 32;}
int r5_native_ap_send(void*x,const uint8_t*p,size_t n){(void)x;uint8_t ack[32];assert(n==32);sends++;last_sequence=get32(p+8);if(send_fail)return -1;memcpy(ack,p,32);ack[2]=0x81;
 if(inject_late){uint8_t late[32];memcpy(late,ack,32);put32(late+8,get32(late+8)-1);put32(late+28,crc(late));assert(r5_filter_inbound(late,0x90030001)==1);inject_late=0;}
 if(inject_new){inject_new=0;assert(!r5_filter_request(2));}
 put32(ack+28,crc(ack));assert(r5_filter_inbound(ack,0x90030001)==1);if(inject_power){uint32_t event=0x920143;inject_power=0;r5_stage421_power(&event);}return 0;}
static int openat_fixture(int d,const char*n,int f,unsigned mode){(void)mode;assert(d==9);pos=0;if(f==0x80c1){pending_len=0;return 11;}reading_stage=!strcmp(n,R5_FILTER_SELECTION_PENDING);if(!(reading_stage?pending_len:saved_len)){error_no=2;return-1;}return 10;}
static intptr_t read_fixture(int fd,void*out,size_t n){(void)fd;unsigned len=reading_stage?pending_len:saved_len;if(n>len-pos)n=len-pos;memcpy(out,(reading_stage?pending_file:saved_file)+pos,n);pos+=(unsigned)n;return(intptr_t)n;}
static intptr_t write_fixture(int fd,const void*p,size_t n){assert(fd==11);if(store_fail)return-1;memcpy(pending_file+pending_len,p,n);pending_len+=(unsigned)n;return(intptr_t)n;}
static int close_fixture(int fd){(void)fd;return 0;}static int sync_fixture(int fd){(void)fd;return 0;}
static int rename_fixture(int d,const char*a,int e,const char*b){assert(d==9&&e==9&&!strcmp(a,R5_FILTER_SELECTION_PENDING)&&!strcmp(b,R5_FILTER_SELECTION_FILE));memcpy(saved_file,pending_file,pending_len);saved_len=pending_len;pending_len=0;return 0;}
static int unlink_fixture(int d,const char*n,int f){assert(d==9&&!strcmp(n,R5_FILTER_SELECTION_PENDING)&&!f);pending_len=0;return 0;}static int*errno_fixture(void){return &error_no;}
int r5_native_lut_directory_api_init(struct r5_lut_directory_api*a){memset(a,0,sizeof(*a));a->openat=openat_fixture;a->read=read_fixture;a->write=write_fixture;a->close=close_fixture;a->sync=sync_fixture;a->renameat=rename_fixture;a->unlinkat=unlink_fixture;a->error_number=errno_fixture;return 0;}
int r5_lut_directory_acquire(struct r5_lut_directory*d,const struct r5_lut_directory_api*a,uint8_t*s,size_t n){(void)s;assert(n==65537);d->api=*a;d->phase=2;d->fd=9;return 0;}int r5_lut_directory_release(struct r5_lut_directory*d){assert(d->phase==2);d->phase=3;return 0;}
int main(int argc,char **argv){(void)argv;struct r5_look_set set={0};unsigned total=0;set.valid_mask=3;for(unsigned i=0;i<2;i++){strcpy(set.look[i].short_name,i?"Two":"One");strcpy(set.look[i].full_name,i?"Filter two":"Filter one");for(unsigned j=0;j<129;j++)set.look[i].gamma[j]=j*1000;}assert(r5_filter_names_publish(&set)==1);
 if(argc>1){struct r5_lut_directory d={0};struct r5_lut_directory_api a;uint32_t event;
 r5_native_lut_directory_api_init(&a);assert(!r5_lut_directory_acquire(&d,&a,pending_file,65537));
 assert(!r5_filter_selection_save(&d,2));r5_filter_load_selection(&d);r5_session_cold();assert(r5_session_prepare());r5_filter_bank_ready(20,30,3);r5_filter_service();assert(r5_filter_selected()==2&&sends==1);
 assert(!r5_filter_request(1));r5_filter_load_selection(&d);r5_filter_bank_ready(21,30,3);r5_filter_service();assert(r5_filter_selected()==1&&get32(saved_file+12)==1);
 event=0x920143;r5_stage421_power(&event);event=0x92015a;r5_stage421_power(&event);assert(r5_session_prepare());r5_filter_load_selection(&d);r5_filter_bank_ready(22,30,3);r5_session_finish();r5_filter_service();assert(r5_filter_selected()==1&&sends==3);
 printf("{\"passed\":true,\"camera_io\":false,\"scenarios\":3,\"scope\":\"cold persisted selection restore, UI request wins late sidecar read, retained wake reload\"}\n");return 0;}
 assert(r5_filter_request(1)==-1);r5_session_cold();assert(r5_session_prepare());r5_filter_bank_ready(10,20,3);r5_filter_service();assert(r5_filter_selected()==0 && refreshes==1&&sends==1);total++;
 r5_session_finish();assert(r5_session_current());assert(!r5_filter_request(1));r5_filter_service();assert(r5_filter_selected()==1&&!r5_filter_pending()&&refreshes==2&&get32(saved_file+12)==1);total++;
 inject_late=1;assert(!r5_filter_request(2));r5_filter_service();assert(r5_filter_selected()==2&&refreshes==3);total++;
 inject_new=1;assert(!r5_filter_request(1));r5_filter_service();assert(r5_filter_selected()==1&&r5_filter_pending());r5_filter_service();assert(r5_filter_selected()==2&&!r5_filter_pending());total++;
 unsigned before=sends;send_fail=1;assert(!r5_filter_request(1));for(unsigned i=0;i<5;i++)r5_filter_service();assert(sends==before+3&&r5_filter_selected()==2&&r5_filter_pending());send_fail=0;assert(!r5_filter_request(1));r5_filter_service();assert(r5_filter_selected()==1);total++;
 store_fail=1;before=sends;assert(!r5_filter_request(2));for(unsigned i=0;i<5;i++)r5_filter_service();assert(sends==before&&r5_filter_selected()==1);store_fail=0;assert(!r5_filter_request(2));r5_filter_service();assert(r5_filter_selected()==2);total++;
 uint32_t event=0x920143;r5_stage421_power(&event);before=sends;assert(!r5_filter_request(1));r5_filter_service();assert(sends==before);event=0x92015a;r5_stage421_power(&event);assert(r5_session_prepare());r5_filter_bank_ready(11,20,3);r5_session_finish();r5_filter_service();assert(r5_filter_selected()==1 && sends==before+1);total++;
 /* A changed valid mask invalidates an absent selected slot and restores off. */
 set.valid_mask=2;assert(r5_filter_names_publish(&set)==1);r5_filter_bank_ready(12,21,2);r5_filter_service();assert(r5_filter_selected()==0&&!r5_filter_pending()&&get32(saved_file+12)==0);assert(r5_filter_request(1)==-1);total++;
 /* Reannouncing the identical accepted bank must not rewind SELECT serials. */
 unsigned prior_sequence=last_sequence;r5_filter_bank_ready(12,21,2);r5_filter_service();assert(last_sequence==prior_sequence+1&&r5_filter_selected()==0&&!r5_filter_pending());total++;
 /* A power epoch change after delivery prevents stale AP state/refresh. */
 unsigned prior_refreshes=refreshes;inject_power=1;assert(!r5_filter_request(2));r5_filter_service();assert(r5_filter_selected()==0&&refreshes==prior_refreshes&&r5_filter_pending());event=0x92015a;r5_stage421_power(&event);assert(r5_session_prepare());r5_filter_bank_ready(13,21,2);r5_filter_service();assert(r5_filter_selected()==2&&refreshes==prior_refreshes+1&&!r5_filter_pending());total++;
 printf("{\"passed\":true,\"camera_io\":false,\"scenarios\":%u,\"sends\":%u,\"native_refreshes\":%u,\"scope\":\"compiled AP runtime with real session/protocol/sidecar; files, clocks, scheduler and native transport are fixtures\"}\n",total,sends,refreshes);return 0;}
