/* Adapted for our signing identity and actual sector plan; 2026-10-29. */
/* 仅供本次固定一号逻辑分区事务；全部目标写入由 trust_apply_fd 完成。 */
#include <stddef.h>
#include <stdint.h>
typedef long ssize_t;
struct target_stat {
    u64 dev,ino; unsigned mode,nlink,uid,gid; u64 rdev,pad;
    s64 size; unsigned blksize,pad2; u64 blocks,rest[7];
};
_Static_assert(sizeof(struct target_stat)==128,"AArch64 stat ABI");
static unsigned char inspection[65536];
static int cmp(const void *aa,const void *bb,size_t n)
{ const unsigned char *a=aa,*b=bb;for(size_t i=0;i<n;i++)if(a[i]!=b[i])return 1;return 0; }
#ifndef TRUST_PRECHECK_ONLY
static void *copy(void *aa,const void *bb,size_t n)
{ unsigned char *a=aa;const unsigned char *b=bb;for(size_t i=0;i<n;i++)a[i]=b[i];return aa; }
#endif
#include "trust_config.h"
#ifndef TRUST_FORCE_SECTOR_READBACK
#define TRUST_FORCE_SECTOR_READBACK 0
#endif
#ifndef TRUST_PLANNED_RESOURCE_BUDGET
#define TRUST_PLANNED_RESOURCE_BUDGET 0
#endif
#if TRUST_PLANNED_RESOURCE_BUDGET
#if !TRUST_FORCE_MODE || !TRUST_FORCE_SECTOR_READBACK
#error planned_resource_budget_requires_force_sector_readback
#endif
#define TRUST_MEMORY_REQUIRED_KIB 32768UL
#define TRUST_RAM_REQUIRED_BYTES (13312UL+131072UL+32768UL+8388608UL)
#define TRUST_FILE_REQUIRED_BYTES 131072UL
#else
#define TRUST_MEMORY_REQUIRED_KIB 65536UL
#define TRUST_RAM_REQUIRED_BYTES (PARTITION_BYTES+(TRUST_FORCE_MODE?8388608UL:1048576UL))
#define TRUST_FILE_REQUIRED_BYTES PARTITION_BYTES
#endif
#ifndef TRUST_PRECHECK_ONLY
static long t_pread(int f,void *p,size_t n,long off){return sc(67,f,P(p),n,off,0,0);}
static long t_pwrite(int f,const void *p,size_t n,long off){return sc(68,f,P(p),n,off,0,0);}
static long t_write(int f,const void *p,size_t n){return sc(64,f,P(p),n,0,0,0);}
static int t_sync(int f){return (int)sc(82,f,0,0,0,0,0);}
#define pread t_pread
#define pwrite t_pwrite
#define write t_write
#define fsync t_sync
#define memcmp cmp
#define memcpy copy
#include "sha256.h"
static int note(int fd,const char *phase,unsigned count,long offset,int code)
{
    char row[256];u64 n=append(row,0,"A7R5_TRUST " RUN_ID " ");
    n=append(row,n,phase);n=append(row,n," completed=");n=number(row,n,count);
    n=append(row,n," offset=");n=number(row,n,offset);
    n=append(row,n," code=");n=number(row,n,code);row[n++]='\n';
    return write(fd,row,n)!=(long)n||fsync(fd)?-1:0;
}
#include "sector_core.inc"
#endif

