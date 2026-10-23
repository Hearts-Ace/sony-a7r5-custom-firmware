#ifndef R5_GRID422_H
#define R5_GRID422_H
#include <stdint.h>
/* Append-only heap ABI. All original bank/Gamma/diagnostic/transfer offsets stay.
 * Four bytes pad the old 52348-byte allocation to an eight-byte boundary. */
#define R5_GRID422_OFFSET 52352u
#define R5_GRID422_POINTS 405u
#define R5_GRID422_CLASSES 8u
#define R5_GRID422_SLOTS 12u
#define R5_GRID422_MAGIC 0x422671adu
struct r5_grid422 {
 uint32_t ready, mask;
 uint32_t packed[R5_GRID422_SLOTS][R5_GRID422_CLASSES][R5_GRID422_POINTS];
};
#define R5_GRID422_ALLOCATION (R5_GRID422_OFFSET+sizeof(struct r5_grid422))
_Static_assert(R5_GRID422_ALLOCATION==207880u,"retained heap ABI422");
struct r5_boot_bank;
void r5_grid422_prepare(struct r5_boot_bank *);
void r5_grid422_controller(const uint32_t *,const uint32_t *);
#endif
