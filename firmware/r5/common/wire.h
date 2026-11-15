#ifndef R5_OWNER_WIRE_H
#define R5_OWNER_WIRE_H
#include <stdint.h>
#define R5S_MAGIC 0x46303536u
#define R5S_PREPARE 1u
#define R5S_ABORT 2u
#define R5S_COLLECT 3u
#define R5S_ACCEPT 4u
#define R5S_COOKIE_MAX 0x007fffffu
#define R5S_TAG 0x80000000u
#define R5S_QUEUE_AP 0x80020002u
static inline uint32_t r5s_color_word(uint8_t color, uint32_t cookie)
{
    return R5S_TAG | (cookie << 8) | color;
}
#endif
