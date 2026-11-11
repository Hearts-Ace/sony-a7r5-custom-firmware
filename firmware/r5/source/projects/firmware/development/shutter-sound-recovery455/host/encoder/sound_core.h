#ifndef R5_SOUND_PARSE_H
#define R5_SOUND_PARSE_H
#include <stddef.h>
#include <stdint.h>
#define SS_MAX_WAV_BYTES (1024u*1024u)
#define SS_MAX_SECONDS 2u
#define SS_NAME_BYTES 256u
enum {SS_OK=0,SS_INVALID=1,SS_WAV_INVALID=2,SS_LIMIT=3};
typedef struct {uint32_t channels,sample_rate,bits_per_sample,block_align,data_offset,data_bytes,frames;} ss_format;
int ss_valid_name(const char *,size_t);
int ss_parse_wav(const uint8_t *,size_t,ss_format *);
int ss_decode_q31(const uint8_t *,size_t,const ss_format *,uint32_t,uint32_t,int32_t *);
int ss_decode_frames_q31(const uint8_t *,size_t,uint32_t,uint32_t,int32_t *,size_t,ss_format *);
int ss_sha256(const uint8_t *,size_t,uint8_t[32]);
uint32_t ss_crc32(const uint8_t *,size_t);
#endif
