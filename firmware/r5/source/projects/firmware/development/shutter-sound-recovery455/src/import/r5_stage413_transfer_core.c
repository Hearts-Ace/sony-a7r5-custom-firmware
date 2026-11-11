/* AP-only projection of r5_look_transfer.c; upload-only profile; NOT_READY is rejected (no readiness consumers). */
#include "r5_look_transfer.h"
#include "r5_filter423.h"
#define BUILDING 0x35424c44u
#define SEALED 0x35424c53u
static uint32_t get32(const uint8_t *p) {
    return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
static void put32(uint8_t *p,uint32_t v) {
    p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);p[2]=(uint8_t)(v>>16);p[3]=(uint8_t)(v>>24);
}
static uint32_t crcbyte(uint32_t c,uint8_t b) {
    unsigned k;c^=b;
    for(k=0;k<8;k++)c=(c>>1)^((0u-(c&1u))&0xedb88320u);
    return c;
}
static uint32_t message_crc(const uint8_t *p,size_t n) {
    uint32_t c=~0u;size_t i;
    for(i=0;i<n;i++)c=crcbyte(c,(i>=28&&i<32)?0:p[i]);
    return ~c;
}
int r5_transfer_is_envelope(const uint8_t *p,size_t n) {
    return p&&n>=8&&p[0]==R5_TRANSFER_CLASS&&p[4]=='R'&&p[5]=='5'&&p[6]=='N'&&p[7]=='X';
}
static void header(uint8_t *p,unsigned op,uint32_t token,uint32_t mask,uint32_t slot,uint32_t crc,uint32_t seq) {
    size_t i;for(i=0;i<32;i++)p[i]=0;p[0]=R5_TRANSFER_CLASS;p[1]=3;p[2]=(uint8_t)op;
    p[4]='R';p[5]='5';p[6]='N';p[7]='X';put32(p+8,token);put32(p+12,mask);
    put32(p+16,slot);put32(p+20,crc);put32(p+24,seq);
}
static unsigned next_slot(uint32_t mask,unsigned last) {
    unsigned s;for(s=last+1;s<=12;s++)if(mask&(1u<<(s-1)))return s;return 13;
}
int r5_transfer_ap_begin(struct r5_transfer_ap *a,const struct r5_look_set *s,
    uint32_t token,uint32_t digest,uint64_t now,uint64_t deadline) {
    if(!a||!s||a->phase||!token||(s->valid_mask&~4095u)||now>=deadline)return -1;
    a->set=s;a->token=token;a->mask=s->valid_mask;a->payload_crc=digest;
    a->slot=0;a->sequence=0;a->phase=1;a->error=0;a->last_now=now;a->deadline=deadline;a->retry_at=0;return 0;
}
static int time_ok(struct r5_transfer_ap *a,uint64_t now) {
    if(now<a->last_now||now>=a->deadline){a->phase=5;a->error=1;return 0;}
    a->last_now=now;return 1;
}
int r5_transfer_ap_step(struct r5_transfer_ap *a,const struct r5_transfer_io *io,
    uint64_t now,uint8_t p[R5_TRANSFER_MAX]) {
    unsigned op;size_t n=32;
    if(!a||!io||!io->send||!p||!a->phase||a->phase==5)return -1;
    if(a->phase==4)return 1;
    if(!time_ok(a,now))return -1;
    if(a->phase==2)return 0;
    if(a->phase==6) {
        if(now<a->retry_at)return 0;
        a->phase=1;
    }
    op=a->sequence==0?R5_X_BEGIN:a->sequence==13?R5_X_SEAL:R5_X_PUT;
    header(p,op,a->token,a->mask,a->slot,a->payload_crc,a->sequence);
    if(op==R5_X_PUT){n=R5_TRANSFER_MAX;if(!r5_filter_pack_compact(&a->set->look[a->slot-1],p+32)){a->phase=5;a->error=4;return -1;}}
    put32(p+28,message_crc(p,n));a->phase=2;
    if(io->send(io->context,p,n)){a->phase=5;a->error=2;return -1;}
    return 0;
}
int r5_transfer_ap_ack(struct r5_transfer_ap *a,const uint8_t *p,size_t n,uint64_t now) {
    uint32_t state,status,received;
    if(!a||a->phase!=2||!time_ok(a,now))return -1;
    if(n!=R5_TRANSFER_ACK||!r5_transfer_is_envelope(p,n)||p[1]!=3||p[2]!=R5_X_ACK||p[3]||
       get32(p+28)!=message_crc(p,n)||get32(p+8)!=a->token||get32(p+12)!=a->mask||
       get32(p+16)!=a->slot||get32(p+20)!=a->payload_crc||get32(p+24)!=a->sequence)goto bad;
    state=get32(p+32);status=get32(p+36);received=get32(p+40);
    if(!status&&a->sequence==0&&state==SEALED&&received==a->mask){a->phase=4;return 1;}
    if(status||state!=(a->sequence==13?SEALED:BUILDING))goto bad;
    if(a->sequence==13){if(received!=a->mask)goto bad;a->phase=4;return 1;}
    if(a->sequence==0){if(received)goto bad;}
    else if(received!=(a->mask&((1u<<a->slot)-1u)))goto bad;
    a->slot=next_slot(a->mask,a->slot);a->sequence=a->slot;
    if(a->slot==13)a->slot=0;
    a->phase=1;return 0;
bad:
    a->phase=5;a->error=3;return -1;
}
uint32_t r5_transfer_ap_active_mask(const struct r5_transfer_ap *a) {
    return a&&a->phase==4?a->mask:0;
}
