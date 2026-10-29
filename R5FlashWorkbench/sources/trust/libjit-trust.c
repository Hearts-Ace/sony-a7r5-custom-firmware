/* 固定任务的一次性 libJit 执行器；加载器和 fork 后路径只调用 Linux 系统调用。 */
typedef long s64;
typedef unsigned long u64;
#include "jit_config.h"
#ifdef TRUST_FIXTURE
__attribute__((used)) static const char trust_build_mode[]="A7R5_TRUST_FIXTURE_ONLY_V2";
#else
__attribute__((used)) static const char trust_build_mode[]="A7R5_TRUST_PRODUCTION_V2";
#endif

static s64 sc(s64 n, s64 a, s64 b, s64 c, s64 d, s64 e, s64 f)
{
    register s64 x0 __asm__("x0")=a, x1 __asm__("x1")=b, x2 __asm__("x2")=c;
    register s64 x3 __asm__("x3")=d, x4 __asm__("x4")=e, x5 __asm__("x5")=f;
    register s64 x8 __asm__("x8")=n;
    __asm__ volatile("svc 0" : "+r"(x0) : "r"(x1),"r"(x2),"r"(x3),"r"(x4),"r"(x5),"r"(x8) : "memory","cc");
    return x0;
}
#define P(x) ((s64)(x))
#define RDONLY 0
#define WRONLY 1
#define RDWR 2
#define CREATE 64
#define EXCL 128
#define NOFOLLOW 32768
#define CLOEXEC 524288
#define AT_FDCWD -100

