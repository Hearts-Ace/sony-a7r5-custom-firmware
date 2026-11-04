#include "sound_core.h"
#include <string.h>
/* Retain the freestanding comparison primitive formerly supplied by the
 * converter; host tests use libc. No audio conversion remains here. */
#ifdef R5SS_SHARED_MEMSET
int memcmp(const void *a,const void *b,size_t n) {
    const uint8_t *x=a,*y=b;
    for(size_t i=0;i<n;i++)if(x[i]!=y[i])return (int)x[i]-(int)y[i];
    return 0;
}
#endif
int ss_valid_name(const char *name, size_t n) {
    size_t i=0;
    if (!name || n<5 || n>=SS_NAME_BYTES) return 0;
    if (name[n-4]!='.' || (name[n-3]!='r' && name[n-3]!='R') ||
        name[n-2]!='5' || (name[n-1]!='s' && name[n-1]!='S')) return 0;
    if (name[0]==' ' || name[n-1]==' ' || name[0]=='.') return 0;
    while (i<n) {
        uint32_t c=(uint8_t)name[i++], value, min; size_t extra, j;
        if (c<128) {
            if (c<32 || c==127 || c=='/' || c=='\\' || c==':' || c=='*' ||
                c=='?' || c=='"' || c=='<' || c=='>' || c=='|') return 0;
            continue;
        }
        if (c>=0xc2 && c<=0xdf) { extra=1; value=c&31; min=0x80; }
        else if (c>=0xe0 && c<=0xef) { extra=2; value=c&15; min=0x800; }
        else if (c>=0xf0 && c<=0xf4) { extra=3; value=c&7; min=0x10000; }
        else return 0;
        if (extra>n-i) return 0;
        for (j=0;j<extra;j++) { c=(uint8_t)name[i++]; if ((c&0xc0)!=0x80) return 0; value=(value<<6)|(c&63); }
        if (value<min || value>0x10ffff || (value>=0xd800 && value<=0xdfff)) return 0;
    }
    return 1;
}

#ifdef R5SS_NATIVE_SHA256
/* Existing AP libcrypto imports. Native ARM64 replay proves the 112-byte
 * SHA256_CTX ABI and return1 contract; no new loader symbol or dlsym. */
extern int r5sound_sha256_init(void *);
extern int r5sound_sha256_update(void *,const void *,size_t);
extern int r5sound_sha256_final(void *,void *);
int ss_sha256(const uint8_t *bytes,size_t n,uint8_t digest[32]){
    _Alignas(16) uint8_t context[112];
    if(r5sound_sha256_init(context)!=1 ||
       r5sound_sha256_update(context,bytes,n)!=1 ||
       r5sound_sha256_final(digest,context)!=1)return -1;
    return 0;
}
#else
static uint32_t rotr(uint32_t v, unsigned n) { return (v>>n)|(v<<(32-n)); }
static void hash_block(uint32_t h[8], const uint8_t p[64]) {
    static const uint32_t k[64]={
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
    uint32_t w[64],a,b,c,d,e,f,g,v; unsigned i;
    for(i=0;i<16;i++) w[i]=((uint32_t)p[i*4]<<24)|((uint32_t)p[i*4+1]<<16)|((uint32_t)p[i*4+2]<<8)|p[i*4+3];
    for(i=16;i<64;i++) w[i]=w[i-16]+(rotr(w[i-15],7)^rotr(w[i-15],18)^(w[i-15]>>3))+
        w[i-7]+(rotr(w[i-2],17)^rotr(w[i-2],19)^(w[i-2]>>10));
    a=h[0];b=h[1];c=h[2];d=h[3];e=h[4];f=h[5];g=h[6];v=h[7];
    for(i=0;i<64;i++) {
        uint32_t t1=v+(rotr(e,6)^rotr(e,11)^rotr(e,25))+((e&f)^((~e)&g))+k[i]+w[i];
        uint32_t t2=(rotr(a,2)^rotr(a,13)^rotr(a,22))+((a&b)^(a&c)^(b&c));
        v=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
    }
    h[0]+=a;h[1]+=b;h[2]+=c;h[3]+=d;h[4]+=e;h[5]+=f;h[6]+=g;h[7]+=v;
}
int ss_sha256(const uint8_t *bytes, size_t n, uint8_t digest[32]) {
    uint32_t h[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    uint8_t tail[128]; size_t i, left=n; uint64_t bits=(uint64_t)n*8; size_t blocks;
    while (left>=64) { hash_block(h,bytes); bytes+=64; left-=64; }
    memset(tail,0,sizeof(tail)); if(left) memcpy(tail,bytes,left); tail[left]=0x80;
    blocks=left<56 ? 1 : 2;
    for(i=0;i<8;i++) tail[blocks*64-1-i]=(uint8_t)(bits>>(i*8));
    hash_block(h,tail); if(blocks==2) hash_block(h,tail+64);
    for(i=0;i<8;i++) { digest[i*4]=(uint8_t)(h[i]>>24); digest[i*4+1]=(uint8_t)(h[i]>>16); digest[i*4+2]=(uint8_t)(h[i]>>8); digest[i*4+3]=(uint8_t)h[i]; }
    return 0;
}
#endif
static uint32_t crc_step(uint32_t crc, uint8_t b) {
    unsigned bit; crc^=b; for(bit=0;bit<8;bit++) crc=(crc>>1)^(0xedb88320u & (0u-(crc&1u))); return crc;
}
uint32_t ss_crc32(const uint8_t *p, size_t n) { uint32_t crc=0xffffffffu; size_t i; for(i=0;i<n;i++) crc=crc_step(crc,p[i]); return ~crc; }
