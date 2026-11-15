#ifndef OD_OWNERS_H
#define OD_OWNERS_H
#include "generation.h"
struct od_context;
enum { OD_TASKS=490, OD_OWNER_FIELDS=16 };
/* Native pool objects own their immutable capture generation. Other native
 * fields have explicit identities: source color, tone output, pending copy,
 * or a stack-scoped work root. No lookup samples the current selection. */
struct od_field_owner {uint32_t field,ticket;};
struct od_owners {uint32_t tasks[OD_TASKS];struct od_field_owner fields[OD_OWNER_FIELDS];};
const struct od_context *od_ticket_pin(uint32_t,struct r5g_lease *);
const struct od_context *od_field_pin(uintptr_t,struct r5g_lease *);
const struct od_context *od_work_pin(const uint32_t *,struct r5g_lease *);
void od_work_drop(struct r5g_lease *);
int od_field_take(uintptr_t,struct r5g_lease *);
int od_field_copy(uintptr_t,uintptr_t);
void od_field_clear(uintptr_t);
int od_pool_field(uintptr_t);
void od_task_retire(uintptr_t,uintptr_t);
void od_owners_pool_reset(uintptr_t);
void od_color_accept(void);
void *od_settings_snapshot(void *,const void *,uint32_t);
void *od_freeze_snapshot(void *,const void *,uint32_t);
void od_capture_snapshot(void *,const void *);
#endif
