#include "convert.h"
#include "sound_core.h"
#include "kernel_q24.h"

/* Supply only the C primitives used by the unchanged ss_parse_wav. Linker GC
 * removes unrelated core routines. Neither primitive may recurse via builtins. */
#ifndef R5SS_SHARED_MEMSET
void *memset(void *p, int v, size_t n) {
    uint8_t *s=p; for(size_t i=0;i<n;i++)s[i]=(uint8_t)v; return p;
}
#endif
int memcmp(const void *a,const void *b,size_t n) {
    const uint8_t *x=a,*y=b;
    for(size_t i=0;i<n;i++)if(x[i]!=y[i])return (int)x[i]-(int)y[i];
    return 0;
}

enum { Q24=16777216, KERNEL_RADIUS=12, MAX_TAPS=195 };
typedef struct {
    const uint8_t *data;
    ss_format f;
    uint32_t half, scale, last_phase;
    int32_t weights[MAX_TAPS];
    int64_t sum;
} fir_state;

static int span(uintptr_t p, size_t n) { return p && n && p<=(uintptr_t)-1-n; }
static int overlap(uintptr_t a,size_t na,uintptr_t b,size_t nb) {
    return a<b+nb && b<a+na;
}
static int32_t decode(const uint8_t *p,uint32_t bits) {
    uint32_t u=p[0];
    if(bits==8)return ((int32_t)u-128)*256;
    u|=(uint32_t)p[1]<<8;
    if(bits==16)return u>=32768?(int32_t)u-65536:(int32_t)u;
    u|=(uint32_t)p[2]<<16;
    if(bits==24)return u>=8388608?((int32_t)u-16777216)/256:(int32_t)u/256;
    u|=(uint32_t)p[3]<<24;
    /* Conversion from signed full-width input is explicit and avoids
     * implementation-defined uint32->int32 and negative right shifts. */
    int64_t s=u>=0x80000000u?(int64_t)u-4294967296LL:(int64_t)u;
    return (int32_t)(s/65536);
}
static int32_t mono(const fir_state *s,int32_t frame) {
    if(frame<0)frame=0;
    if((uint32_t)frame>=s->f.frames)frame=(int32_t)s->f.frames-1;
    const uint8_t *p=s->data+(uint32_t)frame*s->f.block_align;
    int32_t a=decode(p,s->f.bits_per_sample);
    return s->f.channels==1?a:(a+decode(p+s->f.bits_per_sample/8,s->f.bits_per_sample))/2;
}
static int32_t coefficient(uint32_t distance) {
    uint32_t k=distance>>18, f=distance&262143u;
    if(k>=768)return 0;
    int32_t a=csnd_kernel_q24[k],b=csnd_kernel_q24[k+1];
    return a+(int32_t)(((int64_t)(b-a)*f)/262144);
}
static void prepare(fir_state *s,uint32_t phase) {
    if(phase==s->last_phase)return;
    s->last_phase=phase;s->sum=0;
    int64_t x=-(int64_t)s->half*Q24-(int64_t)phase*Q24/24000;
    for(uint32_t i=0;i<=2*s->half;i++,x+=Q24) {
        uint64_t absolute=(uint64_t)(x<0?-x:x);
        uint32_t distance=(uint32_t)((absolute*s->scale)>>24);
        int32_t w=coefficient(distance);s->weights[i]=w;s->sum+=w;
    }
}
static int32_t sample(fir_state *s,uint32_t center,uint32_t phase) {
    prepare(s,phase);
    int64_t acc=0;
    for(uint32_t i=0;i<=2*s->half;i++)
        acc+=(int64_t)mono(s,(int32_t)center+(int32_t)i-(int32_t)s->half)*s->weights[i];
    return (int32_t)(acc/s->sum);
}
static void advance(const ss_format *f,uint32_t *center,uint32_t *phase) {
    uint32_t p=*phase+f->sample_rate;
    *center+=p/24000;*phase=p%24000;
}
static void block(const int16_t *pcm,uint32_t count,uint8_t *out) {
    uint32_t peak=0,shift=0;
    for(uint32_t i=0;i<count;i++) {
        int v=pcm[i];uint32_t a=(uint32_t)(v<0?-v:v);if(a>peak)peak=a;
    }
    while(shift<7 && peak>(127u<<shift))shift++;
    out[0]=(uint8_t)shift;
    for(uint32_t i=0;i<31;i++) {
        int v=i<count?pcm[i]:0;
        uint32_t a=(uint32_t)(v<0?-v:v);
        uint32_t q=(a+(shift?(1u<<(shift-1)):0))>>shift;
        if(v>=0 && q>127)q=127;if(v<0 && q>128)q=128;
        out[i+1]=(uint8_t)(v<0?-(int)q:(int)q);
    }
}

