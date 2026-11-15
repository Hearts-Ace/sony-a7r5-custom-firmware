#ifndef R5_OD_GRID_OWNERS_H
#define R5_OD_GRID_OWNERS_H
#include "generation.h"
struct od_context;
enum { OD_GRID_FIELDS = 16 };
#define OD_GRID_MARKER 0xa0000000u
#define OD_GRID_TICKET_MAX 0x01ffffffu
_Static_assert((R5G_SERIAL_MAX << 2 | 3u) == OD_GRID_TICKET_MAX, "encoded generation width");
struct od_grid_field { uint32_t field, ticket, reserved; };
struct od_grid_owners { struct od_grid_field fields[OD_GRID_FIELDS]; };
_Static_assert(sizeof(struct od_grid_owners) == 192, "grid ownership BSS budget");

/* The native source word carries identity, never a parameter address.
 * Pool fields use the containing native task's owner. Other fields hold an
 * explicit reference in this table until native replacement or retirement. */
int od_grid_state_own(uint8_t *, struct r5g_lease *, unsigned);
int od_grid_state_stock(uint8_t *);
const struct od_context *od_grid_desc_pin(const uint8_t *, struct r5g_lease *, unsigned *);
int od_grid_field_copy(uint32_t *, const uint32_t *);
int od_grid_field_clear(uint32_t *);
void od_grid_forget_range(uintptr_t, uint32_t);
#endif
