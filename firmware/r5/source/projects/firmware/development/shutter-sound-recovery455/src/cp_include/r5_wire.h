/* Same shared wire/layout; the CP CRC body is linked once in resident RX. */
#define r5_wire_crc r5_wire_crc_inline_unused
#include "../import/r5_wire.h"
#undef r5_wire_crc
uint32_t r5_wire_crc(const uint8_t *,size_t);
