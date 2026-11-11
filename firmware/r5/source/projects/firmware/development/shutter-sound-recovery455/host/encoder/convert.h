#ifndef CSND_WAV_CONVERSION_H
#define CSND_WAV_CONVERSION_H
#include <stdint.h>
#include <stddef.h>
#include "sound_core.h"

enum { CSND_CONVERT_OK=0, CSND_CONVERT_INVALID=-1,
       CSND_CONVERT_CAPACITY=-2, CSND_CONVERT_OVERLAP=-3,
       CSND_CONVERT_WAV=-4, CSND_CONVERT_LIMIT=-5 };
enum { CSND_PCM_RATE=24000, CSND_MAX_PCM_FRAMES=48000,
       CSND_MAX_F0_BYTES=49568, CSND_F0_GUARD=64,
       CSND_MAX_STAGING_BYTES=51200 };
typedef struct {
    uint32_t schema, source_rate, source_frames, pcm_frames;
    uint32_t encoded_bytes, padded_frames, source_peak, gain_denominator;
} csnd_convert_info;

/* Pure CPU conversion. The WAV must remain immutable throughout this call.
 * Destination is caller-owned UNREGISTERED staging, not active audio memory.
 * Input, entire destination capacity and info must be pairwise disjoint.
 * Parse/size/pointer errors leave destination AND info untouched.
 * No allocations, waits, camera APIs, floating point or libm are used. The
 * shared exact kernel expands once; all conversions use the one audio worker.
 * Up to 1 MiB / 2 s PCM WAV, 8..192 kHz, 8/16/24/32-bit, mono/stereo;
 * exactly the existing ss_parse_wav acceptance contract is reused.
 * Output is the acoustically inferred 24k mono f0-only format0 candidate;
 * format1 and hardware acceptance are not claimed by this component.
 */
int csnd_wav_to_f0(const uint8_t *wav, uint32_t wav_bytes,
                   uint8_t *staging, uint32_t capacity,
                   csnd_convert_info *info);
/* The existing AP copy API returns a detached PCM copy plus ss_format with
 * data_offset=0 and data_bytes=pcm_bytes. This entry avoids copying/reparsing
 * the RIFF container while preserving the same conversion and format limits.
 * Format is copied locally before work; it must also be disjoint from inputs,
 * staging and result. All pointers must remain valid throughout the call. */
int csnd_pcm_f0(const uint8_t *pcm, uint32_t pcm_bytes, const ss_format *format,
                uint8_t *staging, uint32_t capacity, csnd_convert_info *info);
int csnd_pcm_f0_volume(const uint8_t *,uint32_t,const ss_format *,uint8_t *,uint32_t,csnd_convert_info *,uint32_t);
#endif
