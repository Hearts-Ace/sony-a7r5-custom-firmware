#include "sd_native_look.h"

static const uint8_t magic[8]={'R','5','C','U','S','T','4',0};
static const uint8_t model[16]={'I','L','C','E','-','7','R','M','5',0,0,0,0,0,0,0};
static const uint8_t base_ap[32] = {
    0x8e,0xe4,0xd5,0x87,0x6b,0x7e,0x12,0x7d,0xf3,0x9f,0x8f,0x82,0x0b,0x9d,0x21,0x83,
    0x4c,0x30,0x0f,0xf8,0x95,0xe0,0x2c,0xa5,0x22,0x63,0x6e,0xd4,0x73,0x3e,0xfc,0x4b
};
static const uint8_t base_cp[32] = {
    0x8e,0x9e,0x26,0xbf,0x2e,0x4b,0x93,0xfa,0x51,0x42,0xe9,0x61,0xdc,0xf2,0x1c,0xb0,
    0xf4,0x3f,0x88,0x71,0x28,0x38,0x14,0xbe,0x2d,0xcf,0xb0,0xa6,0x94,0xcb,0x5a,0x32
};
static uint32_t u32(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static int16_t s16(const uint8_t *p) {
    int32_t v = (int32_t)p[0] | (int32_t)p[1]<<8;
    return (int16_t)(v >= 32768 ? v-65536 : v);
}
static int equal(const uint8_t *a, const uint8_t *b, size_t n) {
    size_t i;
    for (i=0;i<n;i++) if (a[i]!=b[i]) return 0;
    return 1;
}
static int zeros(const uint8_t *p, size_t n) {
    size_t i;
    for (i=0;i<n;i++) if (p[i]) return 0;
    return 1;
}
static uint32_t checksum(const uint8_t *p, size_t n) {
    uint32_t c=0xffffffffu;
    size_t i;
    unsigned bit;
    for (i=0;i<n;i++) {
        c ^= (i>=112 && i<116) ? 0u : p[i];
        for (bit=0;bit<8;bit++) c=(c>>1) ^ (0xedb88320u & (0u-(c&1u)));
    }
    return c^0xffffffffu;
}
/* Strict UTF-8, 1..capacity-1 bytes followed by zero padding. No C0/C1,
 * overlongs, surrogate scalar or codepoint beyond U+10ffff. */
static int valid_name(const uint8_t *p, unsigned capacity) {
    unsigned i=0,j,n;uint32_t cp,min;
    if(!p[0])return 0;
    while(i<capacity&&p[i]) {
        unsigned a=p[i++];
        if(a<128){if(a<32||a==127)return 0;continue;}
        if(a>=0xc2&&a<=0xdf){n=1;cp=a&31u;min=128;}
        else if(a>=0xe0&&a<=0xef){n=2;cp=a&15u;min=2048;}
        else if(a>=0xf0&&a<=0xf4){n=3;cp=a&7u;min=65536;}
        else return 0;
        for(j=0;j<n;j++){if(i>=capacity||(p[i]&0xc0)!=0x80)return 0;cp=(cp<<6)|(p[i++]&63u);}
        if(cp<min||cp>0x10ffffu||(cp>=0xd800&&cp<=0xdfff)||cp<=159)return 0;
    }
    if(i==capacity)return 0;
    for(;i<capacity;i++)if(p[i])return 0;
    return 1;
}
static int grid_valid(const struct r5_native_look *v) {
    unsigned i; const int8_t *p=(const int8_t *)v->grid;
    if(v->grid_padding)return 0;
    for(i=0;i<1215;i++)if(p[i]<-64 || p[i]>63)return 0;
    return 1;
}
static int valid_record(const uint8_t *p) {
    unsigned i,g,k; uint32_t last=0;
    if(u32(p)<1 || u32(p)>12 || !valid_name(p+4,24) ||
       !valid_name(p+28,64) || !zeros(p+2447,5)) return 0;
    for(i=0;i<1215;i++){int v=(int8_t)p[1232+i];if(v< -64 || v>63)return 0;}
    for(g=0;g<3;g++)for(i=0;i<8;i++) {
        int32_t v=s16(p+92+2*i); if(g)v+=s16(p+92+16*g+2*i);
        if(i<4 ? (v < -1024 || v > 1023) : (v < 0 || v > 1023))return 0;
    }
    for(k=0;k<288;k++){int32_t v=s16(p+140+2*k);if(v< -8192 || v>8191)return 0;}
    for(i=0;i<129;i++){uint32_t v=u32(p+716+4*i);if((!i && v) || v<last || v>131071)return 0;last=v;}
    return 1;
}
static void decode_record(const uint8_t *p, struct r5_native_look *out) {
    unsigned i,g,s,k;
    for(i=0;i<24;i++)out->short_name[i]=(char)p[4+i];
    for(i=0;i<64;i++)out->full_name[i]=(char)p[28+i];
    for(g=0;g<3;g++)for(i=0;i<8;i++)out->cc1[g][i]=s16(p+92+16*g+2*i);
    for(g=0;g<3;g++)for(s=0;s<16;s++)for(k=0;k<6;k++)out->block13[g][s][k]=s16(p+140+2*(96*g+6*s+k));
    for(i=0;i<129;i++)out->gamma[i]=u32(p+716+4*i);
    for(i=0;i<1215;i++)((int8_t *)out->grid)[i]=(int8_t)p[1232+i];
    out->grid_padding=0;
}
int r5_decode_look_file(const uint8_t *p, size_t n, struct r5_look_set *out) {
    uint32_t count,mask,found=0,previous=0,i;
    if (!p || !out || n<R5_LOOK_HEADER || n>R5_LOOK_MAX) return R5_INVALID;
    {uintptr_t a=(uintptr_t)p,b=(uintptr_t)out;
     if(b>=a ? b-a<n : a-b<sizeof(*out))return R5_INVALID;}
    count=u32(p+20);mask=u32(p+24);
    if (!equal(p,magic,8) || u32(p+8)!=R5_LOOK_VERSION || u32(p+12)!=R5_LOOK_HEADER || u32(p+16)!=n ||
        count>12 || n!=R5_LOOK_HEADER+(size_t)count*R5_LOOK_RECORD ||
        (mask&~4095u) || u32(p+28)!=0 || !equal(p+32,model,16) ||
        !equal(p+48,base_ap,32) || !equal(p+80,base_cp,32) || !zeros(p+116,12) ||
        checksum(p,n)!=u32(p+112)) return R5_INVALID;
    /* Two passes: even malformed last records leave out entirely untouched. */
    for (i=0;i<count;i++) {
        const uint8_t *r=p+R5_LOOK_HEADER+(size_t)i*R5_LOOK_RECORD;
        uint32_t slot=u32(r);
        if (!valid_record(r) || slot<=previous) return R5_INVALID;
        found|=1u<<(slot-1);previous=slot;
    }
    if (found!=mask) return R5_INVALID;
    /* Full replacement: validation above is atomic with respect to output. */
    for(size_t clear=0;clear<sizeof(*out);clear++)((uint8_t *)out)[clear]=0;
    for (i=0;i<count;i++) {
        const uint8_t *r=p+R5_LOOK_HEADER+(size_t)i*R5_LOOK_RECORD;
        decode_record(r,&out->look[u32(r)-1]);
    }
    out->valid_mask=mask;
    return R5_IMPORTED;
}
static void put16(uint8_t *p, int16_t v) {
    uint16_t n=(uint16_t)v;
    p[0]=(uint8_t)n;p[1]=(uint8_t)(n>>8);
}
static void put32(uint8_t *p, uint32_t v) {
    p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);p[2]=(uint8_t)(v>>16);p[3]=(uint8_t)(v>>24);
}
static int valid_look(const struct r5_native_look *look) {
    unsigned i,g,s,k;
    uint32_t last=0;
    if (!valid_name((const uint8_t *)look->short_name,24) || !valid_name((const uint8_t *)look->full_name,64) || !grid_valid(look)) return 0;
    for (g=0;g<3;g++) for (i=0;i<8;i++) {
        int32_t v=look->cc1[0][i];
        if (g) v+=look->cc1[g][i];
        if (i<4 ? (v < -1024 || v > 1023) : (v < 0 || v > 1023)) return 0;
    }
    for (g=0;g<3;g++) for (s=0;s<16;s++) for (k=0;k<6;k++) {
        int32_t v=look->block13[g][s][k];
        if (v < -8192 || v > 8191) return 0;
    }
    for (i=0;i<129;i++) {
        uint32_t v=look->gamma[i];
        if ((i==0 && v!=0) || v<last || v>131071u) return 0;
        last=v;
    }
    return 1;
}
size_t r5_encode_look_file(const struct r5_look_set *set, uint8_t *out, size_t capacity) {
    unsigned slot,count=0,i,g,s,k;
    size_t n,at;
    uintptr_t source,target;
    if (!set || !out || (set->valid_mask&~4095u)) return 0;
    for (slot=0;slot<12;slot++) if (set->valid_mask&(1u<<slot)) {
        if (!valid_look(&set->look[slot])) return 0;
        count++;
    }
    n=R5_LOOK_HEADER+(size_t)count*R5_LOOK_RECORD;
    if (capacity<n) return 0;
    source=(uintptr_t)set;target=(uintptr_t)out;
    if (target>=source ? target-source<sizeof(*set) : source-target<n) return 0;
    for (at=0;at<n;at++) out[at]=0;
    for (i=0;i<8;i++) out[i]=magic[i];
    put32(out+8,R5_LOOK_VERSION);put32(out+12,R5_LOOK_HEADER);put32(out+16,(uint32_t)n);
    put32(out+20,count);put32(out+24,set->valid_mask);
    for (i=0;i<16;i++) out[32+i]=model[i];
    for (i=0;i<32;i++) {out[48+i]=base_ap[i];out[80+i]=base_cp[i];}
    at=R5_LOOK_HEADER;
    for (slot=0;slot<12;slot++) if (set->valid_mask&(1u<<slot)) {
        const struct r5_native_look *look=&set->look[slot];
        uint8_t *r=out+at;
        put32(r,slot+1);
        for (i=0;i<24;i++) r[4+i]=(uint8_t)look->short_name[i];
        for (i=0;i<64;i++) r[28+i]=(uint8_t)look->full_name[i];
        for (g=0;g<3;g++) for (i=0;i<8;i++) put16(r+92+16*g+2*i,look->cc1[g][i]);
        for (g=0;g<3;g++) for (s=0;s<16;s++) for (k=0;k<6;k++)
            put16(r+140+2*(96*g+6*s+k),look->block13[g][s][k]);
        for (i=0;i<129;i++) put32(r+716+4*i,look->gamma[i]);
        for(i=0;i<1215;i++)r[1232+i]=((const uint8_t *)look->grid)[i];
        at+=R5_LOOK_RECORD;
    }
    put32(out+112,checksum(out,n));
    return n;
}

