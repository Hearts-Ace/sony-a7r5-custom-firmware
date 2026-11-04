#include "r5sound_store.h"
#include "r5_runtime_session.h"
#include <string.h>
extern void *r5_stage411_dlsym(void *,const char *);
extern int r5_native_fsys_open(const char *,uint32_t,uint64_t *);
extern int r5_native_fsys_write(uint64_t,const void *,uint64_t);
extern int r5_native_fsys_close(uint64_t);
#define RFLAGS (0x8000|0x20000|0x80000|0x800)
#define WFLAGS (RFLAGS|1|0x40|0x80)
static int safe(const char*n){
 unsigned len=0;if(!n)return 0;while(len<76&&n[len])len++;
 if(len==11&&(!memcmp(n,"R5SOUND.IDX",11)||!memcmp(n,"R5SOUND.SEL",11)||!memcmp(n,"R5SOUND.VOL",11)||!memcmp(n,"R5SOUND.NEW",11)))return 1;
 if(len!=73||memcmp(n,"R5SN_",5)||memcmp(n+69,".R5S",4))return 0;
 for(unsigned i=5;i<69;i++)if(!((n[i]>='0'&&n[i]<='9')||(n[i]>='a'&&n[i]<='f')))return 0;
 return 1;
}
static int read_all(struct r5_lut_directory*d,int fd,uint8_t*p,size_t cap,size_t*out){
 size_t used=0;unsigned calls=0;
 while(used<cap){size_t k=cap-used;if(k>65536)k=65536;intptr_t n=d->api.read(fd,p+used,k);if(n<0||(size_t)n>k||++calls>cap+1)return -1;if(!n){*out=used;return 0;}used+=(size_t)n;}
 uint8_t tail;intptr_t n=d->api.read(fd,&tail,1);if(n)return -1;*out=used;return 0;
}
static int read_file(void*ctx,const char*name,uint8_t*p,size_t cap,size_t*out){
 struct r5_lut_directory*d=ctx;if(!safe(name)||!p||!out||d->phase!=2)return -1;
 int fd=d->api.openat(d->fd,name,RFLAGS,0);if(fd<0)return *d->api.error_number()==2?1:-1;
 int rc=read_all(d,fd,p,cap,out),close=d->api.close(fd);return rc||close?-1:0;
}
static int remove_file(void*ctx,const char*name){struct r5_lut_directory*d=ctx;if(!safe(name)||d->phase!=2)return -1;return d->api.unlinkat(d->fd,name,0)&&*d->api.error_number()!=2?-1:0;}
typedef intptr_t (*sound_pread)(int,void *,size_t,int64_t);
static int pread_all(sound_pread read,int fd,uint8_t*p,size_t n,int64_t offset){
 size_t at=0;
 while(at<n){intptr_t got=read(fd,p+at,n-at,offset+(int64_t)at);if(got<=0||(size_t)got>n-at||!r5_session_current())return -1;at+=(size_t)got;}
 return 0;
}
static int read_audio(void*ctx,const char*name,const uint8_t*identity,size_t bytes,unsigned volume,uint8_t*p,size_t cap,size_t*out){
 struct r5_lut_directory*d=ctx;
 if(!safe(name)||!identity||!p||!out||d->phase!=2||volume<1||volume>10||cap<R5SOUND_STAGING_BYTES||!r5_session_current())return -1;
 sound_pread read=(sound_pread)r5_stage411_dlsym(0,"pread64");if(!read)return -1;
 int fd=d->api.openat(d->fd,name,RFLAGS,0);if(fd<0)return -1;
 uint8_t header[R5SOUND_PACKAGE_HEADER_BYTES],hash[32],tail;int rc=-1;r5sound_package_info info;
 if(pread_all(read,fd,header,sizeof header,0)||r5sound_package_header(header,sizeof header,bytes,&info))goto done;
 if(ss_sha256(header,sizeof header,hash)||memcmp(hash,identity,32))goto done;
 /* Both probes bind the external size without introducing another stat ABI.
  * Header, requested payload and probes refer to this same open inode. */
 if(read(fd,&tail,1,(int64_t)bytes-1)!=1||read(fd,&tail,1,(int64_t)bytes)!=0)goto done;
 memset(p,0,cap);
 if(pread_all(read,fd,p,info.encoded_bytes,R5SOUND_PACKAGE_HEADER_BYTES+(int64_t)(volume-1)*info.encoded_bytes))goto done;
 if(r5sound_package_audio(header,&info,volume,p,info.encoded_bytes)||!r5_session_current())goto done;
 rc=0;
done:
 if(d->api.close(fd))rc=-1;
 if(!rc)*out=info.encoded_bytes;
 return rc;
}
static int atomic_file(void*ctx,const char*name,const uint8_t*p,size_t n){
 struct r5_lut_directory*d=ctx;size_t at=0;int rc=0,fd=-1;uint8_t verify[4096];
 if(!safe(name)||!p||!n||d->phase!=2||!r5_session_current())return -1;
 if(!memcmp(name,"R5SOUND.NEW",12))return -1;
 if(remove_file(ctx,"R5SOUND.NEW"))return -1;
 fd=d->api.openat(d->fd,"R5SOUND.NEW",WFLAGS,0600);if(fd<0)return -1;
 while(at<n){size_t k=n-at;if(k>65536)k=65536;intptr_t wrote=d->api.write(fd,p+at,k);if(wrote<=0||(size_t)wrote>k||!r5_session_current()){rc=-1;break;}at+=(size_t)wrote;}
 if(!rc&&d->api.sync(fd))rc=-1;if(d->api.close(fd))rc=-1;if(rc)return -1;
 fd=d->api.openat(d->fd,"R5SOUND.NEW",RFLAGS,0);if(fd<0)return -1;
 for(at=0;at<n;){size_t k=n-at;if(k>sizeof verify)k=sizeof verify;intptr_t got=d->api.read(fd,verify,k);if(got<=0||(size_t)got>k||memcmp(verify,p+at,(size_t)got)){rc=-1;break;}at+=(size_t)got;}
 if(!rc&&d->api.read(fd,verify,1)!=0)rc=-1;
 if(d->api.close(fd))rc=-1;if(rc||!r5_session_current())return -1;
 if(d->api.renameat(d->fd,"R5SOUND.NEW",d->fd,name))return -1;
 /* A sync failure after rename is reported as uncertain, never rollback. */
 return d->api.sync(d->fd)?-1:0;
}
void r5sound_storage_bind(r5sound_storage*s,struct r5_lut_directory*d){
 uintptr_t a=(uintptr_t)read_file,b=(uintptr_t)atomic_file,c=(uintptr_t)remove_file,e=(uintptr_t)read_audio;
 __asm__ volatile("" : "+r"(a),"+r"(b),"+r"(c),"+r"(e));
 *s=(r5sound_storage){d,(void*)a,(void*)b,(void*)c,0,(void*)e};
}
static uint32_t log_drives;
static char*hex(char*p,uint32_t x){static const char digits[]="0123456789abcdef";for(int i=7;i>=0;i--)*p++=digits[(x>>(i*4))&15];return p;}
void r5sound_log(unsigned drive,const char*stage,const char*name,int rc,const uint32_t*v,unsigned n){
 if(drive<'A'||drive>'Z'||!stage||n>32)return;
 char path[]="A:/R5SOUND.LOG",buf[768],*p=buf;uint64_t handle=0;path[0]=(char)drive;
 for(unsigned i=0;i<40&&stage[i];i++)*p++=stage[i];
 *p++=' ';p=hex(p,(uint32_t)rc);
 for(unsigned i=0;i<n;i++){*p++=' ';p=hex(p,v[i]);}
 if(name){*p++=' ';*p++='[';for(unsigned i=0;i<255&&name[i];i++){unsigned c=(unsigned char)name[i];*p++=c<32||c==127?'?':(char)c;}*p++=']';}*p++='\n';
 int (*flush)(uint64_t)=(void*)r5_stage411_dlsym(0,"Fsys_Flush");
 if(r5_native_fsys_open(path,(log_drives&(1u<<(drive-'A')))?0x16u:0x0eu,&handle))return;
 log_drives|=1u<<(drive-'A');
 int written=r5_native_fsys_write(handle,buf,(uint64_t)(p-buf));int synced=flush?flush(handle):-1;int closed=r5_native_fsys_close(handle);
 (void)written;(void)synced;(void)closed;
}
