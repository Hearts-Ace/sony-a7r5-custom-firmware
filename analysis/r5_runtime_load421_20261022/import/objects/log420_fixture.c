
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "r5_grid_diagnostics.h"
extern int r5_grid420_inbound(const uint8_t *,uint32_t);
int r5_session_current(void){return 1;}uint32_t r5_session_epoch(void){return 0;}
static char output[65536];static unsigned used,mode,opens,closes,flushes,fault,queries;static uint64_t ms;static uint32_t size;
void reset(unsigned f){used=opens=closes=flushes=queries=0;ms=0;fault=f;output[0]=0;}
const char *text(void){return output;}unsigned metric(unsigned n){return n==0?opens:n==1?closes:n==2?flushes:n==3?queries:mode;}
int r5_native_fsys_open(const char *p,uint32_t m,uint64_t *h){if(strcmp(p,"C:/R5IMPORT.LOG"))return -8;opens++;mode=m;if(fault==1)return -1;*h=7;if(m==14){used=0;output[0]=0;}return 0;}
int r5_native_fsys_write(uint64_t h,const void *p,uint64_t n){if(h!=7||used+n>=sizeof(output))return -9;if(fault==2)return -2;memcpy(output+used,p,n);used+=n;output[used]=0;return 0;}
int r5_native_fsys_close(uint64_t h){if(h!=7)return -9;closes++;return fault==4?-4:0;}
static int flush(uint64_t h){if(h!=7)return -9;flushes++;return fault==3?-3:0;}
struct time64{int64_t s,ns;};static int clock0(int kind,struct time64 *t){if(kind!=1)return -9;t->s=ms/1000;t->ns=ms%1000*1000000;return fault==8?-1:0;}
static int sleep0(const struct time64 *t,void *unused){(void)unused;ms+=(uint64_t)t->s*1000+t->ns/1000000;return fault==9?-1:0;}
void *r5_stage411_dlsym(void *h,const char *s){(void)h;if(!strcmp(s,"Fsys_Flush"))return fault==5?0:(void *)flush;if(!strcmp(s,"clock_gettime"))return (void *)clock0;if(!strcmp(s,"nanosleep"))return (void *)sleep0;return 0;}
uint32_t r5_osal_msg_size(const void *p){(void)p;return size;}
int r5_native_ap_send(void *ctx,const uint8_t *p,size_t n){uint8_t a[128]={0};(void)ctx;queries++;if(n!=32||r5_diag_get(p+28)!=r5_diag_crc(p,32))return -9;if(fault==6)return -6;if(fault==7)return 0;memcpy(a,p,12);a[2]=0x81;a[3]=128;r5_diag_put(a+12,0x420);r5_diag_put(a+16,28768);r5_diag_put(a+20,0x35424c53);r5_diag_put(a+24,2);r5_diag_put(a+32,2);r5_diag_put(a+36,2);r5_diag_put(a+40,2);r5_diag_put(a+44,fault==10?0:2);r5_diag_put(a+48,fault==10?3:0);r5_diag_put(a+28,r5_diag_crc(a,128));if(fault==11)a[127]^=1;size=128;r5_grid420_inbound(a,0x90030001);return 0;}
