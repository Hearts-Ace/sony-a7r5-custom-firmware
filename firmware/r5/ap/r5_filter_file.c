#include "r5_filter_file.h"

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
static uint32_t file_checksum(const uint8_t *p, size_t n) {
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

static void copy(void *out,const void *src,size_t n){
    uint8_t *d=out;const uint8_t *p=src;for(size_t i=0;i<n;i++)d[i]=p[i];
}
static void zero(void *out,size_t n){uint8_t *p=out;for(size_t i=0;i<n;i++)p[i]=0;}
uint32_t r5f_crc(const uint8_t *p,size_t n){
    uint32_t c=~0u;for(size_t i=0;i<n;i++){c^=p[i];for(unsigned b=0;b<8;b++)c=(c>>1)^(0xedb88320u&(0u-(c&1u)));}return ~c;
}
static int header_valid(const uint8_t *p,size_t n){
    uint32_t count=u32(p+20),mask=u32(p+24);
    return equal(p,magic,8) && u32(p+8)==4 && u32(p+12)==R5F_HEADER && u32(p+16)==n &&
       count<=12 && n==R5F_HEADER+(size_t)count*R5F_RECORD && !(mask&~4095u) && !u32(p+28) &&
       equal(p+32,model,16) && equal(p+48,base_ap,32) && equal(p+80,base_cp,32) && zeros(p+116,12);
}
int r5f_index_bytes(const uint8_t *p,size_t n,struct r5f_index *out){
    struct r5f_index next;uint32_t count,found=0,last=0;
    if(!p || !out || n<R5F_HEADER || n>R5F_MAX || !header_valid(p,n) || file_checksum(p,n)!=u32(p+112))return -1;
    {uintptr_t a=(uintptr_t)p,b=(uintptr_t)out;if(b>=a?b-a<n:a-b<sizeof(*out))return -1;}
    zero(&next,sizeof(next));copy(next.header,p,R5F_HEADER);next.mask=u32(p+24);count=u32(p+20);
    for(uint32_t i=0;i<count;i++){
        uint32_t offset=R5F_HEADER+i*R5F_RECORD;const uint8_t *r=p+offset;uint32_t slot=u32(r);
        if(!valid_record(r)||slot<=last)return -1;last=slot;found|=1u<<(slot-1);
        next.entry[slot-1].offset=offset;next.entry[slot-1].crc=r5f_crc(r,R5F_RECORD);
        copy(next.entry[slot-1].short_name,r+4,24);copy(next.entry[slot-1].full_name,r+28,64);
    }
    if(found!=next.mask)return -1;copy(out,&next,sizeof(next));return 0;
}
static int exact(const struct r5f_reader *reader,uint32_t offset,uint8_t *out,size_t n){
    for(size_t used=0;used<n;){size_t got=0;
        if(reader->read_at(reader->context,offset+(uint32_t)used,out+used,n-used,&got)||!got||got>n-used)return -1;
        used+=got;
    }return 0;
}
int r5f_read_one(const struct r5f_reader *reader,const struct r5f_index *index,unsigned slot,uint8_t compact[R5F_COMPACT]){
    uint8_t header[R5F_HEADER],record[R5F_RECORD],end;size_t got=0;const struct r5f_entry *entry;
    if(!reader||!reader->read_at||!index||!compact||slot<1||slot>12||!(index->mask&(1u<<(slot-1))))return -1;
    entry=&index->entry[slot-1];
    if(exact(reader,0,header,sizeof(header))||!equal(header,index->header,sizeof(header)))return -1;
    /* Read at EOF once so an appended or truncated replacement cannot pass by
     * retaining the old header; record identity is independently checked. */
    if(exact(reader,u32(header+16)-1,&end,1)||reader->read_at(reader->context,u32(header+16),&end,1,&got)||got)return -1;
    if(exact(reader,entry->offset,record,sizeof(record))||r5f_crc(record,sizeof(record))!=entry->crc||
       u32(record)!=slot||!valid_record(record))return -1;
    zero(compact,R5F_COMPACT);copy(compact,record+4,24);
    copy(compact+32,record+92,48);copy(compact+80,record+140,576);
    copy(compact+656,record+716,516);compact[1172]=1;
    copy(compact+1176,record+1232,1215);return 0;
}
static void put32(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
void r5f_empty(uint8_t out[R5F_HEADER]){
    zero(out,R5F_HEADER);copy(out,magic,8);put32(out+8,4);put32(out+12,R5F_HEADER);put32(out+16,R5F_HEADER);
    copy(out+32,model,16);copy(out+48,base_ap,32);copy(out+80,base_cp,32);put32(out+112,file_checksum(out,R5F_HEADER));
}
_Static_assert(sizeof(struct r5f_index)==1284,"parameter-free file index");
