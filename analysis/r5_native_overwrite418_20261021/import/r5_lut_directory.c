#include "r5_lut_directory.h"

static int path_is(const char *p,const char *q) {
    size_t i;if(!p)return 0;
    for(i=0;;i++){if(p[i]!=q[i])return 0;if(!q[i])return 1;}
}
static int number(const uint8_t *p,size_t n,uint64_t *out) {
    size_t i;uint64_t v=0;if(!n)return -1;
    for(i=0;i<n;i++) {
        unsigned d=(unsigned)p[i]-'0';
        if(d>9 || v>(UINT64_MAX-d)/10)return -1;
        v=v*10+d;
    }
    if(!v)return -1;
    *out=v;return 0;
}
static int read_complete(struct r5_lut_directory *d,const char *path,uint8_t *b,
    size_t maximum,size_t *length) {
    int fd,result=-1;size_t used=0,n;unsigned calls=0;intptr_t got;
    fd=d->api.open(path,0x8000,0);if(fd<0)return -1;
    while(calls++<128) {
        n=maximum+1-used;if(n>1024)n=1024;
        got=d->api.read(fd,b+used,n);
        if(got<0 || (size_t)got>n)break;
        if(!got){*length=used;result=0;break;}
        used+=(size_t)got;if(used>maximum)break;
    }
    if(d->api.close(fd))result=-1;
    return result;
}
static int fdinfo_id(const uint8_t *p,size_t n,uint64_t *out) {
    size_t start=0,i,j;unsigned count=0;uint64_t value=0;
    static const char key[]="mnt_id:";
    if(!n || p[n-1]!='\n')return -1;
    for(i=0;i<n;i++) {
        if(!p[i] || (p[i]<32 && p[i]!='\t' && p[i]!='\n') || p[i]>126)return -1;
        if(p[i]!='\n')continue;
        if(i-start>=sizeof(key)-1) {
            for(j=0;j<sizeof(key)-1 && p[start+j]==(uint8_t)key[j];j++){}
            if(j==sizeof(key)-1) {
                if(++count!=1)return -1;
                j+=start;while(j<i && (p[j]==' ' || p[j]=='\t'))j++;
                if(number(p+j,i-j,&value))return -1;
            }
        }
        start=i+1;
    }
    if(count!=1)return -1;
    *out=value;return 0;
}
static int mount_id(const uint8_t *p,size_t n,uint64_t wanted) {
    size_t start=0,i,j,k,field;uint64_t id;
    if(r5_lut_mountinfo_check(p,n))return -1;
    for(i=0;i<n;i++)if(p[i]=='\n') {
        j=start;while(j<i && p[j]!=' ')j++;
        /* The guard already proves the tokenized record and exactly one LUT
         * mount. Match field4 and parse that same record's first token. */
        k=start;for(field=0;field<4;field++){while(k<i && p[k]!=' ')k++;k++;}
        field=k;while(k<i && p[k]!=' ')k++;
        if(k-field==sizeof("/usr/data/lut")-1) {
            static const char target[]="/usr/data/lut";size_t t;
            for(t=0;t<sizeof(target)-1 && p[field+t]==(uint8_t)target[t];t++){}
            if(t==sizeof(target)-1)return number(p+start,j-start,&id) || id!=wanted ? -1:0;
        }
        start=i+1;
    }
    return -1;
}
int r5_lut_directory_acquire(struct r5_lut_directory *d,const struct r5_lut_directory_api *a,
    uint8_t *scratch,size_t capacity) {
    static const char prefix[]="/proc/self/fdinfo/";
    char path[sizeof(prefix)+10],digits[10];unsigned n=0,i,v;size_t length=0;
    uint64_t id;
    if(!d || !a || !scratch || capacity<65537 || d->phase || !a->open || !a->openat ||
       !a->read || !a->write || !a->close || !a->sync || !a->renameat || !a->unlinkat ||
       !a->dup || !a->error_number)return -1;
    d->api=*a;d->phase=1;d->fd=d->api.open(R5_LOOK_DIRECTORY,0xc000,0);
    if(d->fd<0){d->phase=3;return -1;}
    for(i=0;i<sizeof(prefix)-1;i++)path[i]=prefix[i];
    v=(unsigned)d->fd;do{digits[n++]=(char)('0'+v%10);v/=10;}while(v);
    for(i=0;i<n;i++)path[sizeof(prefix)-1+i]=digits[n-1-i];
    path[sizeof(prefix)-1+n]=0;
    if(read_complete(d,path,scratch,4096,&length) || fdinfo_id(scratch,length,&id) ||
       read_complete(d,"/proc/self/mountinfo",scratch,65536,&length) || mount_id(scratch,length,id)) {
        int fd=d->fd;d->fd=-1;d->phase=3;d->api.close(fd);return -1;
    }
    d->mount_id=id;d->phase=2;return 0;
}
int r5_lut_directory_release(struct r5_lut_directory *d) {
    int fd;if(!d || d->phase!=2)return -1;
    fd=d->fd;d->fd=-1;d->phase=3;return d->api.close(fd)?-1:0;
}
static int ready(struct r5_lut_directory *d){return d && d->phase==2 && d->fd>=0;}
static int error(struct r5_lut_directory *d) {
    int *p=d->api.error_number();d->last_errno=p?*p:0;return -1;
}
static const char *basename_for(const char *p) {
    if(path_is(p,R5_LOOK_STORE))return "R5NATIVE.BIN";
    if(path_is(p,R5_LOOK_PENDING))return "R5NATIVE.NEW";
    return 0;
}
int r5_lut_directory_read_open(void *ctx,const char *path,uintptr_t *out) {
    struct r5_lut_directory *d=ctx;const char *name=basename_for(path);int fd;
    if(!ready(d) || !out || !name)return -1;
    fd=d->api.openat(d->fd,name,0x8000,0);
    if(fd<0){error(d);return d->last_errno==2?1:-1;}
    d->last_errno=0;*out=(uintptr_t)fd;return 0;
}
int r5_lut_directory_create(void *ctx,const char *path,uintptr_t *out) {
    struct r5_lut_directory *d=ctx;int fd;
    if(!ready(d) || !out || !path_is(path,R5_LOOK_PENDING))return -1;
    fd=d->api.openat(d->fd,"R5NATIVE.NEW",0x80c1,0600);
    if(fd<0){error(d);return d->last_errno==17?2:-1;}
    d->last_errno=0;*out=(uintptr_t)fd;return 0;
}
static int handle_ok(struct r5_lut_directory *d,uintptr_t fd) {
    return ready(d) && fd<=0x7fffffff && (int)fd!=d->fd;
}
int r5_lut_directory_read(void *ctx,uintptr_t fd,uint8_t *b,size_t n,size_t *out) {
    struct r5_lut_directory *d=ctx;intptr_t got;if(!out)return -1;*out=0;
    if(!handle_ok(d,fd) || !b || !n || n>1024)return -1;
    got=d->api.read((int)fd,b,n);if(got<0)return error(d);if((size_t)got>n)return -1;
    d->last_errno=0;*out=(size_t)got;return 0;
}
int r5_lut_directory_write(void *ctx,uintptr_t fd,const uint8_t *b,size_t n,size_t *out) {
    struct r5_lut_directory *d=ctx;intptr_t got;if(!out)return -1;*out=0;
    if(!handle_ok(d,fd) || !b || !n || n>R5_LOOK_MAX)return -1;
    got=d->api.write((int)fd,b,n);if(got<0)return error(d);if((size_t)got>n)return -1;
    d->last_errno=0;*out=(size_t)got;return 0;
}
int r5_lut_directory_close(void *ctx,uintptr_t fd) {
    struct r5_lut_directory *d=ctx;if(!handle_ok(d,fd))return -1;
    if(d->api.close((int)fd))return error(d);d->last_errno=0;return 0;
}
int r5_lut_directory_sync(void *ctx,uintptr_t fd) {
    struct r5_lut_directory *d=ctx;if(!handle_ok(d,fd))return -1;
    if(d->api.sync((int)fd))return error(d);d->last_errno=0;return 0;
}
int r5_lut_directory_open_parent(void *ctx,const char *path,uintptr_t *out) {
    struct r5_lut_directory *d=ctx;int fd;
    if(!ready(d) || !out || !path_is(path,R5_LOOK_DIRECTORY))return -1;
    fd=d->api.dup(d->fd);if(fd<0)return error(d);
    d->last_errno=0;*out=(uintptr_t)fd;return 0;
}
int r5_lut_directory_rename(void *ctx,const char *source,const char *target) {
    struct r5_lut_directory *d=ctx;
    if(!ready(d) || !path_is(source,R5_LOOK_PENDING) || !path_is(target,R5_LOOK_STORE))return -1;
    if(d->api.renameat(d->fd,"R5NATIVE.NEW",d->fd,"R5NATIVE.BIN"))return error(d);
    d->last_errno=0;return 0;
}
int r5_lut_directory_unlink(void *ctx,const char *path) {
    struct r5_lut_directory *d=ctx;if(!ready(d) || !path_is(path,R5_LOOK_PENDING))return -1;
    if(d->api.unlinkat(d->fd,"R5NATIVE.NEW",0))return error(d);
    d->last_errno=0;return 0;
}
int r5_lut_directory_bind_storage(struct r5_lut_directory *d,
    struct r5_persist_ops *persist,struct r5_stage_ops *stage) {
    if(!ready(d) || !persist || !stage)return -1;
    *persist=(struct r5_persist_ops){d,r5_lut_directory_read_open,
        r5_lut_directory_read,r5_lut_directory_close,r5_lut_directory_open_parent,
        r5_lut_directory_rename,r5_lut_directory_sync};
    *stage=(struct r5_stage_ops){d,r5_lut_directory_create,r5_lut_directory_write,
        r5_lut_directory_sync,r5_lut_directory_close,r5_lut_directory_unlink};
    return 0;
}