int csnd_pcm_f0_volume(const uint8_t *pcm_input,uint32_t pcm_bytes,const ss_format *format,
                uint8_t *staging,uint32_t capacity,csnd_convert_info *info,uint32_t volume_step) {
    if(volume_step<1 || volume_step>10)return CSND_CONVERT_INVALID;
    uintptr_t a=(uintptr_t)pcm_input,b=(uintptr_t)staging,c=(uintptr_t)info,d=(uintptr_t)format;
    if(!span(a,pcm_bytes)||!span(b,capacity)||!span(c,sizeof(*info))||!span(d,sizeof(*format)))return CSND_CONVERT_INVALID;
    if(capacity>CSND_MAX_STAGING_BYTES)return CSND_CONVERT_CAPACITY;
    if(overlap(a,pcm_bytes,b,capacity)||overlap(a,pcm_bytes,c,sizeof(*info))||
       overlap(b,capacity,c,sizeof(*info))||overlap(d,sizeof(*format),a,pcm_bytes)||
       overlap(d,sizeof(*format),b,capacity)||overlap(d,sizeof(*format),c,sizeof(*info)))return CSND_CONVERT_OVERLAP;
    fir_state s;s.f=*format;
    if(pcm_bytes>SS_MAX_WAV_BYTES)return CSND_CONVERT_LIMIT;
    if((s.f.channels!=1 && s.f.channels!=2)||s.f.sample_rate<8000||s.f.sample_rate>192000||
       (s.f.bits_per_sample!=8 && s.f.bits_per_sample!=16 && s.f.bits_per_sample!=24 && s.f.bits_per_sample!=32)||
       s.f.block_align!=s.f.channels*(s.f.bits_per_sample/8)||s.f.data_offset||
       s.f.data_bytes!=pcm_bytes||pcm_bytes%s.f.block_align||s.f.frames!=pcm_bytes/s.f.block_align)
        return CSND_CONVERT_WAV;
    if(!s.f.frames || s.f.frames>s.f.sample_rate*SS_MAX_SECONDS)return CSND_CONVERT_LIMIT;
    uint32_t frames=(uint32_t)(((uint64_t)s.f.frames*24000+s.f.sample_rate-1)/s.f.sample_rate);
    uint32_t blocks=(frames+30)/31,bytes=blocks*32;
    if(!frames||frames>CSND_MAX_PCM_FRAMES)return CSND_CONVERT_LIMIT;
    if(capacity<CSND_F0_GUARD||bytes>capacity-CSND_F0_GUARD)return CSND_CONVERT_CAPACITY;
    csnd_kernel_prepare();
    s.data=pcm_input;
    s.scale=s.f.sample_rate>24000?(uint32_t)(((uint64_t)24000*Q24)/s.f.sample_rate):Q24;
    s.half=s.f.sample_rate>24000?(KERNEL_RADIUS*s.f.sample_rate+23999)/24000:KERNEL_RADIUS;
    s.last_phase=0xffffffffu;
    uint32_t center=0,phase=0,peak=0;
    /* Two passes avoid a full-length PCM allocation. With immutable input
     * and valid caller buffers all remaining operations are total/bounded. */
    for(uint32_t i=0;i<frames;i++) {
        int32_t v=sample(&s,center,phase);uint32_t p=(uint32_t)(v<0?-v:v);
        if(p>peak)peak=p;advance(&s.f,&center,&phase);
    }
    uint32_t denominator=peak>32768?peak:32768;
    center=0;phase=0;int16_t pcm[31];uint32_t at=0;
    for(uint32_t i=0;i<frames;i++) {
        int32_t v=sample(&s,center,phase);
        /* User scale:50percent is the636 gain7864/32768;100percent doubles
         * this amplitude. Whole-clip overshoot control bounds PCM to15728,
         * below16-bit saturation; f0 exponent7 is present in stock resources. */
        pcm[at++]=(int16_t)((((int64_t)v*7864)/denominator)*(int64_t)volume_step/5);
        advance(&s.f,&center,&phase);
        if(at==31 || i+1==frames) {block(pcm,at,staging+(i/31)*32);at=0;}
    }
    for(uint32_t i=bytes;i<capacity;i++)staging[i]=0;
    csnd_convert_info r={1,s.f.sample_rate,s.f.frames,frames,bytes,blocks*31-frames,peak,denominator};
    *info=r;return CSND_CONVERT_OK;
}

int csnd_wav_to_f0(const uint8_t *wav,uint32_t wav_bytes,
                   uint8_t *staging,uint32_t capacity,csnd_convert_info *info) {
    uintptr_t a=(uintptr_t)wav,b=(uintptr_t)staging,c=(uintptr_t)info;
    if(!span(a,wav_bytes)||!span(b,capacity)||!span(c,sizeof(*info)))return CSND_CONVERT_INVALID;
    if(overlap(a,wav_bytes,b,capacity)||overlap(a,wav_bytes,c,sizeof(*info))||
       overlap(b,capacity,c,sizeof(*info)))return CSND_CONVERT_OVERLAP;
    ss_format f;int status=ss_parse_wav(wav,wav_bytes,&f);
    if(status!=SS_OK)return status==SS_LIMIT?CSND_CONVERT_LIMIT:CSND_CONVERT_WAV;
    const uint8_t *pcm=wav+f.data_offset;f.data_offset=0;
    return csnd_pcm_f0(pcm,f.data_bytes,&f,staging,capacity,info);
}

int csnd_pcm_f0(const uint8_t *p,uint32_t n,const ss_format *f,uint8_t *d,uint32_t cap,csnd_convert_info *i) {
 return csnd_pcm_f0_volume(p,n,f,d,cap,i,5);
}