static int numeric(const char *s)
{if(!*s)return 0;for(;*s;s++)if(*s<'0'||*s>'9')return 0;return 1;}
static int terminated(const char *s,unsigned n)
{for(unsigned i=0;i<n;i++)if(!s[i])return 1;return 0;}
static int protected_dev(u64 d)
{return d==((252UL<<8)|129)||d==((252UL<<8)|1)||d==(252UL<<8);}
#ifndef TRUST_PRECHECK_ONLY
static int target_identity(int fd)
{
    struct target_stat st;u64 capacity=0;
    if(sc(80,fd,P(&st),0,0,0,0)<0)return 1;
#ifdef TRUST_FIXTURE
    /* 此分支只生成模拟夹具；实机包不定义该宏，并绑定另一份库的摘要。 */
    (void)capacity;
    return (st.mode&0170000)==0100000&&st.size==PARTITION_BYTES?0:2;
#else
    if((st.mode&0170000)!=0060000||st.rdev!=((252UL<<8)|129))return 2;
    if(sc(29,fd,0x80081272UL,P(&capacity),0,0,0)<0||capacity!=PARTITION_BYTES)return 3;
    return 0;
#endif
}
#endif
static int same_original_namespace(void)
{
    char a[128],b[128];
    s64 n=sc(78,AT_FDCWD,P("/proc/self/ns/mnt"),P(a),sizeof(a),0,0);
    s64 m=sc(78,AT_FDCWD,P("/proc/1/ns/mnt"),P(b),sizeof(b),0,0);
    return n>0&&n<(s64)sizeof(a)&&n==m&&!cmp(a,b,n);
}
/* 把首次阻塞的具体原因放入同一次终态响应，不追加失败后的USB请求。 */
static int users_reason;
static s64 users_pid,users_fd,users_error;
static u64 users_device;
static int users_block(int reason,s64 error,u64 device)
{users_reason=reason;users_error=error;users_device=device;return 0;}
#ifdef TRUST_USER_CHECK_DIAGNOSTICS
static u64 trust_users_state(char *row,u64 n)
{
    n=append(row,n," precheck_reason=");n=number(row,n,users_reason);
    n=append(row,n," precheck_pid=");n=number(row,n,users_pid);
    n=append(row,n," precheck_fd=");n=number(row,n,users_fd);
    n=append(row,n," precheck_error=");n=number(row,n,users_error);
    n=append(row,n," precheck_device=");n=number(row,n,(s64)users_device);
    return append(row,n," partition_writes=0");
}
#endif
static s64 proc_open_at(int parent,const char *name,int flags)
{return sc(56,parent,P(name),flags,0600,0,0);}
/* 固定到已打开的进程目录，避免PID复用后改读另一个进程。 */
static s64 proc_read_at(int parent,const char *name,char *raw,u64 cap,s64 *close_error)
{
    *close_error=0;
    s64 fd=proc_open_at(parent,name,RDONLY|NOFOLLOW|CLOEXEC);if(fd<0)return fd;
    u64 used=0;s64 result=0;
    while(used<cap){
        s64 got=sc(63,fd,P(raw+used),cap-used,0,0,0);if(got==-4)continue;
        if(got<0){result=got;break;}if(!got)break;
        if((u64)got>cap-used){result=-5;break;}used+=(u64)got;
    }
    if(!result&&used==cap){
        char extra;s64 got;
        do{got=sc(63,fd,P(&extra),1,0,0,0);}while(got==-4);
        if(got)result=got<0?got:-5;
    }
    s64 closed=close_fd(fd);if(closed<0)*close_error=closed;
    return result?result:(s64)used;
}
static int proc_decimal(const char *raw,s64 n,s64 *at,u64 *value,int signed_ok)
{
    s64 p=*at;u64 v=0;
    if(p<n&&raw[p]=='-'&&signed_ok)p++;
    s64 begin=p;
    while(p<n&&raw[p]>='0'&&raw[p]<='9'){
        unsigned digit=(unsigned)(raw[p++]-'0');
        if(v>(~(u64)0-digit)/10)return 0;v=v*10+digit;
    }
    if(p==begin||p>=n||(raw[p]!=' '&&raw[p]!='\n'))return 0;
    *at=p;*value=v;return 1;
}
static int proc_stat_without_namespace(const char *raw,s64 n)
{
    if(n<1||raw[n-1]!='\n')return 0;
    s64 at=0;u64 pid,flags=0;
    if(!proc_decimal(raw,n,&at,&pid,0)||pid!=(u64)users_pid||raw[at++]!=' '
        ||at>=n||raw[at]!='(')return 0;
    s64 end=n-1;while(end>at&&raw[end]!=')')end--;
    if(end<=at||end+4>=n||raw[end+1]!=' '||raw[end+3]!=' ')return 0;
    char state=raw[end+2];int known=0;
    const char *states="RSDZTtXxKWPI";
    for(unsigned i=0;states[i];i++)if(state==states[i])known=1;
    if(!known)return 0;
    at=end+4;
    /* 核验到starttime字段，命令名中的空格和括号不作为分隔符。 */
    for(int field=4;field<=22;field++){
        u64 value;
        if(!proc_decimal(raw,n,&at,&value,field!=9&&field!=22))return 0;
        if(field==9)flags=value;
        if(field<22&&raw[at++]!=' ')return 0;
    }
    return (flags&0x00200000UL)!=0||state=='Z'||state=='X'||state=='x';
}
static int proc_namespace_absent(int parent)
{
    char link[128];
    s64 n=sc(78,parent,P("ns/mnt"),P(link),sizeof(link),0,0);
    return n==-2||n==-3;
}
static int mountinfo_not_applicable(int parent)
{
    if(!proc_namespace_absent(parent))return 0;
    char raw[4096];s64 closed,n=proc_read_at(parent,"stat",raw,sizeof(raw),&closed);
    if(closed<0)return 0;
    int gone=n==-2||n==-3;
    if(!gone&&(n<0||!proc_stat_without_namespace(raw,n)))return 0;
    /* 第二次仍须不存在；命名空间出现或核验失败时保留原EINVAL。 */
    return proc_namespace_absent(parent);
}
static int mounts_clear(int parent)
{
    s64 closed,n=proc_read_at(parent,"mountinfo",(char *)inspection,sizeof(inspection),&closed);
    if(closed<0)return users_block(11,closed,0);
    if(n==-2||n==-3)return 1;
    if(n==-22&&mountinfo_not_applicable(parent))return 1;
    if(n<0)return users_block(4,n,0);
    for(s64 at=0;at<n;){
        s64 end=at;while(end<n&&inspection[end]!='\n')end++;
        if(end==n)return users_block(12,-5,0);
        s64 p=at;
        for(int k=0;k<2;k++){
            while(p<end&&inspection[p]!=' ')p++;
            if(p==end)return users_block(12,-5,0);p++;
        }
        s64 q=p;while(q<end&&inspection[q]!=' ')q++;
        if(q==end||q==p)return users_block(12,-5,0);
        int colons=0;
        for(s64 i=p;i<q;i++){
            if(inspection[i]==':'&&i>p&&i+1<q)colons++;
            else if(inspection[i]<'0'||inspection[i]>'9')return users_block(12,-5,0);
        }
        if(colons!=1)return users_block(12,-5,0);
        if(q-p==7&&!cmp(inspection+p,"252:129",7))return users_block(5,0,(252UL<<8)|129);
        if(q-p==5&&!cmp(inspection+p,"252:1",5))return users_block(5,0,(252UL<<8)|1);
        if(q-p==5&&!cmp(inspection+p,"252:0",5))return users_block(5,0,252UL<<8);
        at=end+1;
    }
    return 1;
}
static int process_fds_clear(int parent,s64 id,s64 own)
{
    unsigned char fds[16384];int ok=1;
    int dir=(int)proc_open_at(parent,"fd",RDONLY|16384|NOFOLLOW|CLOEXEC);
    if(dir<0)return dir==-2||dir==-3?1:users_block(6,dir,0);
    for(;;){
        s64 count=sc(61,dir,P(fds),sizeof(fds),0,0,0);
        if(count<0){ok=users_block(7,count,0);break;}if(!count)break;
        if(count>(s64)sizeof(fds)){ok=users_block(8,-5,0);break;}
        for(s64 off=0;off<count;){
            if(count-off<20){ok=users_block(8,-5,0);break;}
            unsigned bytes=fds[off+16]|((unsigned)fds[off+17]<<8);
            if(bytes<20||off+bytes>count){ok=users_block(8,-5,0);break;}
            char *name=(char *)fds+off+19;
            if(!terminated(name,bytes-19)){ok=users_block(8,-5,0);break;}
            off+=bytes;if(!numeric(name)||id==own)continue;
            users_fd=0;for(char *s=name;*s;s++)users_fd=users_fd*10+*s-'0';
            struct target_stat st;s64 r=sc(79,dir,P(name),P(&st),0,0,0);
            if(r<0){if(r!=-2&&r!=-3)ok=users_block(9,r,0);}
            else if((st.mode&0170000)==0060000&&protected_dev(st.rdev))ok=users_block(10,0,st.rdev);
            if(!ok)break;
        }
        if(!ok)break;
    }
    s64 closed=close_fd(dir);if(closed<0&&ok)ok=users_block(11,closed,0);
    return ok;
}
/* 消失的进程或FD允许忽略；其他错误保持拒绝，并报告真实原因。 */
static int process_users_clear(void)
{
    users_reason=0;users_pid=-1;users_fd=-1;users_error=0;users_device=0;
    int proc=(int)open_file("/proc",RDONLY|16384|NOFOLLOW|CLOEXEC);
    if(proc<0)return users_block(1,proc,0);
    unsigned char dirs[16384];int ok=1;
    s64 own=sc(172,0,0,0,0,0,0);
    if(own<0){close_fd(proc);return users_block(13,own,0);}
    for(;;){
        s64 n=sc(61,proc,P(dirs),sizeof(dirs),0,0,0);
        if(n<0){ok=users_block(2,n,0);break;}if(!n)break;
        if(n>(s64)sizeof(dirs)){ok=users_block(3,-5,0);break;}
        for(s64 at=0;at<n;){
            if(n-at<20){ok=users_block(3,-5,0);break;}
            unsigned len=dirs[at+16]|((unsigned)dirs[at+17]<<8);
            if(len<20||at+len>n){ok=users_block(3,-5,0);break;}
            char *pid=(char *)dirs+at+19;
            if(!terminated(pid,len-19)){ok=users_block(3,-5,0);break;}
            at+=len;if(!numeric(pid))continue;
            s64 id=0;for(char *s=pid;*s;s++)id=id*10+*s-'0';
            users_pid=id;users_fd=-1;
            int task=(int)proc_open_at(proc,pid,RDONLY|16384|NOFOLLOW|CLOEXEC);
            if(task<0){if(task!=-2&&task!=-3)ok=users_block(14,task,0);if(!ok)break;continue;}
            ok=mounts_clear(task)&&process_fds_clear(task,id,own);
            s64 closed=close_fd(task);if(closed<0&&ok)ok=users_block(11,closed,0);if(!ok)break;
        }
        if(!ok)break;
    }
    s64 closed=close_fd(proc);if(closed<0&&ok)ok=users_block(11,closed,0);return ok;
}
#ifndef TRUST_PRECHECK_ONLY
#if TRUST_FORCE_MODE && TRUST_FORCE_SECTOR_READBACK
static int capture_reopened(int journal)
{
    int fd=(int)open_file(TARGET_PATH,RDONLY|EXCL|NOFOLLOW|CLOEXEC);
    if(fd<0||target_identity(fd)){if(fd>=0)close_fd(fd);return 62;}
    char digest[65];int code=0,output=-1;
    /* 先保留重新打开后的整分区摘要检查，随后仅导出固定计划扇区。 */
    if(full_hash(fd,digest,0)||cmp(digest,force_candidate_sha,65))code=65;
    for(unsigned first=0;!code&&first<PATCH_COUNT;first+=32){
        char path[256];u64 n=append(path,0,READBACK_PATH);n=append(path,n,".sectors-");
        n=number(path,n,first/32);path[n]=0;
        output=(int)open_file(path,WRONLY|CREATE|EXCL|NOFOLLOW|CLOEXEC);
        if(output<0){code=63;break;}
        unsigned end=first+32;if(end>PATCH_COUNT)end=PATCH_COUNT;
        for(unsigned i=first;i<end;i++){
            if(pread(fd,inspection,512,(long)PATCH_OFFSETS[i])!=512
                ||cmp(inspection,AFTER_SECTORS+i*512,512)||write(output,inspection,512)!=512){code=64;break;}
        }
        if(!code&&fsync(output))code=65;
        if(close_fd(output)<0&&!code)code=66;output=-1;
    }
    if(output>=0&&close_fd(output)<0&&!code)code=66;
    if(close_fd(fd)<0&&!code)code=67;
    if(!code&&note(journal,"REOPENED_FULL_CAPTURE_MATCH",PATCH_COUNT,-1,0))code=68;
    return code;
}
#else
static int capture_reopened(int journal)
{
    int fd=(int)open_file(TARGET_PATH,RDONLY|EXCL|NOFOLLOW|CLOEXEC);
    if(fd<0||target_identity(fd)){if(fd>=0)close_fd(fd);return 62;}
    int output=-1;
#if !TRUST_FORCE_MODE
    output=(int)open_file(READBACK_PATH,WRONLY|CREATE|EXCL|NOFOLLOW|CLOEXEC);
    if(output<0){close_fd(fd);return 63;}
#endif
    struct sha_ctx h;sha_init(&h);char digest[65];int code=0;
    const u64 step=TRUST_FORCE_MODE?16384:sizeof(inspection);
    for(u64 at=0;at<PARTITION_BYTES;at+=step){
        u64 n=PARTITION_BYTES-at;if(n>step)n=step;
#if TRUST_FORCE_MODE
        char path[256];u64 pos=append(path,0,READBACK_PATH);pos=append(path,pos,".part-");
        pos=number(path,pos,(s64)(at/16384));path[pos]=0;
        output=(int)open_file(path,WRONLY|CREATE|EXCL|NOFOLLOW|CLOEXEC);
        if(output<0){code=63;break;}
#endif
        if(pread(fd,inspection,n,at)!=(long)n||write(output,inspection,n)!=(long)n){code=64;break;}
        sha_add(&h,inspection,n);
#if TRUST_FORCE_MODE
        if(fsync(output)){code=65;break;}
        if(close_fd(output)<0){output=-1;code=66;break;}output=-1;
#endif
    }
    if(!code){sha_end(&h,digest);
#if TRUST_FORCE_MODE
        if(cmp(digest,force_candidate_sha,65))code=65;
#else
        if(cmp(digest,CANDIDATE_SHA,65)||fsync(output))code=65;
#endif
    }
    if(output>=0&&close_fd(output)<0)code=66;if(close_fd(fd)<0)code=67;
    if(!code&&note(journal,"REOPENED_FULL_CAPTURE_MATCH",PATCH_COUNT,-1,0))code=68;
    return code;
}
#endif
#endif
/* 新计划扇区预算有独立编译标记；旧模式保持原资源门槛。 */
static int resource_reason;
static s64 resource_error,resource_memory=-1,resource_ram_bytes=-1;
static void resource_block(int reason,s64 error)
{if(!resource_reason){resource_reason=reason;resource_error=error;}}
#ifdef TRUST_RESOURCE_CHECK_DIAGNOSTICS
static u64 trust_resources_state(char *row,u64 n)
{
    n=append(row,n," resource_reason=");n=number(row,n,resource_reason);
    n=append(row,n," resource_error=");n=number(row,n,resource_error);
    n=append(row,n," memory_available_kib=");n=number(row,n,resource_memory);
    n=append(row,n," memory_required_kib=");n=number(row,n,TRUST_MEMORY_REQUIRED_KIB);
    n=append(row,n," ram_available_bytes=");n=number(row,n,resource_ram_bytes);
    return append(row,n," partition_writes=0");
}
#endif
#if TRUST_PLANNED_RESOURCE_BUDGET
static int planned_memory_available(const unsigned char *raw,s64 size,u64 *available)
{
    if(size<=0||size>(s64)sizeof(inspection))return 0;
    int found=0;
    for(s64 start=0;start<size;){
        s64 end=start;while(end<size&&raw[end]!='\n')end++;
        if(end-start>=13&&!cmp(raw+start,"MemAvailable:",13)){
            if(found)return 0;
            s64 at=start+13;while(at<end&&(raw[at]==' '||raw[at]=='\t'))at++;
            s64 begin=at;u64 value=0;
            while(at<end&&raw[at]>='0'&&raw[at]<='9'){
                unsigned digit=raw[at++]-'0';
                if(value>(0x7fffffffffffffffUL-digit)/10)return 0;
                value=value*10+digit;
            }
            if(at==begin)return 0;
            while(at<end&&(raw[at]==' '||raw[at]=='\t'))at++;
            if(at+2>end||cmp(raw+at,"kB",2))return 0;at+=2;
            while(at<end&&(raw[at]==' '||raw[at]=='\t'))at++;
            if(at!=end)return 0;*available=value;found=1;
        }
        start=end+1;
    }
    return found;
}
#endif
static int native_task(int output)
{
#ifdef TRUST_PRECHECK_ONLY
    (void)output;
#endif
    char preload[4096],size[32];
    if(sc(174,0,0,0,0,0,0)||sc(175,0,0,0,0,0,0)||!same_original_namespace())return 40;
    s64 n=bounded("/etc/ld.so.preload",preload,sizeof(preload));
#if TRUST_FORCE_MODE
    if(!((n==(s64)sizeof(FORCE_PRELOAD_A)-1&&!cmp(preload,FORCE_PRELOAD_A,n))||
         (n==(s64)sizeof(FORCE_PRELOAD_B)-1&&!cmp(preload,FORCE_PRELOAD_B,n))))return 41;
#ifndef TRUST_PRECHECK_ONLY
    char before_preload[4096];int preload_length=(int)n;copy(before_preload,preload,n);
#endif
#else
    if(n!=(s64)sizeof(EXPECTED_PRELOAD)-1||cmp(preload,EXPECTED_PRELOAD,sizeof(EXPECTED_PRELOAD)-1))return 41;
#endif
#ifndef TRUST_FIXTURE
    n=bounded("/sys/dev/block/252:129/size",size,sizeof(size));
    if(n!=6||cmp(size,"49024\n",6))return 42;
#else
    (void)size;
#endif
    n=bounded("/proc/meminfo",(char *)inspection,sizeof(inspection));
    if(n<0){resource_block(1,n);return 43;}
    u64 available=0;
#if TRUST_PLANNED_RESOURCE_BUDGET
    if(!planned_memory_available(inspection,n,&available)){resource_block(2,-22);return 43;}
#else
    for(s64 at=0;at+13<n;at++)if((at==0||inspection[at-1]=='\n')&&!cmp(inspection+at,"MemAvailable:",13)){
        at+=13;while(at<n&&inspection[at]==' ')at++;
        while(at<n&&inspection[at]>='0'&&inspection[at]<='9')available=available*10+inspection[at++]-'0';
        break;
    }
#endif
    resource_memory=(s64)available;
    if(available<TRUST_MEMORY_REQUIRED_KIB){resource_block(2,0);return 43;}
    int dir=(int)open_file("/tmp_wbshd",RDONLY|16384|NOFOLLOW|CLOEXEC);
    if(dir<0){resource_block(3,dir);return 43;}
    s64 fs[15];u64 limit[2];
    s64 fs_result=sc(44,dir,P(fs),0,0,0,0);
#if TRUST_PLANNED_RESOURCE_BUDGET
    int ram_size_valid=fs_result==0&&fs[1]>0&&fs[4]>0&&
        (u64)fs[1]<=0x7fffffffffffffffUL/(u64)fs[4];
    if(ram_size_valid)resource_ram_bytes=fs[1]*fs[4];
    int valid=ram_size_valid&&fs[0]==0x01021994&&(u64)resource_ram_bytes>TRUST_RAM_REQUIRED_BYTES;
#else
    if(fs_result==0&&fs[1]>0&&fs[4]>0)resource_ram_bytes=(s64)((u64)fs[1]*(u64)fs[4]);
    int valid=fs_result==0&&fs[0]==0x01021994&&fs[1]>0&&fs[4]>0&&
        (u64)fs[1]*(u64)fs[4]>TRUST_RAM_REQUIRED_BYTES;
#endif
    if(!valid)resource_block(4,fs_result);
    s64 limit_result=sc(163,1,P(limit),0,0,0,0);
    if(limit_result<0||limit[0]<TRUST_FILE_REQUIRED_BYTES){resource_block(5,limit_result);valid=0;}
    s64 dir_closed=close_fd(dir);
    if(dir_closed<0){resource_block(6,dir_closed);return 44;}
    if(!valid)return 44;
    if(sc(34,AT_FDCWD,P(RAM_DIR),0700,0,0,0)<0)return 45;
    int journal=(int)open_file(JOURNAL_PATH,WRONLY|CREATE|EXCL|NOFOLLOW|CLOEXEC);
    if(journal<0)return 46;
#ifndef TRUST_FIXTURE
    if(!process_users_clear()){close_fd(journal);return 47;}
#else
    (void)process_users_clear;
#endif
#ifdef TRUST_PRECHECK_ONLY
    /* 诊断模板在此结束；写目标的打开和事务代码不进入此编译分支。 */
    if(close_fd(journal)<0)return 53;
    return 0;
#else
    int fd=(int)open_file(TARGET_PATH,RDWR|EXCL|NOFOLLOW|CLOEXEC);
    if(fd<0){note(journal,"OPEN_REFUSED",0,-1,fd);close_fd(journal);return 48;}
    if(target_identity(fd)){close_fd(fd);close_fd(journal);return 49;}
    int code=trust_apply_fd(fd,journal,0);
    if(close_fd(fd)<0&&!code)code=50;
    if(!code)code=capture_reopened(journal);
    if(!code){
        n=bounded("/etc/ld.so.preload",preload,sizeof(preload));
#if TRUST_FORCE_MODE
        if(n!=preload_length||cmp(preload,before_preload,n))code=51;
#else
        if(n!=(s64)sizeof(EXPECTED_PRELOAD)-1||cmp(preload,EXPECTED_PRELOAD,sizeof(EXPECTED_PRELOAD)-1))code=51;
#endif
    }
    if(note(journal,code?"STOP_NO_RETRY":"COMPLETED",code?0:PATCH_COUNT,-1,code)&&!code)code=52;
    if(close_fd(journal)<0&&!code)code=53;
    if(!code){
#if TRUST_FORCE_MODE
        char message[512];u64 len=append(message,0,OUTPUT_BEGIN "A7R5_TRUST_FORCE_COMPLETE ");
        len=append(message,len,force_candidate_sha);len=append(message,len," source_sha256=");
        len=append(message,len,force_source_sha);
        len=append(message,len,
#if TRUST_FORCE_SECTOR_READBACK
            " sectors=26 bytes=13312 reopened=1 chunks=9 chunk_bytes=16384 readback=planned-sectors-v2\n" OUTPUT_END);
#else
            " sectors=26 bytes=13312 reopened=1 chunks=1532 chunk_bytes=16384\n" OUTPUT_END);
#endif
        if(write(output,message,len)!=(s64)len)code=54;
#else
        const char message[]=OUTPUT_BEGIN "A7R5_TRUST_COMPLETE " CANDIDATE_SHA " sectors=26 bytes=13312 reopened=1\n" OUTPUT_END;
        if(write(output,message,sizeof(message)-1)!=(s64)sizeof(message)-1)code=54;
#endif
    }
    return code;
#endif
}
