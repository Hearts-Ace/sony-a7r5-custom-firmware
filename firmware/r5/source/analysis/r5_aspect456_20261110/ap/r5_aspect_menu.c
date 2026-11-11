/* Candidate native-menu integration. Caller must install all declared hooks,
 * including row registry/normalization/parent and descriptor remaps. No IO. */
#include "r5_aspect_state.h"
extern const unsigned char r5_native_aspect_rows[4][0x80];
extern uint32_t r5_native_aspect_get(void);
extern void r5_native_aspect_set(uint32_t);
extern void r5_native_aspect_commit(uint32_t);
extern void r5_aspect_native_apply(void *,uint32_t);
extern uint32_t r5_aspect_native_size_alias(uint32_t);
extern void r5_aspect_original_rows_register(void *,const void *,const void *);
extern uint32_t r5_aspect_original_row_normalize(void *,uint32_t);
extern uint32_t r5_aspect_original_row_available(void *,uint32_t);
extern uint32_t r5_aspect_original_row_available_direct(void *,uint32_t);
extern uint32_t r5_aspect_original_row_parent(void *,uint32_t);
extern void r5_native_row_insert(void *,const void *,const void *);
unsigned char r5_aspect_menu_rows[8][0x80] __attribute__((aligned(8)));
struct row_pair {uint64_t alias;const void *row;};
static struct row_pair extra_rows[4];
static uint32_t initialized;
/* Display order is independent of stable native/private choice IDs. */
static const uint32_t display_order[8]={0,4,1,6,2,7,5,3};
/* MENU small badges use row+0x0c; Fn images stay at +0x20/+0x24. */
static const uint32_t menu_badges[4]={0x02001e80,0x02001e81,0x02001e82,0x02001e83};
static void put32(unsigned char *p,uint32_t at,uint32_t value) {
    for (unsigned i=0;i<4;i++)p[at+i]=(unsigned char)(value>>(8*i));
}
void r5_aspect_menu_init(void) {
    if (initialized) return;
    for (unsigned position=0;position<8;position++) {
        uint32_t n=display_order[position];
        unsigned char *p=r5_aspect_menu_rows[position];
        const unsigned char *s=r5_native_aspect_rows[n<4?n:0];
        for (unsigned i=0;i<0x80;i++)p[i]=s[i];
        if (n<4) continue;
        uint32_t k=n-4,alias=R5_ASPECT_ALIAS_FIRST+k;
        put32(p,0,alias);put32(p,4,alias);
        put32(p,8,R5_ASPECT_TEXT_FIRST+k);
        put32(p,0x0c,menu_badges[k]);
        put32(p,0x20,R5_ASPECT_ICON_FIRST+k);
        put32(p,0x24,R5_ASPECT_ICON_FIRST+k+4);
        put32(p,0x28,~0u);put32(p,0x2c,~0u);put32(p,0x34,n);
        extra_rows[k]=(struct row_pair){alias,p};
    }
    initialized=1;
}
void r5_aspect_rows_register_extra(void *m) {
    r5_aspect_menu_init();r5_native_row_insert(m,extra_rows,extra_rows+4);
}
uint32_t r5_aspect_menu_get(void) {
    r5_aspect_restore_once();
    return r5_aspect_effective(r5_native_aspect_get(),r5_aspect_token());
}
void r5_aspect_menu_set(uint32_t id) {
    if (id>7u) return;
    r5_aspect_publish(id);r5_native_aspect_set(id>=4u?0u:id);
}
void r5_aspect_menu_commit(uint32_t alias) {
    uint32_t id=r5_aspect_choice_from_alias(alias);
    if (id==~0u) return;
    r5_aspect_publish(id);r5_native_aspect_commit(r5_aspect_native_alias(alias));
    (void)r5_aspect_save(id>=4u?id:0u);
}
/* Native generic apply bypasses descriptor +80 and hands row+34 directly to
 * the settings broker. Normalize this independent consumer as well. */
void r5_aspect_apply_hook(void *self,uint32_t alias) {
    uint32_t id=r5_aspect_choice_from_alias(alias);
    if (id!=~0u)r5_aspect_publish(id);
    r5_aspect_native_apply(self,r5_aspect_native_alias(alias));
}
uint32_t r5_aspect_size_alias_hook(uint32_t alias) {
    return r5_aspect_native_size_alias(r5_aspect_native_alias(alias));
}
void r5_aspect_rows_register(void *m,const void *begin,const void *end) {
    r5_aspect_original_rows_register(m,begin,end);
    r5_aspect_rows_register_extra(m);
}
uint32_t r5_aspect_row_normalize(void *self,uint32_t alias) {
    return alias-R5_ASPECT_ALIAS_FIRST<4u?alias:
           r5_aspect_original_row_normalize(self,alias);
}
uint32_t r5_aspect_row_available(void *self,uint32_t alias) {
    return r5_aspect_original_row_available(self,r5_aspect_native_alias(alias));
}
uint32_t r5_aspect_row_available_direct(void *self,uint32_t alias) {
    return r5_aspect_original_row_available_direct(self,r5_aspect_native_alias(alias));
}
uint32_t r5_aspect_row_parent(void *self,uint32_t alias) {
    return alias-R5_ASPECT_ALIAS_FIRST<4u?R5_ASPECT_LEAF:
           r5_aspect_original_row_parent(self,alias);
}
