#ifndef R5_CUSTOM_FILTER423_H
#define R5_CUSTOM_FILTER423_H
#include <stdint.h>
#include <stddef.h>
#include "native_gamma.h"
#define R5_FILTER423_MAGIC 0x423f17e1u
#define R5_FILTER423_ACTIVE_VA 0x1a39458u
#define R5_FILTER423_CONTROL_VA 0x1a3945cu
#define R5_FILTER423_OFF_TABLE 48796u
#define R5_FILTER423_VIEWS 50896u
#define R5_FILTER423_EXTRA_GAMMA 301840u
#define R5_FILTER423_ALLOCATION 522152u
#define R5_FILTER423_SELECT_CLASS 0xeau
#define R5_FILTER423_SELECT_MAGIC 0x53463552u
#define R5_FILTER423_SELECT_BYTES 32u
enum r5_filter423_status {R5_F_OK=0,R5_F_BAD_PACKET=1,R5_F_NOT_READY=2,
 R5_F_STALE=3,R5_F_BAD_SELECTION=4,R5_F_BAD_BANK=5};
struct r5_filter423_view {
 uint32_t ready,bank,selected,table,route,normal_route;
};
struct r5_boot_bank;
static inline struct r5_native_gamma418 *r5_filter423_gamma(struct r5_boot_bank *b,unsigned n){
 return (void *)((uintptr_t)b+(n?R5_FILTER423_EXTRA_GAMMA+(n-1u)*sizeof(struct r5_native_gamma418):28768u));
}
static inline struct r5_filter423_view *r5_filter423_view(struct r5_boot_bank *b,unsigned n){
 return (void *)((uintptr_t)b+R5_FILTER423_VIEWS+n*sizeof(struct r5_filter423_view));
}
static inline const struct r5_filter423_view *r5_filter423_acquire(void){
 const struct r5_filter423_view *v=(const void *)(uintptr_t)__atomic_load_n((const uint32_t *)(uintptr_t)R5_FILTER423_ACTIVE_VA,__ATOMIC_ACQUIRE);
 return v&&v->ready==R5_FILTER423_MAGIC?v:0;
}
void r5_filter423_accept(uint32_t alias,unsigned new_generation);
int r5_filter423_select(const uint8_t *,uint32_t,uint8_t [32]);
_Static_assert(R5_FILTER423_OFF_TABLE+75u*7u*4u==R5_FILTER423_VIEWS,"off table adjacency");
_Static_assert(R5_FILTER423_VIEWS+13u*sizeof(struct r5_filter423_view)<=51780u,"old ready/diag offsets preserved");
_Static_assert(R5_FILTER423_EXTRA_GAMMA+11u*sizeof(struct r5_native_gamma418)==R5_FILTER423_ALLOCATION-4u,"extra Gamma ABI");
#endif
