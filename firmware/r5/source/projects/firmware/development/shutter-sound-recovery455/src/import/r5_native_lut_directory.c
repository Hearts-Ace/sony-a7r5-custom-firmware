#include "r5_native_lut_directory.h"
extern int r5_ap_posix_open(const char *,int,unsigned);
extern int r5_ap_posix_openat(int,const char *,int,unsigned);
extern intptr_t r5_ap_posix_read(int,void *,size_t);
extern intptr_t r5_ap_posix_write(int,const void *,size_t);
extern int r5_ap_posix_close(int);
extern int r5_ap_posix_fsync(int);
extern int r5_ap_posix_unlinkat(int,const char *,int);
extern int *r5_ap_posix_errno(void);
extern void *r5_ap_dlsym(void *,const char *);
static uintptr_t runtime_address(uintptr_t p) {
    __asm__ volatile("" : "+r"(p));return p;
}
int r5_native_lut_directory_api_init(struct r5_lut_directory_api *out) {
    struct r5_lut_directory_api a;
    if(!out)return -1;
    a.renameat=(int (*)(int,const char *,int,const char *))r5_ap_dlsym((void *)0,"renameat");
    if(!a.renameat)return -1;
    a.dup=(int (*)(int))r5_ap_dlsym((void *)0,"dup");
    if(!a.dup)return -1;
    a.open=(int (*)(const char *,int,unsigned))runtime_address((uintptr_t)r5_ap_posix_open);
    a.openat=(int (*)(int,const char *,int,unsigned))runtime_address((uintptr_t)r5_ap_posix_openat);
    a.read=(intptr_t (*)(int,void *,size_t))runtime_address((uintptr_t)r5_ap_posix_read);
    a.write=(intptr_t (*)(int,const void *,size_t))runtime_address((uintptr_t)r5_ap_posix_write);
    a.close=(int (*)(int))runtime_address((uintptr_t)r5_ap_posix_close);
    a.sync=(int (*)(int))runtime_address((uintptr_t)r5_ap_posix_fsync);
    a.unlinkat=(int (*)(int,const char *,int))runtime_address((uintptr_t)r5_ap_posix_unlinkat);
    a.error_number=(int *(*)(void))runtime_address((uintptr_t)r5_ap_posix_errno);
    *out=a;return 0;
}
