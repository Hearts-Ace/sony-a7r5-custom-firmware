#ifndef R5_BOOT_BANK_H
#define R5_BOOT_BANK_H
#include "sd_native_look.h"

/* Offline candidate CP ABI. The startup owner must serialize these calls and
 * keep every consumer stopped until seal returns. No runtime hot reload. */
struct r5_boot_record {
    uint8_t cc1[64];
    uint8_t block13[768];
    uint8_t gamma[576];
};
/* Only imported ordinates/coefficients occupy persistent CP bank space.
 * Native tail fields and pointers belong to each caller's render record. */
struct r5_boot_value {
    char name[32];
    uint8_t cc1[48], block13[576], gamma[516];
    uint32_t grid_enabled;
    int8_t grid[3][405];
    uint8_t grid_padding;
};
struct r5_boot_bank {
    uint32_t state, token, expected_mask, received_mask;
    uint32_t reserved[12];
    struct r5_boot_value value[R5_LOOK_SLOTS];
};

/* Only a zero-initialized, never-exposed bank may begin. An interrupted
 * transaction stays unusable until the next cold initialization. */
int r5_boot_bank_begin(struct r5_boot_bank *, uint32_t token, uint32_t mask);
/* Rejects overlap, duplicate and foreign tokens. No native pointers from SD. */
int r5_boot_bank_put(struct r5_boot_bank *, uint32_t token, unsigned slot,
    const struct r5_native_look *);
int r5_boot_bank_seal(struct r5_boot_bank *, uint32_t token);
/* Caller has already established photograph/preview mode. No native camera
 * mode number is inferred here. Returns NULL for the original path. */
const struct r5_boot_value *r5_boot_bank_select(const struct r5_boot_bank *,
    unsigned slot, unsigned allowed_path);
/* Render-owned output must already contain the original full native template.
 * Preserves CC1/B13/Gamma tails. Does not return pointers into a reused scratch
 * record or rewrite the sealed bank. The caller owns output through rendering. */
int r5_boot_bank_materialize(const struct r5_boot_bank *, unsigned slot,
    unsigned allowed_path, struct r5_boot_record *output);
#endif
