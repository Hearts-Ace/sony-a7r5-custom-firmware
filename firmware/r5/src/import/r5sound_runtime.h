#ifndef R5SOUND_RUNTIME_H
#define R5SOUND_RUNTIME_H
#include <stdint.h>
unsigned r5sound_volume_get(void);
unsigned r5sound_revision(void);
int r5sound_volume_blocked(void);
int r5sound_volume_enqueue(unsigned);
unsigned r5sound_count(void);
const char *r5sound_name(unsigned);
unsigned r5sound_selected(void);
int r5sound_request(unsigned);
const char *r5sound_status(void);
void r5sound_boot(void);
int r5sound_service(void); /* background loop only: true selects 10ms cadence */
/* Shared worker only. Yield at file boundaries, service filter requests, and
 * return nonzero only while the current power/session witness still holds. */
int r5sound_worker_yield(void);
void r5sound_initial(uint32_t,uint32_t);
void r5sound_completed(uint32_t);
void r5sound_media(uint32_t,uint32_t,uint32_t);
void r5sound_inbound(const uint8_t *,uint32_t);
void r5sound_power(const uint32_t *);
#endif