static int same(const char *a,const char *b,u64 n) { for(u64 i=0;i<n;i++)if(a[i]!=b[i])return 0;return 1; }
static s64 open_file(const char *p,int flags) { return sc(56,AT_FDCWD,P(p),flags,0600,0,0); }
static s64 close_fd(s64 fd) { return sc(57,fd,0,0,0,0,0); }
static s64 unlink_file(const char *p) { return sc(35,AT_FDCWD,P(p),0,0,0,0); }
static void die(int rc) { sc(94,rc,0,0,0,0,0);for(;;){} }
static int write_all(s64 fd,const char *s,u64 n)
{
    while(n){s64 got=sc(64,fd,P(s),n,0,0,0);if(got==-4)continue;if(got<=0)return -1;s+=got;n-=got;}return 0;
}
static s64 bounded(const char *path,char *raw,u64 cap)
{
    s64 fd=open_file(path,RDONLY|NOFOLLOW|CLOEXEC);if(fd<0)return fd;
    u64 used=0;while(used<cap){s64 got=sc(63,fd,P(raw+used),cap-used,0,0,0);if(got==-4)continue;
        if(got<0){close_fd(fd);return got;}if(!got)break;used+=got;}
    char extra; s64 got=sc(63,fd,P(&extra),1,0,0,0);s64 closed=close_fd(fd);
    return got!=0||closed<0?-5:(s64)used;
}
static u64 number(char *out,u64 at,s64 value)
{
    char digits[24];u64 n=0,v=value<0?(u64)(-value):(u64)value;
    if(value<0)out[at++]='-';do{digits[n++]=(char)('0'+v%10);v/=10;}while(v);
    while(n)out[at++]=digits[--n];return at;
}
static u64 append(char *out,u64 at,const char *s) { for(u64 i=0;s[i];i++)out[at++]=s[i];return at; }
#ifdef CAPTURE_CONTROL_DIR
#include "capture_control.h"
#endif
#ifdef TRUST_USER_CHECK_DIAGNOSTICS
static u64 trust_users_state(char *row,u64 n);
#endif
#ifdef TRUST_RESOURCE_CHECK_DIAGNOSTICS
static u64 trust_resources_state(char *row,u64 n);
#endif
static int state(const char *phase,int code,s64 bytes,int unlinked,int children)
{
    char row[512];u64 n=append(row,0,"A7R5-JIT-1 " RUN_ID " ");n=append(row,n,phase);
    n=append(row,n," ");n=number(row,n,code);n=append(row,n," uid=");n=number(row,n,sc(174,0,0,0,0,0,0));
    n=append(row,n," euid=");n=number(row,n,sc(175,0,0,0,0,0,0));n=append(row,n," bytes=");n=number(row,n,bytes);
    n=append(row,n," disarmed=");n=number(row,n,unlinked);n=append(row,n," children=");n=number(row,n,children);
#ifdef TRUST_USER_CHECK_DIAGNOSTICS
    if(code==47)n=trust_users_state(row,n);
#endif
#ifdef TRUST_RESOURCE_CHECK_DIAGNOSTICS
    if(code==43||code==44)n=trust_resources_state(row,n);
#endif
    row[n++]='\n';
    s64 fd=open_file(STATE_NEW,WRONLY|CREATE|EXCL|NOFOLLOW|CLOEXEC);if(fd<0)return -1;
    int failed=write_all(fd,row,n)||sc(82,fd,0,0,0,0,0)<0;if(close_fd(fd)<0)failed=1;
    if(failed)return -1;
    return sc(38,AT_FDCWD,P(STATE_NEW),AT_FDCWD,P(STATE_PATH),0,0)<0?-1:0;
}
static void fail(int code) { state("FAILED",code,0,1,-1);die(code); }
static int no_children(void)
{
    char path[128],buf[64];u64 n=append(path,0,"/proc/self/task/");n=number(path,n,sc(172,0,0,0,0,0,0));
    n=append(path,n,"/children");path[n]=0;return bounded(path,buf,sizeof(buf))==0;
}
/* 原生写入在单个分离工作进程内执行；绝不因主机观察超时发信号。 */
#include "native_gate.c"
static void worker(void)
{
    if(sc(157,0,0,0,0,0,0)<0)fail(80);
    if(sc(167,36,1,0,0,0,0)<0)fail(81);
    u64 action[4]={0,0,0,0},mask=0;
    if(sc(134,17,P(action),0,8,0,0)<0||sc(135,2,P(&mask),0,8,0,0)<0)fail(82);
    u64 limits[2];if(sc(163,7,P(limits),0,0,0,0)<0||limits[0]<3||limits[0]>65536)fail(83);
    s64 null=open_file("/dev/null",RDWR|CLOEXEC);if(null<0)fail(84);
    if(sc(25,null,2,0,0,0,0)<0)fail(84);
    for(int i=0;i<3;i++)if(null!=i&&sc(24,null,i,0,0,0,0)<0)fail(84);
    for(u64 i=3;i<limits[0];i++)close_fd(i);
    if(sc(49,P("/"),0,0,0,0,0)<0)fail(85);
    s64 output=open_file(OUTPUT_PATH,WRONLY|CREATE|EXCL|NOFOLLOW|CLOEXEC);if(output<0)fail(86);
    if(state("RUNNING",0,0,1,0))die(87);
    int rc=native_task((int)output);
    s64 bytes=sc(62,output,0,2,0,0,0);
    if(bytes<0||bytes>=32768||sc(82,output,0,0,0,0,0)<0){if(!rc)rc=95;}
    if(close_fd(output)<0&&!rc)rc=95;
    int children=no_children()?0:-1;
    if(children&&!rc)rc=94;
    if(state(rc?"FAILED":"DONE",rc,bytes,1,children))die(96);
    die(rc);
}
__attribute__((visibility("default"))) void _init(void)
{
#ifdef CAPTURE_CONTROL_DIR
    if(sc(174,0,0,0,0,0,0)||sc(175,0,0,0,0,0,0)||!capture_control_parent_ready())return;
#endif
    char ticket[128];s64 n=bounded(TICKET_PATH,ticket,sizeof(ticket));
    if(n!=(s64)sizeof(TICKET_BYTES)-1||!same(ticket,TICKET_BYTES,sizeof(TICKET_BYTES)-1))return;
#ifdef CAPTURE_CONTROL_DIR
    if(!capture_control_create())return;
#endif
    if(sc(174,0,0,0,0,0,0)||sc(175,0,0,0,0,0,0)){state("FAILED",97,0,0,-1);return;}
    /* 无任何文件不存在的推断；只有真实 unlink 成功才报告解除加载文件。 */
    if(unlink_file(LIBJIT_PATH)<0){state("FAILED",98,0,0,-1);return;}
    s64 claim=open_file(CLAIM_PATH,WRONLY|CREATE|EXCL|NOFOLLOW|CLOEXEC);
    if(claim<0){state("FAILED",99,0,0,-1);return;}
    int failed=write_all(claim,TICKET_BYTES,sizeof(TICKET_BYTES)-1)||sc(82,claim,0,0,0,0,0)<0;
    if(close_fd(claim)<0)failed=1;
    if(failed||unlink_file(TICKET_PATH)<0){state("FAILED",100,0,0,-1);return;}
    s64 pid=sc(220,17,0,0,0,0,0);if(!pid)worker();
    if(pid<0)state("FAILED",101,0,1,-1);
    /* 父线程返回 dlopen，禁止 _exit 或在此 wait，否则会杀死或阻塞原厂服务。 */
}
