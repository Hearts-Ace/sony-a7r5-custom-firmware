/* Host-only driver. The encoder and parser beside this file are unchanged
 * frozen menu441 source. All intermediate FIR/PCM and guards stay on host. */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "sound_core.h"
#include "convert.h"
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

static uint8_t wav[SS_MAX_WAV_BYTES + 1u];
static uint8_t staging[CSND_MAX_STAGING_BYTES];

static int put32(uint32_t v) {
    uint8_t p[4]={(uint8_t)v,(uint8_t)(v>>8),(uint8_t)(v>>16),(uint8_t)(v>>24)};
    return fwrite(p,1,4,stdout)==4 ? 0 : -1;
}

int main(void) {
#ifdef _WIN32
    if(_setmode(_fileno(stdin),_O_BINARY)<0 || _setmode(_fileno(stdout),_O_BINARY)<0) return 7;
#endif
    size_t length=fread(wav,1,sizeof(wav),stdin);
    if(ferror(stdin)) { fputs("input read failed\n",stderr); return 2; }
    ss_format f;
    int parsed=ss_parse_wav(wav,length,&f);
    if(parsed!=SS_OK) { fprintf(stderr,"WAV rejected (ss_parse_wav=%d)\n",parsed); return 3; }
    uint32_t original_offset=f.data_offset;
    const uint8_t *pcm=wav+original_offset;
    f.data_offset=0;
    csnd_convert_info first={0};
    for(uint32_t step=1;step<=10;step++) {
        csnd_convert_info info;
        int status=csnd_pcm_f0_volume(pcm,f.data_bytes,&f,staging,sizeof(staging),&info,step);
        if(status!=CSND_CONVERT_OK) { fprintf(stderr,"conversion rejected (step=%u,status=%d)\n",step,status); return 4; }
        if(step==1) {
            first=info;
            if(fwrite("R5ENC01\0",1,8,stdout)!=8) return 5;
            const uint32_t fields[12]={f.channels,f.sample_rate,f.bits_per_sample,f.block_align,
                original_offset,f.data_bytes,f.frames,info.pcm_frames,info.encoded_bytes,
                info.padded_frames,info.source_peak,info.gain_denominator};
            for(unsigned i=0;i<12;i++) if(put32(fields[i])) return 5;
        } else if(memcmp(&first,&info,sizeof(info))) { fputs("encoder metadata changed between steps\n",stderr); return 6; }
        for(uint32_t i=info.encoded_bytes;i<sizeof(staging);i++)
            if(staging[i]) { fputs("encoder guard is not zero\n",stderr); return 6; }
        /* Store encoded bytes only. The camera adds its own 64-byte guard. */
        if(fwrite(staging,1,info.encoded_bytes,stdout)!=info.encoded_bytes) return 5;
    }
    return fflush(stdout)==0 ? 0 : 5;
}
