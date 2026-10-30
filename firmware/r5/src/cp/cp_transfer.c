#include "r5_look_transfer.h"
#define BUILDING 0x35424c44u
#define SEALED 0x35424c53u
_Static_assert(sizeof(struct r5_transfer_cp)==24,"CP context allocation ABI");
_Static_assert(sizeof(struct r5_boot_value)==R5_TRANSFER_VALUES,"compact wire ABI");
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
static int overlap(const void *a,size_t an,const void *b,size_t bn) {
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;return x>=y?x-y<bn:y-x<an;
}
static int s16(const uint8_t *p) {
    unsigned v=(unsigned)p[0]|((unsigned)p[1]<<8);return v<32768?(int)v:(int)v-65536;
}
static int valid_name(const uint8_t *p) {
    unsigned i=0,j,n;uint32_t cp,min;
    if(!p[0])return 0;
    while(i<32&&p[i]) {
        unsigned a=p[i++];
        if(a<128){if(a<32||a==127)return 0;continue;}
        if(a>=0xc2&&a<=0xdf){n=1;cp=a&31u;min=128;}
        else if(a>=0xe0&&a<=0xef){n=2;cp=a&15u;min=2048;}
        else if(a>=0xf0&&a<=0xf4){n=3;cp=a&7u;min=65536;}
        else return 0;
        for(j=0;j<n;j++){if(i>=32||(p[i]&0xc0)!=0x80)return 0;cp=(cp<<6)|(p[i++]&63u);}
        if(cp<min||cp>0x10ffffu||(cp>=0xd800&&cp<=0xdfff)||cp<=159)return 0;
    }
    if(i==32)return 0;
    for(;i<32;i++)if(p[i])return 0;
    return 1;
}

