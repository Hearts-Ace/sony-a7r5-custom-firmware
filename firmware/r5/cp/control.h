#ifndef OD_CONTROL_H
#define OD_CONTROL_H
#include "submit.h"
#include "owners.h"
#include "grid_owners.h"
/* Reserved by the stock-derived CP mapper; native boot clear includes this
 * exact region. Source-owner arrays are added only with verified boundaries. */
struct od_state {struct r5s_state submit; uint32_t accept_pending; struct od_owners owners; struct od_grid_owners grid;};
#define OD_STATE ((struct od_state *)(uintptr_t)0x1a39698u)
_Static_assert(sizeof(struct od_state)<=2408,"reserved BSS gap");
unsigned od_collect(void);
unsigned od_native_dispatch(const uint8_t *,uint32_t);
void od_receive_complete(void);
#endif
