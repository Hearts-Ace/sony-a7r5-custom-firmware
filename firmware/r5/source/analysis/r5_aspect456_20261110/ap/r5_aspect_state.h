#ifndef R5_ASPECT_STATE_H
#define R5_ASPECT_STATE_H
#include <stdint.h>
#define R5_ASPECT_ALIAS_FIRST 0x1660u
#define R5_ASPECT_COUNT 4u
#define R5_ASPECT_TEXT_FIRST 0x0200ab4cu
#define R5_ASPECT_ICON_FIRST 0x02001e90u
#define R5_ASPECT_NATIVE_ALIAS 126u
#define R5_ASPECT_LEAF 33u
/* Epoch is advanced even on native/canceled selections. Readers must retain
 * the complete token if results are published across page lifecycle changes. */
extern uint32_t r5_aspect_selection;
uint32_t r5_aspect_token(void);
uint32_t r5_aspect_publish(uint32_t choice);
uint32_t r5_aspect_effective(uint32_t native_choice, uint32_t token);
uint32_t r5_aspect_freeze(uint32_t native_choice);
void r5_aspect_packet(void *packet, uint32_t frozen_choice);
uint32_t r5_aspect_native_alias(uint32_t alias);
uint32_t r5_aspect_choice_from_alias(uint32_t alias);
/* Serialized-record helpers only. IO/lifecycle binding remains separate. */
void r5_aspect_make_record(uint32_t choice, uint32_t record[4]);
int r5_aspect_restore_record(const void *data, uint32_t length,
                             uint32_t unchanged_token);
void r5_aspect_restore_once(void);
int r5_aspect_save(uint32_t choice);
extern int32_t r5_aspect_persist_status;
void r5_aspect_reset_for_test(void);
#endif
