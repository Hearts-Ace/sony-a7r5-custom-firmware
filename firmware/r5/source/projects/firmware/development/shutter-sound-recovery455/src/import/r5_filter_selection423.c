#include "r5_filter_selection423.h"
#include "r5_lut_directory.h"
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t *p,uint32_t v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);p[2]=(uint8_t)(v>>16);p[3]=(uint8_t)(v>>24);}
static uint32_t crc(const uint8_t *p,unsigned n,unsigned at){uint32_t c=~0u;unsigned i,j;for(i=0;i<n;i++){c^=(i>=at && i<at+4)?0:p[i];for(j=0;j<8;j++)c=(c>>1)^((0u-(c&1u))&0xedb88320u);}return ~c;}
int r5_filter_select_is_envelope(const uint8_t *p,size_t n){return p && n>=8 && p[0]==R5_FILTER_SELECT_CLASS && get32(p+4)==R5_FILTER_SELECT_MAGIC;}
int r5_filter_select_encode(const struct r5_filter_select_request *r,uint8_t p[32]){
    unsigned i;uintptr_t a=(uintptr_t)r,b=(uintptr_t)p;
    if(!r || !p || !r->sequence || !r->alias || r->selected>12 ||
       (b>=a?b-a<sizeof(*r):a-b<32))return 0;
    for(i=0;i<32;i++)p[i]=0;
    p[0]=R5_FILTER_SELECT_CLASS;p[1]=1;p[2]=R5_FILTER_SELECT_SET;p[3]=32;
    put32(p+4,R5_FILTER_SELECT_MAGIC);put32(p+8,r->sequence);put32(p+12,r->selected);
    put32(p+16,r->payload_crc);put32(p+20,r->alias);put32(p+28,crc(p,32,28));return 1;
}
int r5_filter_select_ack(const struct r5_filter_select_request *r,const uint8_t *p,size_t n){
    uint32_t status;
    if(!r || !r->sequence || !r->alias || r->selected>12 || n!=32 ||
       !r5_filter_select_is_envelope(p,n) || p[1]!=1 || p[2]!=R5_FILTER_SELECT_ACK || p[3]!=32 ||
       get32(p+8)!=r->sequence || get32(p+12)!=r->selected || get32(p+16)!=r->payload_crc ||
       get32(p+20)!=r->alias || get32(p+28)!=crc(p,32,28))return -256;
    status=get32(p+24);if(status>R5_F_BAD_BANK)return -256;return status?-(int)status:1;
}
static int ready(struct r5_lut_directory *d){return d && d->phase==2 && d->fd>=0 && d->api.openat && d->api.read && d->api.write && d->api.close && d->api.sync && d->api.renameat && d->api.unlinkat && d->api.error_number;}
static void encode(unsigned selected,uint8_t p[24]){
    static const uint8_t magic[8]={'R','5','S','E','L','4',0,0};unsigned i;
    for(i=0;i<24;i++)p[i]=0;for(i=0;i<8;i++)p[i]=magic[i];put32(p+8,1);put32(p+12,selected);put32(p+20,crc(p,24,20));
}
static int decode(const uint8_t p[24],unsigned *out){
    uint8_t expected[24];unsigned i,selected=get32(p+12);if(selected>12)return -1;
    encode(selected,expected);for(i=0;i<24;i++)if(p[i]!=expected[i])return -1;*out=selected;return 0;
}
static int read_exact(struct r5_lut_directory *d,const char *name,uint8_t p[24]){
    int fd,rc=R5_IO_ERROR;uint8_t bytes[25];size_t used=0;unsigned calls=0;intptr_t got;
    fd=d->api.openat(d->fd,name,0x8000,0);
    if(fd<0){int *e=d->api.error_number();return e && *e==2?R5_ABSENT:R5_IO_ERROR;}
    while(calls++<26){got=d->api.read(fd,bytes+used,25-used);if(got<0 || (size_t)got>25-used)break;
        if(!got){if(used==24){unsigned i;for(i=0;i<24;i++)p[i]=bytes[i];rc=R5_IMPORTED;}else rc=R5_INVALID;break;}
        used+=(size_t)got;if(used==25){rc=R5_INVALID;break;}}
    if(d->api.close(fd))return R5_IO_ERROR;return rc;
}
int r5_filter_selection_load(struct r5_lut_directory *d,unsigned *out){
    uint8_t p[24];unsigned selected;int rc;if(!ready(d) || !out)return R5_INVALID;
    rc=read_exact(d,R5_FILTER_SELECTION_FILE,p);if(rc!=R5_IMPORTED)return rc;
    if(decode(p,&selected))return R5_INVALID;*out=selected;return R5_IMPORTED;
}
int r5_filter_selection_save(struct r5_lut_directory *d,unsigned selected){
    uint8_t expected[24],check[24];int fd,rc=2;unsigned i;size_t used=0;intptr_t wrote;
    if(!ready(d) || selected>12)return 1;encode(selected,expected);
    /* Sole worker owns this exact staging basename. A prior interrupted stage
     * is discarded before exclusive create; active BIN is never truncated. */
    if(d->api.unlinkat(d->fd,R5_FILTER_SELECTION_PENDING,0)){int *e=d->api.error_number();if(!e || *e!=2)return 2;}
    fd=d->api.openat(d->fd,R5_FILTER_SELECTION_PENDING,0x80c1,0600);if(fd<0)return 2;
    while(used<24){wrote=d->api.write(fd,expected+used,24-used);if(wrote<=0 || (size_t)wrote>24-used)goto close;used+=(size_t)wrote;}
    if(!d->api.sync(fd))rc=0;
close:
    if(d->api.close(fd))rc=2;
    if(rc){(void)d->api.unlinkat(d->fd,R5_FILTER_SELECTION_PENDING,0);return rc;}
    if(read_exact(d,R5_FILTER_SELECTION_PENDING,check)!=R5_IMPORTED)return 2;
    for(i=0;i<24;i++)if(check[i]!=expected[i])return 2;
    if(d->api.renameat(d->fd,R5_FILTER_SELECTION_PENDING,d->fd,R5_FILTER_SELECTION_FILE))return 3;
    if(d->api.sync(d->fd))return 3;return 0;
}
