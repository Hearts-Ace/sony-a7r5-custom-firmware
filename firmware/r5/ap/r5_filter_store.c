#include "r5_filter_store.h"
#include "r5_runtime_session.h"
#include "r5_native_lut_directory.h"
extern void *r5_stage411_dlsym(void *,const char *);
struct store {
    struct r5_lut_directory directory;
    intptr_t (*pread)(int,void *,size_t,int64_t);
    void (*free)(void *);
    void *scratch;
    uintptr_t file;
    int opened;
};
static int begin(struct store *s){
    struct r5_lut_directory_api api;
    void *(*allocate)(size_t)=(void *)r5_stage411_dlsym(0,"malloc");
    s->free=(void *)r5_stage411_dlsym(0,"free");
    s->pread=(void *)r5_stage411_dlsym(0,"pread");
    if(!allocate||!s->free||!s->pread||r5_native_lut_directory_api_init(&api))return -1;
    s->scratch=allocate(65537);if(!s->scratch)return -1;
    if(r5_lut_directory_acquire(&s->directory,&api,s->scratch,65537)){s->free(s->scratch);s->scratch=0;return -1;}
    /* Mountinfo scratch is never retained during file IO or transport waits. */
    s->free(s->scratch);s->scratch=0;return 0;
}
static int end(struct store *s,int result){
    if(s->opened&&r5_lut_directory_close(&s->directory,s->file))result=-1;
    if(s->directory.phase==2&&r5_lut_directory_release(&s->directory))result=-1;
    if(s->scratch)s->free(s->scratch);return result;
}
static int read_at(void *ctx,uint32_t offset,uint8_t *out,size_t n,size_t *actual){
    struct store *s=ctx;intptr_t got;
    *actual=0;if(!s->opened||n>R5F_MAX+1)return -1;
    got=s->pread((int)s->file,out,n,(int64_t)offset);
    if(got<0||(size_t)got>n)return -1;*actual=(size_t)got;return 0;
}
int r5_filter_store_available(void){struct store s={0};if(begin(&s))return -1;return end(&s,0);}
int r5_filter_store_index(struct r5f_index *index){
    struct store s={0};size_t used=0,got;int rc;uint8_t *bytes;
    void *(*allocate)(size_t)=(void *)r5_stage411_dlsym(0,"malloc");
    if(!allocate||begin(&s))return -1;
    rc=r5_lut_directory_read_open(&s.directory,R5_LOOK_STORE,&s.file);
    if(rc)return end(&s,rc==1?1:-1);s.opened=1;
    bytes=allocate(R5F_MAX+1);if(!bytes)return end(&s,-1);s.scratch=bytes;
    do{got=0;rc=read_at(&s,(uint32_t)used,bytes+used,R5F_MAX+1-used,&got);
       if(rc)break;used+=got;}while(got&&used<R5F_MAX+1);
    rc=rc?-1:r5f_index_bytes(bytes,used,index);return end(&s,rc);
}
int r5_filter_store_publish(const uint8_t *bytes,size_t length,struct r5f_index *index){
    struct store s={0};struct r5f_index next;uint8_t chunk[512];size_t used,got;int rc=-1;
    if(r5f_index_bytes(bytes,length,&next)||begin(&s))return -1;
    if(r5_lut_directory_unlink(&s.directory,R5_LOOK_PENDING)||r5_lut_directory_create(&s.directory,R5_LOOK_PENDING,&s.file))goto done;
    s.opened=1;
    for(used=0;used<length;used+=got){
        got=0;if(r5_lut_directory_write(&s.directory,s.file,bytes+used,length-used,&got)||!got||got>length-used)goto done;
    }
    if(r5_lut_directory_sync(&s.directory,s.file))goto done;
    if(r5_lut_directory_close(&s.directory,s.file)){s.opened=0;goto done;}s.opened=0;
    if(r5_lut_directory_read_open(&s.directory,R5_LOOK_PENDING,&s.file))goto done;s.opened=1;
    for(used=0;used<length;used+=got){
        size_t n=length-used;if(n>sizeof(chunk))n=sizeof(chunk);got=0;
        if(read_at(&s,(uint32_t)used,chunk,n,&got)||!got||got>n)goto done;
        for(size_t i=0;i<got;i++)if(chunk[i]!=bytes[used+i])goto done;
    }
    got=0;if(read_at(&s,(uint32_t)length,chunk,1,&got)||got)goto done;
    if(r5_lut_directory_close(&s.directory,s.file)){s.opened=0;goto done;}s.opened=0;
    if(!r5_session_current()||s.directory.api.renameat(s.directory.fd,"R5NATIVE.NEW",s.directory.fd,"R5NATIVE.BIN")||s.directory.api.sync(s.directory.fd))goto done;
    *index=next;rc=0;
done:return end(&s,rc);
}
int r5_filter_store_read(const struct r5f_index *index,unsigned slot,uint8_t compact[R5F_COMPACT]){
    struct store s={0};struct r5f_reader reader={&s,read_at};int rc;
    if(begin(&s))return -1;
    rc=r5_lut_directory_read_open(&s.directory,R5_LOOK_STORE,&s.file);
    if(rc)return end(&s,-1);s.opened=1;
    rc=r5f_read_one(&reader,index,slot,compact);return end(&s,rc);
}

#define R5_FILTER_SELECTION_FILE "R5FILTER.BIN"
#define R5_FILTER_SELECTION_PENDING "R5FILTER.NEW"
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t *p,uint32_t v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);p[2]=(uint8_t)(v>>16);p[3]=(uint8_t)(v>>24);}
static uint32_t crc(const uint8_t *p,unsigned n,unsigned at){uint32_t c=~0u;unsigned i,j;for(i=0;i<n;i++){c^=(i>=at && i<at+4)?0:p[i];for(j=0;j<8;j++)c=(c>>1)^((0u-(c&1u))&0xedb88320u);}return ~c;}
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
static int selection_load(struct r5_lut_directory *d,unsigned *out){
    uint8_t p[24];unsigned selected;int rc;if(!ready(d) || !out)return R5_INVALID;
    rc=read_exact(d,R5_FILTER_SELECTION_FILE,p);if(rc!=R5_IMPORTED)return rc;
    if(decode(p,&selected))return R5_INVALID;*out=selected;return R5_IMPORTED;
}
static int selection_save(struct r5_lut_directory *d,unsigned selected){
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
    if(!r5_session_current()||d->api.renameat(d->fd,R5_FILTER_SELECTION_PENDING,d->fd,R5_FILTER_SELECTION_FILE))return 3;
    if(d->api.sync(d->fd))return 3;return 0;
}

int r5_filter_store_selection(unsigned *selected,int write){
    struct store s={0};int rc;
    if(!selected||begin(&s))return -1;
    rc=write?selection_save(&s.directory,*selected):selection_load(&s.directory,selected);
    return end(&s,rc);
}
