#ifndef R5SOUND_PACKAGE_H
#define R5SOUND_PACKAGE_H
#include <stddef.h>
#include <stdint.h>

#define R5SOUND_PACKAGE_HEADER_BYTES 416u
#define R5SOUND_PACKAGE_MAX_BYTES 496096u
#define R5SOUND_F0_GUARD 64u
#define R5SOUND_STAGING_BYTES 51200u

typedef struct r5sound_package_info {
 uint32_t frames,encoded_bytes,total_bytes;
} r5sound_package_info;

/* Little-endian R5S version1: 416-byte header then ten equal F0 payloads.
 * No trailing DMA guard is stored. Payload steps are numbered1..10.
 * All functions return0 on success, -1 malformed input, -2 SHA failure.
 * Header accepts at least416 readable bytes and an exact external file size;
 * audio accepts exactly one payload. Neither performs DSP or allocates.
 * Input buffers must stay immutable for the duration of each call.
 * Output info is written only after complete success. */
int r5sound_package_header(const uint8_t *,size_t,size_t,r5sound_package_info *);
int r5sound_package_audio(const uint8_t *,const r5sound_package_info *,
 unsigned,const uint8_t *,size_t);
int r5sound_package_validate(const uint8_t *,size_t,r5sound_package_info *);
#endif