_Static_assert(sizeof(struct r5_native_look)==2444,"v4 AP look ABI");
_Static_assert(sizeof(struct r5_look_set)==29332,"v4 AP set ABI");

/* Canonical CP wire projection: preserve the proven 2392-byte CP layout. */
int r5_filter_pack_compact(const struct r5_native_look *v,uint8_t out[2392]) {
    uintptr_t a=(uintptr_t)v,b=(uintptr_t)out;unsigned i,g,s,k;
    if(!v || !out || !valid_look(v) ||
       (b>=a ? b-a<sizeof(*v) : a-b<2392))return 0;
    for(i=0;i<2392;i++)out[i]=0;
    for(i=0;i<24;i++)out[i]=(uint8_t)v->short_name[i];
    for(g=0;g<3;g++)for(i=0;i<8;i++)put16(out+32+16*g+2*i,v->cc1[g][i]);
    for(g=0;g<3;g++)for(s=0;s<16;s++)for(k=0;k<6;k++)put16(out+80+2*(96*g+6*s+k),v->block13[g][s][k]);
    for(i=0;i<129;i++)put32(out+656+4*i,v->gamma[i]);
    put32(out+1172,1);
    for(i=0;i<1215;i++)out[1176+i]=((const uint8_t *)v->grid)[i];
    return 1;
}
uint32_t r5_filter_compact_set_crc(const struct r5_look_set *set) {
    uint8_t packed[2392];uint32_t c=~0u;unsigned i,j,k;
    if(!set || (set->valid_mask&~4095u))return 0;
    for(i=0;i<12;i++)if((set->valid_mask&(1u<<i)) && !valid_look(&set->look[i]))return 0;
    for(k=0;k<4;k++) {c^=(uint8_t)(set->valid_mask>>(8*k));for(j=0;j<8;j++)c=(c>>1)^((0u-(c&1u))&0xedb88320u);}
    for(i=0;i<12;i++)if(set->valid_mask&(1u<<i)) {
        for(k=0;k<4;k++){c^=(uint8_t)((i+1)>>(8*k));for(j=0;j<8;j++)c=(c>>1)^((0u-(c&1u))&0xedb88320u);}
        if(!r5_filter_pack_compact(&set->look[i],packed))return 0;
        for(k=0;k<2392;k++){c^=packed[k];for(j=0;j<8;j++)c=(c>>1)^((0u-(c&1u))&0xedb88320u);}
    }
    return ~c;
}