static int compact_valid(const uint8_t *p) {
    if(!valid_name(p))return 0;
    { unsigned j;
      if(get32(p+1172)!=1 || p[2391])return 0;
      for(j=0;j<1215;j++){int v=(int8_t)p[1176+j];if(v< -64||v>63)return 0;} }
    p+=32;
    unsigned g,i;uint32_t last=0;
    for(g=0;g<3;g++)for(i=0;i<8;i++) {
        int v=s16(p+2*i);if(g)v+=s16(p+16*g+2*i);
        if(i<4?(v< -1024||v>1023):(v<0||v>1023))return 0;
    }
    for(i=0;i<288;i++){int v=s16(p+48+2*i);if(v< -8192||v>8191)return 0;}
    for(i=0;i<129;i++){uint32_t v=get32(p+624+4*i);if((!i&&v)||v<last||v>131071)return 0;last=v;}
    return 1;
}
int r5_boot_bank_put_compact(struct r5_boot_bank *b,uint32_t token,unsigned slot,
    const uint8_t p[R5_TRANSFER_VALUES]) {
    uint32_t bit;size_t i;uint8_t *to;
    if(!b||!p||b->state!=BUILDING||b->token!=token||slot<1||slot>12)return -1;
    bit=1u<<(slot-1);
    if(!(b->expected_mask&bit)||(b->received_mask&bit)||
       overlap(b,sizeof(*b),p,R5_TRANSFER_VALUES)||!compact_valid(p))return -1;
    to=(uint8_t *)&b->value[slot-1];for(i=0;i<R5_TRANSFER_VALUES;i++)to[i]=p[i];
    b->received_mask|=bit;return 0;
}
uint32_t r5_transfer_bank_crc(const struct r5_boot_bank *b) {
    uint32_t c=~0u;unsigned slot,k;size_t i;
    if(!b||(b->expected_mask&~4095u)||b->received_mask!=b->expected_mask)return 0;
    /* Sealed generations are immutable. The verified digest is written before
     * native publication's release-store, using an existing reserved word. */
    if(b->state==SEALED)return b->reserved[0];
    for(k=0;k<4;k++)c=crcbyte(c,(uint8_t)(b->expected_mask>>(8*k)));
    for(slot=1;slot<=12;slot++)if(b->expected_mask&(1u<<(slot-1))) {
        const uint8_t *p=(const uint8_t *)&b->value[slot-1];
        for(k=0;k<4;k++)c=crcbyte(c,(uint8_t)(slot>>(8*k)));
        for(i=0;i<R5_TRANSFER_VALUES;i++)c=crcbyte(c,p[i]);
    }
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
static int seal_verified(struct r5_boot_bank *b,uint32_t token,uint32_t digest);
int r5_transfer_cp_receive(struct r5_transfer_cp *c,struct r5_boot_bank *b,
    const uint8_t *p,size_t n,uint8_t ack[R5_TRANSFER_ACK]) {
    uint32_t token=0,mask=0,slot=0,digest=0,seq=0;unsigned op=0,status=R5_X_BAD_PACKET;
    size_t i;
    if(!r5_transfer_is_envelope(p,n))return 0;
    if(!c||!b||!ack||overlap(c,sizeof(*c),b,sizeof(*b))||
       overlap(c,sizeof(*c),p,n)||overlap(b,sizeof(*b),p,n)||
       overlap(ack,R5_TRANSFER_ACK,c,sizeof(*c))||overlap(ack,R5_TRANSFER_ACK,b,sizeof(*b))||
       overlap(ack,R5_TRANSFER_ACK,p,n))return 1;
    if(n>=32&&n<=R5_TRANSFER_MAX) {
        token=get32(p+8);mask=get32(p+12);slot=get32(p+16);digest=get32(p+20);seq=get32(p+24);op=p[2];
        if(p[1]!=3||p[3]||!token||(mask&~4095u)||get32(p+28)!=message_crc(p,n))goto rejected;
        if(op==R5_X_BEGIN&&n==32&&!slot&&!seq) {
            const uint8_t *zero=(const uint8_t *)c;
            for(i=0;i<sizeof(*c);i++)if(zero[i]){status=R5_X_BAD_STATE;goto rejected;}
            if(r5_boot_bank_begin(b,token,mask)){status=R5_X_BAD_STATE;goto rejected;}
            c->token=token;c->mask=mask;c->payload_crc=digest;c->phase=1;status=R5_X_OK;
        } else {
            if(c->phase!=1||token!=c->token||mask!=c->mask||digest!=c->payload_crc) {status=R5_X_BAD_STATE;goto rejected;}
            if(op==R5_X_PUT&&n==R5_TRANSFER_MAX&&slot==next_slot(mask,c->last_slot)&&slot<=12&&seq==slot) {
                if(r5_boot_bank_put_compact(b,token,slot,p+32)){status=R5_X_BAD_VALUES;goto rejected;}
                c->last_slot=slot;status=R5_X_OK;
            } else if(op==R5_X_SEAL&&n==32&&!slot&&seq==13&&next_slot(mask,c->last_slot)==13&&b->received_mask==mask) {
                if(r5_transfer_bank_crc(b)!=digest){status=R5_X_BAD_DIGEST;goto rejected;}
                /* This compiler emits a native DMB for ARM and AArch64. It is
                 * a release fence, not proof of intercore ownership/ACK. */
                __atomic_thread_fence(__ATOMIC_RELEASE);
                { int sealed=seal_verified(b,token,digest);
                  if(sealed==-2){status=R5_X_NOT_READY;goto reply;}
                  if(sealed){status=R5_X_BAD_STATE;goto rejected;} }
                c->phase=2;status=R5_X_OK;
            } else goto rejected;
        }
        goto reply;
    }
rejected:
    c->phase=3;c->error=status;
reply:
    header(ack,R5_X_ACK,token,mask,slot,digest,seq);
    put32(ack+32,b->state);put32(ack+36,status);put32(ack+40,b->received_mask);
    put32(ack+28,message_crc(ack,R5_TRANSFER_ACK));return 1;
}

int r5_boot_bank_begin(struct r5_boot_bank *b,uint32_t token,uint32_t mask) {
 unsigned i;const uint8_t *p=(const uint8_t *)b;
 if(!b||!token||(mask&~4095u))return -1;
 for(i=0;i<sizeof(*b);i++)if(p[i])return -1;
 b->token=token;b->expected_mask=mask;b->state=BUILDING;return 0;
}
static int seal_verified(struct r5_boot_bank *b,uint32_t token,uint32_t digest) {
 int result;
 if(!b||b->state!=BUILDING||b->token!=token||b->received_mask!=b->expected_mask)return -1;
 extern int r5_native418_publish(struct r5_boot_bank *);
 b->reserved[0]=digest;result=r5_native418_publish(b);
 if(result)b->reserved[0]=0;
 return result;
}
int r5_boot_bank_seal(struct r5_boot_bank *b,uint32_t token) {
 return seal_verified(b,token,r5_transfer_bank_crc(b));
}
