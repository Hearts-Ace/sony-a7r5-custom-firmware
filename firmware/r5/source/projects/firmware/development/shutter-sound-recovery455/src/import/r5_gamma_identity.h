#ifndef R5_GAMMA_IDENTITY_H
#define R5_GAMMA_IDENTITY_H
#include "r5_boot_bank.h"
/* Components are exactly materialized_root+0x624, not root pointers. */
uint32_t r5_gamma_ready(void);
/* Short lifetime exclusion only; no native deep call may run while held. */
int r5_gamma_lifetime_take(void);
void r5_gamma_lifetime_drop(void);
int r5_custom_bank_seal(struct r5_boot_bank *,uint32_t token);
uint32_t r5_gamma_pool_ready(void *pool,uint32_t arg,uint32_t limit);
uint32_t r5_gamma_q_release(void *pool,void *q);
uint32_t r5_gamma_capture_begin(uint32_t component);
void r5_gamma_capture_stage(uint32_t component,uint32_t marker,
                            uint32_t base,uint32_t token,uint32_t valid);
void r5_gamma_owner(void *descriptor,void *inactive_root);
void r5_gamma_q_initialize(void *q);
void r5_gamma_q_rebuild(void *to,const uint32_t *model,const void *prior,const void *mode);
void r5_gamma_q_rebuild_alternate(void *to,const uint32_t *model,const void *prior,const void *mode);
void r5_gamma_q_snapshot(void *to,const uint32_t *descriptor,const void *cfg,const void *prior);
void r5_gamma_q_clone(void *to,const void *from,uint32_t n);
const struct r5_boot_value *r5_gamma_q_select(const void *request);
void r5_gamma_consume(uint32_t domain,uint8_t *a,uint8_t *main,uint8_t *aux,void *request);
/* Mechanical lifetime ticket with exact 492-byte selected-colour core seal.
 * Other native Q controls are outside this core. A valid ticket proves old Q ownership,
 * not complete model/route semantic qualification. Callers must prove that
 * separately before applying any custom parameter or calling commit. */
struct r5_gamma_rebuild_ticket {
 uint32_t q,epoch,sequence,generation,packed,token;
};
int r5_gamma_q_rebuild_begin(void *to,const void *model,struct r5_gamma_rebuild_ticket *);
int r5_gamma_q_rebuild_valid(const struct r5_gamma_rebuild_ticket *);
int r5_gamma_q_rebuild_commit(const struct r5_gamma_rebuild_ticket *,uint32_t qualified);
/* Caller must already hold r5_gamma_lifetime_take; never acquire recursively. */
int r5_gamma_q_rebuild_valid_locked(const struct r5_gamma_rebuild_ticket *);
int r5_gamma_q_rebuild_commit_locked(const struct r5_gamma_rebuild_ticket *,uint32_t qualified);
void r5_gamma_q_model_invalidate(void *model);
void r5_gamma_q_head_clone(void *to,const void *from);
void r5_gamma_q_saved_rebuild(void *to,const void *model,const void *cfg,uint32_t mode,uint32_t flags);
void r5_gamma_q_model_copy(void *model,const void *from);
void r5_gamma_q_model_saved(void *model,const void *cfg,uint32_t mode,uint32_t flags);
#endif
