/* 只读工作区诊断：仅取FAT引导扇区和根目录；输出写入本次已验证的RAM控制目录。 */
#include <stddef.h>
#include <stdint.h>
#include "work_probe_config.h"
static void *copy(void *aa,const void *bb,size_t n){char *a=aa;const char *b=bb;for(size_t i=0;i<n;i++)a[i]=b[i];return aa;}
#define memcpy copy
#include "sha256.h"
static unsigned char probe_boot[512],probe_root[16384];
static unsigned probe_u16(const unsigned char *p){return p[0]|((unsigned)p[1]<<8);}
static unsigned probe_u32(const unsigned char *p){return probe_u16(p)|((unsigned)probe_u16(p+2)<<16);}
static s64 probe_memory(void){
    s64 n=bounded("/proc/meminfo",(char *)probe_root,sizeof(probe_root));
    if(n<=0)return -1;
    for(s64 at=0;at+13<n;at++)if((!at||probe_root[at-1]=='\n')&&same((char *)probe_root+at,"MemAvailable:",13)){
        at+=13;while(at<n&&(probe_root[at]==' '||probe_root[at]=='\t'))at++;
        s64 first=at;u64 value=0;
        while(at<n&&probe_root[at]>='0'&&probe_root[at]<='9'){
            unsigned digit=probe_root[at++]-'0';if(value>(0x7fffffffffffffffUL-digit)/10)return -1;
            value=value*10+digit;
        }
        while(at<n&&(probe_root[at]==' '||probe_root[at]=='\t'))at++;
        return at>first&&at+2<=n&&same((char *)probe_root+at,"kB",2)?(s64)value:-1;
    }
    return -1;
}
static int native_task(int output){
    (void)sha_bytes;s64 memory=probe_memory();
    int work=(int)open_file("/tmp/jiritsu",RDONLY|16384|NOFOLLOW|CLOEXEC);if(work<0)return 111;
    s64 fs[15];struct control_stat directory;
    int valid=sc(44,work,P(fs),0,0,0,0)==0&&fs[0]==0x4d44&&fs[1]>0&&fs[4]>=0&&
        (u64)fs[4]<=0x7fffffffffffffffUL/(u64)fs[1]&&sc(80,work,P(&directory),0,0,0,0)==0;
    if(close_fd(work)<0||!valid)return 112;
    int source=(int)open_file(PROBE_SOURCE,RDONLY|NOFOLLOW|CLOEXEC);if(source<0)return 113;
    struct control_stat st;u64 bytes=0;
    valid=sc(80,source,P(&st),0,0,0,0)==0;
#ifdef WORK_PROBE_FIXTURE
    valid=valid&&(st.mode&0170000)==0100000&&st.size==26214400;
    (void)bytes;(void)directory;
#else
    valid=valid&&(st.mode&0170000)==0060000&&st.rdev==((252UL<<8)|134)&&st.rdev==directory.dev&&
        sc(29,source,0x80081272UL,P(&bytes),0,0,0)==0&&bytes==26214400;
#endif
    if(!valid){close_fd(source);return 114;}
    if(sc(67,source,P(probe_boot),512,0,0,0)!=512){close_fd(source);return 115;}
    if(probe_u16(probe_boot+11)!=512||probe_boot[13]!=32||probe_u16(probe_boot+14)!=1||
       probe_boot[16]!=1||probe_u16(probe_boot+17)!=512||probe_u16(probe_boot+19)!=51200||
       probe_u16(probe_boot+22)!=5||probe_u32(probe_boot+32)!=0||
       !same((char *)probe_boot+54,"FAT12   ",8)||probe_boot[510]!=0x55||probe_boot[511]!=0xaa){close_fd(source);return 115;}
    if(sc(67,source,P(probe_root),16384,3072,0,0)!=16384){close_fd(source);return 116;}
    unsigned char again[512];
    for(u64 at=0;at<16384;at+=512)if(sc(67,source,P(again),512,3072+at,0,0)!=512||
        !same((char *)again,(char *)probe_root+at,512)){close_fd(source);return 117;}
    if(sc(67,source,P(again),512,0,0,0)!=512||!same((char *)again,(char *)probe_boot,512)||close_fd(source)<0)return 117;
    unsigned free=0,longest=0,run=0;int ended=0;
    for(unsigned at=0;at<512;at++){
        unsigned first=probe_root[at*32];if(!first)ended=1;
        if(ended||first==0xe5){free++;run++;if(run>longest)longest=run;}else run=0;
    }
    struct sha_ctx hash;char digest[65];sha_init(&hash);sha_add(&hash,probe_boot,512);sha_add(&hash,probe_root,16384);sha_end(&hash,digest);
    int snapshot=(int)open_file(PROBE_DATA_PATH,WRONLY|CREATE|EXCL|NOFOLLOW|CLOEXEC);if(snapshot<0)return 118;
    int failed=write_all(snapshot,(char *)probe_boot,512)||write_all(snapshot,(char *)probe_root,16384)||sc(82,snapshot,0,0,0,0,0)<0;
    if(close_fd(snapshot)<0||failed)return 119;
    char row[1024];u64 len=append(row,0,PROBE_BEGIN "A7R5_WORK_PROBE fs_type=");
    len=number(row,len,fs[0]);len=append(row,len," fs_flags=");len=number(row,len,fs[10]);
    len=append(row,len," available_bytes=");len=number(row,len,fs[1]*fs[4]);
    len=append(row,len," memory_available_kib=");len=number(row,len,memory);
    len=append(row,len," root_slots=512 free_slots=");len=number(row,len,free);
    len=append(row,len," max_free_run=");len=number(row,len,longest);
    len=append(row,len," snapshot_bytes=16896 sha256=");len=append(row,len,digest);
    len=append(row,len,"\n" PROBE_END);
    return write_all(output,row,len)?120:0;
}
