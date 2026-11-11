/* Fn MENU rollback: pair only the native key52b cache, never replay old epochs.
 * Native capture/restore and event dispatch are retained. No added file path. */
#include "r5_aspect_state.h"
extern uintptr_t r5_aspect_original_capture(void);
extern uintptr_t r5_aspect_original_restore(void);
extern const volatile uint32_t r5_native_aspect_saved;
extern uint32_t r5_native_restore_alias(void *,uint32_t);
extern uint32_t r5_native_aspect_get(void);
extern void r5_native_aspect_set(uint32_t);
extern void r5_native_aspect_commit(uint32_t);
extern uint32_t r5_aspect_menu_get(void);
extern void r5_aspect_menu_commit(uint32_t);
/* Retained like native cache; outer list removal does not consume this word. */
uint32_t r5_aspect_saved_selection;
static uint32_t next(uint32_t token,uint32_t id) {
    return ((token+16u)&~15u) | (id-4u<4u?8u|id:0u);
}
uintptr_t r5_aspect_capture_value(void) {
    __atomic_store_n(&r5_aspect_saved_selection,0,__ATOMIC_RELEASE);
    /* Complete lazy file restore before freezing this capture's epoch. */
    r5_aspect_restore_once();
    uint32_t token=r5_aspect_token(),selected=r5_aspect_menu_get();
    uintptr_t result=r5_aspect_original_capture();
    /* A concurrent publication makes this capture unusable, not a stale ID. */
    if (r5_aspect_token()==token) {
        uint32_t id=r5_native_aspect_saved==0 && selected-4u<4u?selected:0u;
        __atomic_store_n(&r5_aspect_saved_selection,0x100u|id,__ATOMIC_RELEASE);
    }
    return result;
}
uintptr_t r5_aspect_restore_value(void) {
    uint32_t expected=r5_aspect_token();
    uintptr_t result=r5_aspect_original_restore();
    uint32_t saved=__atomic_load_n(&r5_aspect_saved_selection,__ATOMIC_ACQUIRE);
    if (saved&0x100u) {
        uint32_t desired=next(expected,saved&7u);
        /* Do not overwrite a newer publication during native restore. */
        __atomic_compare_exchange_n(&r5_aspect_selection,&expected,desired,0,
                                    __ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);
    }
    return result;
}
uint64_t r5_aspect_restore_alias(void *self,uint32_t menu) {
    uint32_t token=r5_aspect_token();
    uint32_t alias=r5_native_restore_alias(self,menu);
    /* X0's high half survives MOV W21,W0 + LDR X1 until the patched BL.
     * Capture before the getter so a publication inside it also fails CAS. */
    return (menu==R5_ASPECT_LEAF?(uint64_t)token<<32:0u)|alias;
}
void r5_aspect_restore_commit(uint64_t packed,void (*callback)(uint32_t)) {
    uint32_t alias=(uint32_t)packed;
    if (callback!=r5_aspect_menu_commit) { callback(alias);return; }
    uint32_t id=r5_aspect_choice_from_alias(alias);
    if(id==~0u)return;
    uint32_t expected=packed>>32,desired=next(expected,id);
    /* Protect native aliases too: stale native0 must not erase newer custom. */
    if (!__atomic_compare_exchange_n(&r5_aspect_selection,&expected,desired,0,
                                     __ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))return;
    r5_native_aspect_set(id>=4u?0u:id);
    r5_native_aspect_commit(r5_aspect_native_alias(alias));
    /* No second unconditional publish; retain existing persistence contract. */
    (void)r5_aspect_save(id>=4u?id:0u);
}
