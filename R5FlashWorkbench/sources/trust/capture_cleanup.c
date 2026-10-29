/* 仅删除当前模板绑定的RAM分块；不打开分区、不遍历历史、不递归删除。 */
#include <stddef.h>
#include <stdint.h>
#include "cleanup_config.h"
static void *cleanup_copy(void *aa,const void *bb,size_t n){char *a=aa;const char *b=bb;for(size_t i=0;i<n;i++)a[i]=b[i];return aa;}
#define memcpy cleanup_copy
#include "sha256.h"
struct cleanup_stat {u64 dev,ino;unsigned mode,nlink,uid,gid;u64 rdev,pad;s64 size;unsigned blksize,pad2;u64 blocks,rest[7];};
_Static_assert(sizeof(struct cleanup_stat)==128,"stat ABI");
static struct cleanup_stat cleanup_parts[CAPTURE_PART_COUNT];
static unsigned char cleanup_entries[131072];
static volatile unsigned char cleanup_seen[CAPTURE_PART_COUNT];
static char cleanup_buf[65536];
static unsigned cleanup_deleted;

static int cleanup_stat_fd(int fd,struct cleanup_stat *st,int directory,u64 dev){
    if(sc(80,fd,P(st),0,0,0,0)<0||st->uid||st->dev!=dev)return 0;
    if(directory)return (st->mode&0170000)==0040000&&(st->mode&0777)==0700;
    return (st->mode&0170000)==0100000&&st->nlink==1;
}
static int cleanup_openat(int dir,const char *name,int flags){return (int)sc(56,dir,P(name),flags|NOFOLLOW|CLOEXEC,0,0,0);}
static s64 cleanup_read(int dir,const char *name,char *raw,u64 cap,u64 dev){
    int fd=cleanup_openat(dir,name,RDONLY);if(fd<0)return -1;
    struct cleanup_stat st;int valid=cleanup_stat_fd(fd,&st,0,dev)&&st.size>=0&&(u64)st.size<=cap;
    s64 n=valid?sc(67,fd,P(raw),st.size,0,0,0):-1;
    if(close_fd(fd)<0||!valid||n!=st.size)return -1;
    return n;
}
static int cleanup_source(int control,u64 dev,char digest[65]){
    char raw[512],expected[512];
    s64 n=cleanup_read(control,"task.claim",raw,sizeof(raw),dev);
    if(n!=(s64)sizeof(TICKET_BYTES)-1||!same(raw,TICKET_BYTES,n))return 0;
    n=cleanup_read(control,"task.output",raw,sizeof(raw),dev);
    const char begin[]=CAPTURE_BEGIN "A7R5_CAPTURE_COMPLETE ";
    const char end[]=CAPTURE_SUMMARY CAPTURE_END;
    u64 length=sizeof(begin)-1+64+sizeof(end)-1;
    if(n!=(s64)length||!same(raw,begin,sizeof(begin)-1)||!same(raw+sizeof(begin)-1+64,end,sizeof(end)-1))return 0;
    for(unsigned i=0;i<64;i++){
        char c=raw[sizeof(begin)-1+i];if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return 0;
        digest[i]=c;
    }
    digest[64]=0;
    u64 at=append(expected,0,"A7R5-JIT-1 " RUN_ID " DONE 0 uid=0 euid=0 bytes=");
    at=number(expected,at,(s64)length);at=append(expected,at," disarmed=1 children=0\n");
    n=cleanup_read(control,"task.state",raw,sizeof(raw),dev);
    return n==(s64)at&&same(raw,expected,at);
}
static void cleanup_name(char path[64],unsigned index){u64 n=append(path,0,"partition.bin.part-");n=number(path,n,index);path[n]=0;}
static int cleanup_directory_entries(int dir){
    unsigned char *entries=cleanup_entries;unsigned count=0;
    for(unsigned i=0;i<CAPTURE_PART_COUNT;i++)cleanup_seen[i]=0;
    for(;;){
        s64 n=sc(61,dir,P(entries),sizeof(cleanup_entries),0,0,0);if(n<0)return 0;if(!n)break;
        for(s64 at=0;at<n;){
            if(n-at<20)return 0;
            unsigned len=entries[at+16]|((unsigned)entries[at+17]<<8);
            if(len<20||at+len>n)return 0;
            const char *name=(char *)entries+at+19;unsigned size=0;
            while(size<len-19&&name[size])size++;
            if(size==len-19)return 0;at+=len;
            if((size==1&&name[0]=='.')||(size==2&&same(name,"..",2)))continue;
            int found=0;
            for(unsigned i=0;i<CAPTURE_PART_COUNT;i++){
                char fixed[64];cleanup_name(fixed,i);u64 length=0;while(fixed[length])length++;
                if(size==length&&same(name,fixed,length)){
                    if(cleanup_seen[i])return 0;cleanup_seen[i]=1;count++;found=1;break;
                }
            }
            if(!found)return 0;
        }
    }
    return count==CAPTURE_PART_COUNT;
}
static int cleanup_body(char digest[65]){
    if(sc(174,0,0,0,0,0,0)||sc(175,0,0,0,0,0,0))return 60;
    char a[128],b[128],preload[4096],again[4096];
    s64 n=sc(78,AT_FDCWD,P("/proc/self/ns/mnt"),P(a),sizeof(a),0,0);
    s64 m=sc(78,AT_FDCWD,P("/proc/1/ns/mnt"),P(b),sizeof(b),0,0);
    if(n<=0||n>=128||n!=m||!same(a,b,n))return 60;
    n=bounded("/etc/ld.so.preload",preload,sizeof(preload));
    if(!((n==(s64)sizeof(PRELOAD_A)-1&&same(preload,PRELOAD_A,n))||
         (n==(s64)sizeof(PRELOAD_B)-1&&same(preload,PRELOAD_B,n))))return 61;
    int parent=(int)open_file(CLEANUP_PARENT,RDONLY|16384|NOFOLLOW|CLOEXEC);if(parent<0)return 62;
    struct cleanup_stat pst,dir_stat,control_stat; s64 fs[15];int dir=-1,control=-1,code=0;
    if(sc(80,parent,P(&pst),0,0,0,0)<0||pst.uid||(pst.mode&0170000)!=0040000||
       sc(44,parent,P(fs),0,0,0,0)<0||fs[0]!=0x01021994||(fs[10]&1)){code=62;goto done;}
    dir=cleanup_openat(parent,CLEANUP_DIRECTORY,RDONLY|16384);
    control=cleanup_openat(parent,SOURCE_CONTROL_DIRECTORY,RDONLY|16384);
    if(dir<0||control<0||!cleanup_stat_fd(dir,&dir_stat,1,pst.dev)||
       !cleanup_stat_fd(control,&control_stat,1,pst.dev)){code=63;goto done;}
    if(!cleanup_source(control,pst.dev,digest)){code=64;goto done;}
    if(!cleanup_directory_entries(dir)){code=65;goto done;}
    struct sha_ctx hash;sha_init(&hash);
    for(unsigned i=0;i<CAPTURE_PART_COUNT;i++){
        char name[64];cleanup_name(name,i);int fd=cleanup_openat(dir,name,RDONLY);
        u64 bytes=25100288UL-i*CAPTURE_PART_BYTES;
        if(bytes>CAPTURE_PART_BYTES)bytes=CAPTURE_PART_BYTES;
        if(fd<0){code=66;goto done;}
        if(!cleanup_stat_fd(fd,&cleanup_parts[i],0,pst.dev)||cleanup_parts[i].size!=(s64)bytes)code=66;
        for(u64 at=0;!code&&at<bytes;at+=sizeof(cleanup_buf)){
            u64 size=bytes-at;if(size>sizeof(cleanup_buf))size=sizeof(cleanup_buf);
            if(sc(67,fd,P(cleanup_buf),size,at,0,0)!=(s64)size){code=67;break;}
            sha_add(&hash,cleanup_buf,size);
        }
        if(close_fd(fd)<0&&!code)code=67;if(code)goto done;
    }
    char actual[65],repeat[65];sha_end(&hash,actual);
    if(!same(actual,digest,65)||!cleanup_source(control,pst.dev,repeat)||!same(repeat,digest,65)){code=68;goto done;}
    m=bounded("/etc/ld.so.preload",again,sizeof(again));
    if(m!=n||!same(preload,again,n)){code=69;goto done;}
    for(unsigned i=0;i<CAPTURE_PART_COUNT;i++){
        char name[64];cleanup_name(name,i);struct cleanup_stat st;
        if(sc(79,dir,P(name),P(&st),256,0,0)<0||st.dev!=cleanup_parts[i].dev||st.ino!=cleanup_parts[i].ino||
           st.mode!=cleanup_parts[i].mode||st.nlink!=1||st.uid||st.size!=cleanup_parts[i].size){code=70;goto done;}
        if(sc(35,dir,P(name),0,0,0,0)<0){code=71;goto done;}
        cleanup_deleted++;
        if(sc(79,dir,P(name),P(&st),256,0,0)!=-2){code=72;goto done;}
    }
    struct cleanup_stat st;
    if(sc(79,parent,P(CLEANUP_DIRECTORY),P(&st),256,0,0)<0||st.dev!=dir_stat.dev||st.ino!=dir_stat.ino){code=73;goto done;}
    if(sc(35,parent,P(CLEANUP_DIRECTORY),512,0,0,0)<0||
       sc(79,parent,P(CLEANUP_DIRECTORY),P(&st),256,0,0)!=-2){code=74;goto done;}
done:
    if(control>=0&&close_fd(control)<0&&!code)code=75;
    if(dir>=0&&close_fd(dir)<0&&!code)code=75;
    if(close_fd(parent)<0&&!code)code=75;
    return code;
}
static int native_task(int output){
    (void)sha_bytes;
    char digest[65],row[512];cleanup_deleted=0;int code=cleanup_body(digest);u64 n;
    if(code){
        n=append(row,0,"A7R5_CAPTURE_CLEANUP_FAILED " RUN_ID " deleted=");n=number(row,n,cleanup_deleted);
        n=append(row,n," code=");n=number(row,n,code);row[n++]='\n';
    }else{
        n=append(row,0,"A7R5_CAPTURE_CLEANUP " RUN_ID " sha256=");n=append(row,n,digest);
        n=append(row,n," deleted=");n=number(row,n,CAPTURE_PART_COUNT);
        n=append(row,n," bytes=25100288 directory_removed=1\n");
    }
    if(write_all(output,row,n)&&!code)code=76;
    return code;
}
