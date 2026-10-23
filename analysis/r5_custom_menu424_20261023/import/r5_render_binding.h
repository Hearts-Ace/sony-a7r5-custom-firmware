#ifndef R5_RENDER_BINDING_H
#define R5_RENDER_BINDING_H
#include "r5_boot_bank.h"

/* Offline ABI only: none of these fields has been assigned native padding.
 * Identity comes from this exact snapshot invocation, never the later global
 * receiver shadow. The adapter must establish domain and scene/override gates.
 * Unknown values fail closed. This does not infer a camera mode enumeration. */
struct r5_render_identity {
    const void *state, *source;
    uint32_t sequence, marker, base, valid, token;
    uint32_t domain_allow, scene_allow, override_clear;
};
const struct r5_boot_value *r5_render_select(const struct r5_boot_bank *,
    const struct r5_render_identity *, const void *state, const void *source,
    uint32_t observed_base);
/* Caller has already populated the complete original native 576-byte Gamma
 * record and owns it through all synchronous and deferred uses. Tail fields,
 * including native pointers, remain byte exact. No mutable shared scratch. */
int r5_render_gamma_overlay(const struct r5_boot_bank *,
    const struct r5_boot_value *, uint8_t owned[576]);
#endif
