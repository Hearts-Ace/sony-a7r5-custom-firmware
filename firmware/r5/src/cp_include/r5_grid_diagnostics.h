/* Same shared wire/layout; the CP CRC body is linked once in resident RX. */
#define r5_diag_crc r5_diag_crc_inline_unused
#include "../import/r5_grid_diagnostics.h"
#undef r5_diag_crc
uint32_t r5_diag_crc(const uint8_t *,size_t);
