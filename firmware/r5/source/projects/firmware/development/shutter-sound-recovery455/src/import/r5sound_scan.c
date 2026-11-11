#include "r5sound_scan.h"
#include "sound_core.h"

static uint64_t get64(const unsigned char *p){
 uint64_t x=0;for(unsigned i=0;i<8;i++)x|=(uint64_t)p[i]<<(i*8);return x;
}
static int extension(const char *p,size_t n){
 return n>=5&&p[n-4]=='.'&&(p[n-3]|32)=='r'&&
        p[n-2]=='5'&&(p[n-1]|32)=='s';
}
int r5sound_scan_name(const char *p,size_t n){
 return ss_valid_name(p,n);
}
static int current(const struct r5sound_scan_api *a){return !a->current||a->current(a->current_context);}
int r5sound_scan_root(const struct r5sound_scan_api *a,char drive,void *scratch,size_t cap,
                     r5sound_scan_visit visit,void *ctx,struct r5sound_scan_result *out){
 if(!out)return R5SOUND_SCAN_INVALID;
 *out=(struct r5sound_scan_result){0};
 if(!a||!a->first||!a->next||!scratch||cap<R5SOUND_FIND_SCRATCH_BYTES||
    (uintptr_t)scratch%8||!visit||drive<'A'||drive>'Z')return R5SOUND_SCAN_INVALID;
 unsigned char *info=scratch;char path[]="A:/*";path[0]=drive;
 for(size_t i=0;i<R5SOUND_FIND_SCRATCH_BYTES;i++)info[i]=0;
 if(!current(a))return R5SOUND_SCAN_CANCELED;
 int status=a->first(path,info);
 for(;;){
  out->native_status=status;
  if(!current(a))return R5SOUND_SCAN_CANCELED;
  if(status==4)return R5SOUND_SCAN_OK;
  if(status)return R5SOUND_SCAN_NATIVE;
  if(++out->entries>R5SOUND_SCAN_ENTRY_LIMIT)return R5SOUND_SCAN_LIMIT;
  uint8_t attr=info[0x26];
  if(attr&0x10)out->directories++;
  else {
   uintptr_t lo=(uintptr_t)info,hi=lo+R5SOUND_FIND_INFO_BYTES;
   uintptr_t name=(uintptr_t)get64(info);size_t n=0;
   if(name<lo||name>=hi)return R5SOUND_SCAN_CORRUPT;
   const char *p=(const char *)name;
   while(n<hi-name&&p[n])n++;
   if(n==hi-name)return R5SOUND_SCAN_CORRUPT;
   if(!extension(p,n))out->other++;
   else if(!r5sound_scan_name(p,n))out->unsafe++;
   else {
    out->packages++;
    out->visitor_status=visit(ctx,p,n,get64(info+8),attr);
    if(out->visitor_status)return R5SOUND_SCAN_VISITOR;
   }
  }
  if(!current(a))return R5SOUND_SCAN_CANCELED;
  status=a->next(info);
 }
}
