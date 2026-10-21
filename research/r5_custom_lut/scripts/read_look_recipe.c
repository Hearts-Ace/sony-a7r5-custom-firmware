/* Portable bounded structural reader for R5LKDEV1 development recipes.
 * No firmware addresses, device IO, allocation, hooks or parameter writes.
 * Host CLI only when compiled with -DR5_LOOK_READER_MAIN.
 * META is opaque here; Python additionally validates its JSON semantics.
 * Success means structural validity ONLY, never authorization to apply.
 */
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <float.h>

#define R5_LOOK_MAX 65536u

typedef struct {
    int16_t matrix_q10[6];
    float axis[129];
    float curve[129];
    const uint8_t *metadata;
    uint32_t metadata_bytes;
} r5_look_dev;

static uint16_t u16(const uint8_t *p) {
    return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}

static uint32_t u32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static float f32(const uint8_t *p) {
    uint32_t bits = u32(p);
    float f;
    _Static_assert(sizeof(float) == 4, "IEEE binary32 float required");
    _Static_assert(FLT_RADIX == 2 && FLT_MANT_DIG == 24 && FLT_MAX_EXP == 128,
                   "IEEE binary32 float required");
    memcpy(&f, &bits, 4);
    return f;
}

static uint32_t crc32(const uint8_t *p, size_t n) {
    uint32_t crc = UINT32_MAX;
    for (size_t i = 0; i < n; i++) {
        crc ^= p[i];
        for (unsigned j = 0; j < 8; j++)
            crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}

/* out is modified only after the complete structural and numeric checks.
 * metadata borrows the input buffer; its lifetime must exceed out's use. */
int r5_read_look_dev(const uint8_t *raw, size_t n, r5_look_dev *out) {
    if (!raw || !out || n < 32 || n > R5_LOOK_MAX) return -1;
    if (memcmp(raw, "R5LKDEV1", 8) || u16(raw+8) != 1 ||
        u16(raw+10) != 32 || u32(raw+12) != 1 || u32(raw+16) != n)
        return -2;
    for (unsigned i = 24; i < 32; i++) if (raw[i]) return -2;
    if (crc32(raw+32, n-32) != u32(raw+20)) return -3;
    const uint8_t *meta = NULL, *q = NULL, *axis = NULL, *curve = NULL;
    uint32_t meta_bytes = 0;
    unsigned seen = 0;
    for (size_t at = 32; at < n;) {
        if (n-at < 8) return -4;
        const uint8_t *tag = raw+at;
        uint32_t length = u32(raw+at+4);
        at += 8;
        if (length > n-at) return -4;
        unsigned bit;
        if (!memcmp(tag, "META", 4)) {
            bit = 1; meta = raw+at; meta_bytes = length;
            if (!length) return -4;
        } else if (!memcmp(tag, "B13Q", 4)) {
            bit = 2; q = raw+at;
            if (length != 12) return -4;
        } else if (!memcmp(tag, "AXIS", 4)) {
            bit = 4; axis = raw+at;
            if (length != 516) return -4;
        } else if (!memcmp(tag, "CURV", 4)) {
            bit = 8; curve = raw+at;
            if (length != 516) return -4;
        } else return -4;
        if (seen & bit) return -4;
        seen |= bit;
        at += length;
    }
    if (seen != 15) return -4;
    r5_look_dev result;
    memset(&result, 0, sizeof(result));
    result.metadata = meta;
    result.metadata_bytes = meta_bytes;
    for (unsigned i = 0; i < 6; i++) {
        int32_t value = u16(q+2*i);
        if (value >= 32768) value -= 65536;
        if (value < -4096 || value > 4096) return -5;
        result.matrix_q10[i] = (int16_t)value;
    }
    for (unsigned i = 0; i < 129; i++) {
        result.axis[i] = f32(axis+4*i);
        result.curve[i] = f32(curve+4*i);
        if (!isfinite(result.axis[i]) || !isfinite(result.curve[i]) ||
            result.curve[i] < 0 || result.curve[i] > 1) return -5;
        if (i && (result.axis[i] <= result.axis[i-1] ||
                  result.curve[i] < result.curve[i-1])) return -5;
    }
    if (result.axis[0] != 0 || result.axis[128] <= 0 ||
        result.axis[128] > 64) return -5;
    *out = result;
    return 0;
}

#ifdef R5_LOOK_READER_MAIN
#include <stdio.h>
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    FILE *handle = fopen(argv[1], "rb");
    if (!handle) return 2;
    static uint8_t raw[R5_LOOK_MAX+1];
    size_t n = fread(raw, 1, sizeof(raw), handle);
    int io_error = ferror(handle);
    fclose(handle);
    if (io_error) return 2;
    r5_look_dev result;
    int status = r5_read_look_dev(raw, n, &result);
    if (status) { fprintf(stderr, "invalid development recipe: %d\n", status); return 1; }
    printf("{\"structural_read_ok\":true,\"camera_apply_allowed\":false,"
           "\"metadata_semantics_checked\":false,\"bytes\":%zu,"
           "\"matrix_q10\":[%d,%d,%d,%d,%d,%d]}\n", n,
           result.matrix_q10[0], result.matrix_q10[1], result.matrix_q10[2],
           result.matrix_q10[3], result.matrix_q10[4], result.matrix_q10[5]);
    return 0;
}
#endif
