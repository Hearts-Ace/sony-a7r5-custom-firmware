/* R5 candidate aspect state. No IO, native ABI calls, or camera operations.
 * Private IDs 4..7 are never written to the original enum or settings file. */
#include "r5_aspect_state.h"
uint32_t r5_aspect_selection;
static uint32_t valid(uint32_t choice) { return choice-4u < 4u; }
static uint32_t choice(uint32_t token) {
    uint32_t id=token&7u;
    return (token&8u) && valid(id) ? id : 0;
}
uint32_t r5_aspect_token(void) {
    return __atomic_load_n(&r5_aspect_selection,__ATOMIC_ACQUIRE);
}
uint32_t r5_aspect_publish(uint32_t id) {
    uint32_t old=r5_aspect_token(),next;
    do {
        next=((old+16u)&~15u) | (valid(id)?8u|id:0u);
    } while (!__atomic_compare_exchange_n(&r5_aspect_selection,&old,next,0,
                   __ATOMIC_RELEASE,__ATOMIC_ACQUIRE));
    return next;
}
uint32_t r5_aspect_effective(uint32_t native_choice,uint32_t token) {
    uint32_t id=choice(token);
    return native_choice==0 && id ? id : native_choice;
}
uint32_t r5_aspect_freeze(uint32_t native_choice) {
    return native_choice==0 ? choice(r5_aspect_token()) : 0;
}
void r5_aspect_packet(void *packet,uint32_t frozen_choice) {
    if (packet && valid(frozen_choice))
        ((uint8_t *)packet)[8]=(uint8_t)(frozen_choice+1u);
}
uint32_t r5_aspect_native_alias(uint32_t alias) {
    return alias-R5_ASPECT_ALIAS_FIRST<4u ? R5_ASPECT_NATIVE_ALIAS : alias;
}
uint32_t r5_aspect_choice_from_alias(uint32_t alias) {
    if (alias-R5_ASPECT_ALIAS_FIRST<4u) return alias-R5_ASPECT_ALIAS_FIRST+4u;
    if (alias-126u<4u) return alias-126u;
    return ~0u;
}
void r5_aspect_make_record(uint32_t id,uint32_t record[4]) {
    if (!valid(id)) id=0;
    record[0]=0x32505243u;record[1]=2;record[2]=id;record[3]=~id;
}
int r5_aspect_restore_record(const void *data,uint32_t length,uint32_t expected) {
    uint32_t words[4];const uint8_t *p=data;
    if (!data || length!=16) return 0;
    for (unsigned n=0;n<4;n++)
        words[n]=(uint32_t)p[4*n]|(uint32_t)p[4*n+1]<<8|
                 (uint32_t)p[4*n+2]<<16|(uint32_t)p[4*n+3]<<24;
    if (words[0]!=0x32505243u || words[1]!=2 ||
        (!valid(words[2]) && words[2]!=0) || words[3]!=~words[2]) return 0;
    uint32_t next=((expected+16u)&~15u) | (words[2]?8u|words[2]:0u);
    return __atomic_compare_exchange_n(&r5_aspect_selection,&expected,next,0,
                 __ATOMIC_RELEASE,__ATOMIC_ACQUIRE);
}
void r5_aspect_reset_for_test(void) {
    __atomic_store_n(&r5_aspect_selection,0,__ATOMIC_RELEASE);
}
