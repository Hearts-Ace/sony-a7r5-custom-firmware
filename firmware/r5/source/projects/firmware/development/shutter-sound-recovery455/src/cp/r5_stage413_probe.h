#ifndef R5_STAGE413_PROBE_H
#define R5_STAGE413_PROBE_H
#include <stdint.h>

/* Wire format: byte fields followed by little-endian u32 fields. This is a
 * bank-capacity probe, never configuration acceptance or activation.
 * CRC is IEEE CRC32 of exactly bytes0..27, excluding the final CRC word.
 * config_hash is opaque to CP; AP supplies its current canonical-set CRC.
 * Request words20/24 are zero. ACK word20=28768 or0,word24=0x413.
 */
#define R5_STAGE413_BYTES 32u
#define R5_STAGE413_CLASS 0xe8u
#define R5_STAGE413_VERSION 1u
#define R5_STAGE413_REQUEST 1u
#define R5_STAGE413_ACK 0x81u
#define R5_STAGE413_MAGIC 0x32503552u /* ASCII R5P1 */
#define R5_STAGE413_CP_BUILD 0x420u
#define R5_STAGE413_AP_QUEUE 0x80020002u
#define R5_STAGE413_CP_QUEUE 0x90030001u
#define R5_STAGE413_BANK_BYTES 28768u

enum r5_stage413_offsets {
 R5_STAGE413_O_CLASS=0, R5_STAGE413_O_VERSION=1,
 R5_STAGE413_O_OPERATION=2, R5_STAGE413_O_LENGTH=3,
 R5_STAGE413_O_MAGIC=4, R5_STAGE413_O_TOKEN=8,
 R5_STAGE413_O_CONFIG_HASH=12, R5_STAGE413_O_MASK=16,
 R5_STAGE413_O_RESERVED=20, R5_STAGE413_O_BUILD=24,
 R5_STAGE413_O_CRC=28
};
#endif
