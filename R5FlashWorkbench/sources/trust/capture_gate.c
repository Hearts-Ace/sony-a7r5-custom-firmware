/* 固定cnflasha1只读捕获：目标仅以RDONLY打开，两次读取一致才返回成功。 */
#include <stddef.h>
#include <stdint.h>
#include "capture_config.h"
static void *copy(void *aa,const void *bb,size_t n) {char *a=aa;const char *b=bb;for(size_t i=0;i<n;i++)a[i]=b[i];return aa;}
#define memcpy copy
#include "sha256.h"
struct capture_stat {u64 dev,ino;unsigned mode,nlink,uid,gid;u64 rdev,pad;s64 size;unsigned blksize,pad2;u64 blocks,rest[7];};
_Static_assert(sizeof(struct capture_stat)==128,"stat ABI");
static char capture_buf[65536];
static int capture_memory_ready(void) {
    /* tmpfs剩余容量不代表物理内存可用；不清理旧捕获，低内存或无法核对时直接停止。 */
    s64 n=bounded("/proc/meminfo",capture_buf,sizeof(capture_buf));
    if(n<=0||n>(s64)sizeof(capture_buf))return 0;
    for(s64 at=0;at+13<n;at++)if((at==0||capture_buf[at-1]=='\n')&&same(capture_buf+at,"MemAvailable:",13)){
        at+=13;while(at<n&&(capture_buf[at]==' '||capture_buf[at]=='\t'))at++;
        s64 begin=at;u64 available=0;
        while(at<n&&capture_buf[at]>='0'&&capture_buf[at]<='9'){
            u64 digit=(u64)(capture_buf[at++]-'0');
            if(available>(~0UL-digit)/10)return 0;
            available=available*10+digit;
        }
        if(at==begin)return 0;
        while(at<n&&(capture_buf[at]==' '||capture_buf[at]=='\t'))at++;
        if(at+2>n||!same(capture_buf+at,"kB",2))return 0;
        at+=2;while(at<n&&(capture_buf[at]==' '||capture_buf[at]=='\t'))at++;
        return (at==n||capture_buf[at]=='\n')&&available>=65536UL;
    }
    return 0;
}
static int capture_preload(char *out) {
    s64 n=bounded("/etc/ld.so.preload",out,4096);
    return (n==(s64)sizeof(PRELOAD_A)-1&&same(out,PRELOAD_A,n))||(n==(s64)sizeof(PRELOAD_B)-1&&same(out,PRELOAD_B,n))?(int)n:-1;
}
static int capture_identity(int fd) {
    struct capture_stat st;u64 bytes=0;
    if(sc(80,fd,P(&st),0,0,0,0)<0)return -1;
#ifdef CAPTURE_FIXTURE
    (void)bytes;return (st.mode&0170000)==0100000&&st.size==25100288?0:-1;
#else
    return (st.mode&0170000)==0060000&&st.rdev==((252UL<<8)|129)&&sc(29,fd,0x80081272UL,P(&bytes),0,0,0)==0&&bytes==25100288?0:-1;
#endif
}
static int capture_pass(int save,char digest[65]) {
    int fd=(int)open_file(CAPTURE_TARGET,RDONLY|NOFOLLOW|CLOEXEC);
    if(fd<0)return 61;
    if(capture_identity(fd)){close_fd(fd);return 62;}
    struct sha_ctx h;sha_init(&h);int code=0,output=-1;
    const u64 step=CAPTURE_PART_BYTES<sizeof(capture_buf)?CAPTURE_PART_BYTES:sizeof(capture_buf);
    for(u64 at=0;at<25100288UL;at+=step) {
        u64 n=25100288UL-at;if(n>step)n=step;
        /* 分块大小由编译模板固定，主机不能传入任意布局。 */
        if(save&&at%CAPTURE_PART_BYTES==0){
            char path[512];u64 len=append(path,0,CAPTURE_PATH);
            len=append(path,len,".part-");len=number(path,len,(s64)(at/CAPTURE_PART_BYTES));path[len]=0;
            output=(int)open_file(path,WRONLY|CREATE|EXCL|NOFOLLOW|CLOEXEC);
            if(output<0){code=66;break;}
        }
        if(sc(67,fd,P(capture_buf),n,at,0,0)!=(s64)n){code=63;break;}
        sha_add(&h,capture_buf,n);
        if(output>=0&&write_all(output,capture_buf,n)){code=64;break;}
        if(output>=0&&((at+n)%CAPTURE_PART_BYTES==0||at+n==25100288UL)){
            if(sc(82,output,0,0,0,0,0)<0)code=67;
            if(close_fd(output)<0&&!code)code=68;
            output=-1;if(code)break;
        }
    }
    if(output>=0)close_fd(output);
    if(!code)sha_end(&h,digest);
    if(close_fd(fd)<0&&!code)code=65;
    return code;
}
static int native_task(int output) {
    (void)sha_bytes;
    char before[4096],after[4096],ns1[128],ns2[128];
    if(sc(174,0,0,0,0,0,0)||sc(175,0,0,0,0,0,0))return 40;
    s64 a=sc(78,AT_FDCWD,P("/proc/self/ns/mnt"),P(ns1),128,0,0);
    s64 b=sc(78,AT_FDCWD,P("/proc/1/ns/mnt"),P(ns2),128,0,0);
    if(a<=0||a>=128||a!=b||!same(ns1,ns2,a))return 41;
    int n=capture_preload(before);if(n<0)return 42;
#ifndef CAPTURE_FIXTURE
    char size[16];if(bounded("/sys/dev/block/252:129/size",size,sizeof(size))!=6||!same(size,"49024\n",6))return 43;
#endif
    if(!capture_memory_ready())return 46;
    int ram=(int)open_file(CAPTURE_RAM_PARENT,RDONLY|16384|NOFOLLOW|CLOEXEC);if(ram<0)return 44;
    s64 fs[15];u64 limit[2];
    int enough=sc(44,ram,P(fs),0,0,0,0)==0&&fs[0]==0x01021994&&fs[1]>0&&fs[4]>0&&
        (u64)fs[1]*(u64)fs[4]>25100288UL+8388608;
    if(sc(163,1,P(limit),0,0,0,0)<0||limit[0]<25100288UL)enough=0;
    if(close_fd(ram)<0||!enough)return 44;
    if(sc(34,AT_FDCWD,P(CAPTURE_RAM_DIR),0700,0,0,0)<0)return 45;
    char first[65],second[65];int code=capture_pass(1,first);
    if(!code)code=capture_pass(0,second);
    if(!code&&!same(first,second,65))code=48;
    if(!code&&(capture_preload(after)!=n||!same(before,after,n)))code=49;
    if(!code){char row[512];u64 len=append(row,0,CAPTURE_BEGIN "A7R5_CAPTURE_COMPLETE ");
        len=append(row,len,first);len=append(row,len,CAPTURE_SUMMARY CAPTURE_END);
        if(write_all(output,row,len))code=50;}
    return code;
}
