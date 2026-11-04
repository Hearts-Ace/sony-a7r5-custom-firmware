#include "r5sound_package.h"
#include "sound_core.h"
#include <string.h>

static uint32_t package_u32(const uint8_t *p) {
 return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
static int package_span(const void *p,size_t n) {
 return p && n && (uintptr_t)p<=UINTPTR_MAX-n;
}
static int package_overlap(const void *a,size_t na,const void *b,size_t nb) {
 return (uintptr_t)a<(uintptr_t)b+nb && (uintptr_t)b<(uintptr_t)a+na;
}

int r5sound_package_header(const uint8_t *p,size_t n,size_t expected_total,
                          r5sound_package_info *out) {
 if(n<R5SOUND_PACKAGE_HEADER_BYTES || !package_span(p,n) ||
    !package_span(out,sizeof(*out)) ||
    package_overlap(p,n,out,sizeof(*out)) ||
    expected_total>R5SOUND_PACKAGE_MAX_BYTES ||
    expected_total<R5SOUND_PACKAGE_HEADER_BYTES+320u)return -1;
 if(memcmp(p,"R5SNDF0\0",8) || package_u32(p+8)!=1 ||
    package_u32(p+12)!=R5SOUND_PACKAGE_HEADER_BYTES ||
    package_u32(p+16)!=expected_total || package_u32(p+20)!=24000 ||
    package_u32(p+32)!=10 || package_u32(p+36))return -1;
 uint32_t frames=package_u32(p+24),bytes=package_u32(p+28);
 if(!frames || frames>48000 || bytes!=((frames+30u)/31u)*32u ||
    bytes>49568 || expected_total!=R5SOUND_PACKAGE_HEADER_BYTES+10u*bytes)return -1;
 for(size_t i=76;i<96;i++)if(p[i])return -1;
 uint8_t copy[R5SOUND_PACKAGE_HEADER_BYTES];
 memcpy(copy,p,sizeof copy);memset(copy+72,0,4);
 if(ss_crc32(copy,sizeof copy)!=package_u32(p+72))return -1;
 r5sound_package_info info={frames,bytes,(uint32_t)expected_total};
 *out=info;return 0;
}

/* Caller has already bounded the buffers, step and frame/byte relationship. */
static int package_payload(const uint8_t *header,const r5sound_package_info *info,
                           unsigned step,const uint8_t *p) {
 size_t n=info->encoded_bytes;
 for(size_t i=0;i<n;i+=32)if(p[i]>7)return -1;
 uint32_t tail=info->frames%31u;
 if(tail)for(size_t i=n-32u+1u+tail;i<n;i++)if(p[i])return -1;
 uint8_t digest[32];
 if(ss_sha256(p,n,digest))return -2;
 return memcmp(digest,header+96u+(step-1u)*32u,sizeof digest)?-1:0;
}

int r5sound_package_audio(const uint8_t *header,const r5sound_package_info *info,
                         unsigned step,const uint8_t *p,size_t n) {
 if(step<1 || step>10 || !package_span(header,R5SOUND_PACKAGE_HEADER_BYTES) ||
    !package_span(info,sizeof(*info)) || !package_span(p,n))return -1;
 r5sound_package_info checked;
 if(r5sound_package_header(header,R5SOUND_PACKAGE_HEADER_BYTES,info->total_bytes,&checked) ||
    checked.frames!=info->frames || checked.encoded_bytes!=info->encoded_bytes ||
    n!=checked.encoded_bytes)return -1;
 return package_payload(header,&checked,step,p);
}

int r5sound_package_validate(const uint8_t *p,size_t n,r5sound_package_info *out) {
 if(n<R5SOUND_PACKAGE_HEADER_BYTES || n>R5SOUND_PACKAGE_MAX_BYTES ||
    !package_span(p,n) || !package_span(out,sizeof(*out)) ||
    package_overlap(p,n,out,sizeof(*out)))return -1;
 r5sound_package_info info;
 if(r5sound_package_header(p,R5SOUND_PACKAGE_HEADER_BYTES,n,&info))return -1;
 for(unsigned step=1;step<=10;step++) {
  int rc=package_payload(p,&info,step,
   p+R5SOUND_PACKAGE_HEADER_BYTES+(step-1u)*info.encoded_bytes);
  if(rc)return rc;
 }
 *out=info;return 0;
}
