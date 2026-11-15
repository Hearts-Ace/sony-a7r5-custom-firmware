/* AP owner handoff with a stateful CP actor and original Look sentinels. */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "r5_filter_runtime.h"
#include "job.h"
static unsigned epoch=1,live=1,active,reads,saves,prepare_sends,abort_sends,collect_sends,requests,tags,stock;
static unsigned mode,slot_focus,initial_look,look_gets,look_sets,repeats,save_error,retired,previous_cookie,power_loss;
static unsigned prep_slot,prep_cookie,phase;
static uint64_t tick;
static uint8_t prep[32];
static struct r5j_object exact,foreign;
static int deferred;
static uint32_t crc(const uint8_t *p,size_t n){uint32_t c=~0u;for(size_t i=0;i<n;i++){c^=(i>=28&&i<32)?0:p[i];for(unsigned b=0;b<8;b++)c=(c>>1)^(0xedb88320u&(0u-(c&1u)));}return ~c;}
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
static void check(int ok,const char *what){if(!ok){fprintf(stderr,"mode %u FAIL %s\n",mode,what);exit(1);}}
struct time_value {int64_t sec,ns;};
static int clock_value(int id,struct time_value *out){(void)id;out->sec=(int64_t)(tick/1000);out->ns=(int64_t)(tick%1000)*1000000;return 0;}
static int sleep_value(const void *in,void *out){const struct time_value *t=in;(void)out;tick+=(uint64_t)t->sec*1000+(uint64_t)t->ns/1000000;return 0;}
void *r5_stage411_dlsym(void *handle,const char *name){(void)handle;if(!strcmp(name,"clock_gettime"))return (void *)clock_value;if(!strcmp(name,"nanosleep"))return (void *)sleep_value;return 0;}
int r5_session_current(void){return live;}
uint32_t r5_session_epoch(void){return epoch;}
uint32_t r5_osal_msg_size(const void *p){(void)p;return 40;}
unsigned r5_filter_pt_native_get(void){look_gets++;return initial_look;}
void r5_filter_pt_native_set(unsigned n){(void)n;look_sets++;}
static void send_ack(const uint8_t *request,unsigned op,unsigned status,unsigned detail,unsigned corrupt){
    uint8_t a[40];memcpy(a,request,32);a[2]=(uint8_t)(op|0x80);put32(a+24,8);put32(a+32,status);put32(a+36,detail);
    if(corrupt==1)put32(a+12,get32(a+12)-1);
    if(corrupt==2)put32(a+8,get32(a+8)-1);
    put32(a+28,crc(a,sizeof(a)));if(corrupt==3)a[28]^=1;
    check(r5_filter_inbound(a,0x90030001u)==1,"private response consumed");
}
void r5_native_serialize_color(uint32_t mode_native,uint32_t look,uint8_t *out){out[0]=(uint8_t)(mode_native?0:look);}
void r5_native_refresh_construct425(void *object,const void *params){
    (void)params;memset(object,0x39,sizeof(exact));put32((uint8_t *)object+0x1c,initial_look);
    if(object==&exact&&slot_focus==1&&mode==6)((uint8_t *)object)[0x1d]=1;
}
void r5_native_refresh_execute425(void *object){
    uint8_t *p=object,wire[4]={0};unsigned look=get32(p+0x1c),cookie;
    if(object==&exact||object==&foreign){stock++;check(!(look&R5S_TAG),"native objects never mutated");return;}
    check((look&255)==initial_look,"tagged copy preserves stock selector");
    r5_filter_serialize_color(0,look,wire);
    check(wire[0]==initial_look,"stock color byte untouched");
    cookie=((uint32_t)wire[1]|(uint32_t)wire[2]<<8|(uint32_t)(wire[3]&0x7f)<<16);
    check(wire[3]&0x80,"tag bit set");check(cookie==prep_cookie&&phase==1,"native work consumes exact prepared cookie");tags++;
    if(slot_focus==1&&mode==7)return;
    if(active)retired=2;active=prep_slot;phase=2;
    if(slot_focus==1&&(mode==3||mode==13))return;
    if(slot_focus==1&&mode==9){send_ack(prep,R5S_ACCEPT,0,cookie,2);send_ack(prep,R5S_ACCEPT,0,cookie+1,0);send_ack(prep,R5S_ACCEPT,0,cookie,3);}
    send_ack(prep,R5S_ACCEPT,0,cookie,0);
}
void r5_native_creative_sequence_request(const void *params){
    requests++;check(!look_gets&&!look_sets,"stock Look untouched");
    check(*(const uint32_t *)((const uint8_t *)params+4)==1,"stock E4 enqueue flags");
    r5_filter_refresh_construct425(&foreign,&foreign);r5_filter_refresh_execute425(&foreign);
    r5_filter_refresh_construct425(&exact,(const uint8_t *)params+16);
    if(slot_focus==1&&mode==4){deferred=1;return;}
    if(slot_focus==1&&mode==5&&!power_loss++){live=0;epoch++;return;}
    r5_filter_refresh_execute425(&exact);
    check(!(get32((const uint8_t *)&exact+0x1c)&R5S_TAG),"original constructed bytes retained");
}
int r5_filter_store_read(const struct r5f_index *index,unsigned n,uint8_t out[R5F_COMPACT]){
    check(index&&n==slot_focus&&n,"only selected record read");reads++;
    if((mode==8&&n==1)||(mode==12&&n==2))return -1;
    for(unsigned i=0;i<R5F_COMPACT;i++)out[i]=(uint8_t)(n+i);return 0;
}
uint32_t r5f_crc(const uint8_t *p,size_t n){uint32_t c=~0u;for(size_t i=0;i<n;i++){c^=p[i];for(unsigned b=0;b<8;b++)c=(c>>1)^(0xedb88320u&(0u-(c&1u)));}return ~c;}
int r5_filter_store_selection(unsigned *n,int write){check(write==1&&*n==active,"save only authoritative native owner");saves++;if(mode==10&&*n==1&&!save_error++)return -1;return 0;}
int r5_native_ap_send(void *ctx,const uint8_t *p,size_t length){
    unsigned n=get32(p+16),op=p[2];(void)ctx;
    check(p[0]==0xe7&&p[1]==1&&!p[3]&&get32(p+4)==R5S_MAGIC,"wire envelope");check(crc(p,length)==get32(p+28),"request checksum");
    check(length==(op==R5S_PREPARE&&n?32+R5F_COMPACT:32),"only one prepared record or control");
    check(get32(p+8)==epoch+1&&get32(p+12),"AP session identity");
    if(op==R5S_PREPARE){
        prepare_sends++;check(n==slot_focus,"only intended prepare: no rollback and no prefetch");
        check((n&&get32(p+24)==R5F_COMPACT&&get32(p+20)==r5f_crc(p+32,R5F_COMPACT))||(!n&&!get32(p+20)&&!get32(p+24)),"record digest and Off layout");
        if(n==1&&mode==1&&repeats++<3){send_ack(p,op,1,0,0);return 0;}
        if(n==1&&mode==2){send_ack(p,op,4,0,0);return 0;}
        if(memcmp(prep+8,p+8,16)){memcpy(prep,p,32);prep_slot=n;prep_cookie=++previous_cookie;phase=1;}
        if(n==1&&mode==11)return 0;
        send_ack(p,op,phase==2?6u:0u,prep_cookie,n==1&&mode==14&&!repeats++?1u:0u);
    }else if(op==R5S_ABORT){
        abort_sends++;check(!memcmp(prep+8,p+8,16),"abort exact key");
        if(n==1&&mode==13&&abort_sends<=4)return 0;
        send_ack(p,op,phase==2?6u:0u,phase==2?prep_cookie:0,0);if(phase!=2)phase=0;
    }else if(op==R5S_COLLECT){
        collect_sends++;check(!n&&!get32(p+20)&&!get32(p+24),"collect no filter data");
        if(retired)retired--;send_ack(p,op,0,retired,0);
    }else check(0,"unknown AP op");
    return 0;
}
static void request(unsigned n){slot_focus=n;check(!r5_filter_request(n),"UI request");r5_filter_service();}
int main(int argc,char **argv){
    struct r5f_index index={0};unsigned before,prevrequests,prevtags;
    mode=argc>1?(unsigned)atoi(argv[1]):0;initial_look=argc>2?(unsigned)atoi(argv[2]):0;index.mask=4095;
    for(unsigned i=0;i<12;i++){index.entry[i].short_name[0]=(char)('A'+i);index.entry[i].full_name[0]=(char)('a'+i);}
    check(!r5_filter_catalog_ready(&index,0,1),"catalog ready");r5_filter_service();
    check(!active&&!reads&&!r5_filter_pending()&&requests==1&&tags==1,"boot Off tagged no record I/O");
    request(1);
    if(mode==5){
        check(r5_filter_pending()&&r5_filter_selected()==0&&active==0,"sleep did not publish selection");
        live=1;check(!r5_filter_catalog_ready(&index,0,1),"resume catalog");r5_filter_service();
        check(r5_filter_selected()==1&&active==1&&r5_filter_command_state()==2,"new epoch completes original UI selection");
    }else if(mode==2||mode==4||mode==6||mode==7||mode==8||mode==11){
        check(r5_filter_command_state()==3&&r5_filter_selected()==0&&active==0,"failure before acceptance keeps previous owner");
        if(deferred){before=tags;r5_filter_refresh_execute425(&exact);check(tags==before,"late native object is untagged");}
    }else if(mode==10){
        check(r5_filter_command_state()==3&&r5_filter_selected()==1&&active==1,"save failure truthfully exposes accepted owner");
        before=reads;prevrequests=requests;request(1);
        check(r5_filter_command_state()==2&&reads==before&&requests==prevrequests,"same accepted choice retries save without file or native task");
    }else{
        if(mode==13){
            check(r5_filter_pending()&&r5_filter_command_state()==1,"uncertain abort stays pending");
            before=reads;prevrequests=requests;tick+=1000;r5_filter_service();
            check(before==reads&&prevrequests==requests,"recover via exact control only");
        }
        check(r5_filter_selected()==1&&active==1&&r5_filter_command_state()==2,"exact native acceptance publishes 1");
        check(requests==2&&reads==1&&tags==2,"one record and one exact native job despite retries");
        if(mode==12){request(2);check(r5_filter_command_state()==3&&r5_filter_selected()==1&&active==1&&requests==2,"new record read fail does not reload previous");}
        else{
            for(unsigned n=1;n<=12;n++){prevrequests=requests;prevtags=tags;request(n);check(r5_filter_selected()==n&&active==n,"numbered owner");check(requests==prevrequests+(n!=1)&&tags==prevtags+(n!=1),"one native job per actual change");}
            before=reads;prevrequests=requests;request(0);check(!active&&!r5_filter_selected()&&reads==before&&requests==prevrequests+1,"Off tagged without file read");
            tick+=1000;r5_filter_service();check(collect_sends==1&&retired==1,"Off non-viewing retirement collects initially");
            tick+=1000;r5_filter_service();check(collect_sends==2&&!retired,"Off polls until no retired owner");
            tick+=1000;r5_filter_service();check(collect_sends==2,"Off stops polling when retired count zero");
            request(0);check(reads==before&&requests==prevrequests+1,"same durable Off no extra work");
        }
    }
    check(!strcmp(r5_filter_short_name(1),"A"),"short name");index.entry[0].short_name[0]='Z';check(r5_filter_catalog_ready(&index,0,1)==-1,"changed running catalog rejected");
    check(!strcmp(r5_filter_short_name(1),"A")&&!look_gets&&!look_sets,"original look untouched and catalog immutable");
    printf("mode=%u look=%u reads=%u native_jobs=%u tags=%u stock=%u saves=%u prepare=%u abort=%u collect=%u PASS\n",mode,initial_look,reads,requests,tags,stock,saves,prepare_sends,abort_sends,collect_sends);return 0;
}
