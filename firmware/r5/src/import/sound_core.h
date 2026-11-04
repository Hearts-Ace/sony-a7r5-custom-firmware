#ifndef R5_SOUND_INTEGRITY_H
#define R5_SOUND_INTEGRITY_H
#include <stddef.h>
#include <stdint.h>
#define SS_NAME_BYTES 256u
int ss_valid_name(const char *,size_t);
int ss_sha256(const uint8_t *,size_t,uint8_t[32]);
uint32_t ss_crc32(const uint8_t *,size_t);
#endif
