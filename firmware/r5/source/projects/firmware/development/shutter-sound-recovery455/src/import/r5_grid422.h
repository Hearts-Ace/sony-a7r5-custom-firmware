#ifndef R5_GRID422_H
#define R5_GRID422_H
#include <stdint.h>
#include <stddef.h>
/* Append-only heap ABI. All original bank/Gamma/diagnostic/transfer offsets stay.
 * Four bytes pad the old 52348-byte allocation to an eight-byte boundary. */
#define R5_GRID422_OFFSET 52352u
#define R5_GRID422_POINTS 405u
#define R5_GRID422_CLASSES 8u
#define R5_GRID422_SLOTS 12u
#define R5_GRID422_MAGIC 0x422671adu
#define R5_GRID422_RESTORE_ENTRIES 32u
#define R5_GRID422_RESTORE_LIMIT 31u
#define R5_GRID422_RESTORE_LEVEL_CLASSES 9u /* 0, 1..7, and >=8 */
struct r5_grid422_restore_entry {
 uint32_t ready,key; /* 0 free; 1 private snapshot/build; 2 immutable ready. */
 uint8_t raw[1216];
 uint8_t work[92];
 uint32_t packed[405];
};
struct r5_grid422 {
 uint32_t ready, mask;
 uint32_t packed[R5_GRID422_SLOTS][R5_GRID422_CLASSES][R5_GRID422_POINTS];
 uint32_t restore_used,reserved;
 struct r5_grid422_restore_entry restore[R5_GRID422_RESTORE_ENTRIES];
};
#define R5_GRID422_ALLOCATION (R5_GRID422_OFFSET+sizeof(struct r5_grid422))
_Static_assert(R5_GRID422_OFFSET+offsetof(struct r5_grid422,restore_used)==207880u,"append restore header");
_Static_assert(offsetof(struct r5_grid422_restore_entry,packed)-offsetof(struct r5_grid422_restore_entry,work)==92u,"native direct destination");
_Static_assert(sizeof(struct r5_grid422_restore_entry)==2936u,"restore entry ABI");
_Static_assert(R5_GRID422_ALLOCATION==301840u,"retained heap ABI422 restore");
struct r5_boot_bank;
void r5_grid422_prepare(struct r5_boot_bank *);
void r5_grid422_controller(const uint32_t *,const uint32_t *);
const uint32_t *r5_grid422_restore(struct r5_boot_bank *,const uint8_t *,const uint8_t *);
#endif
