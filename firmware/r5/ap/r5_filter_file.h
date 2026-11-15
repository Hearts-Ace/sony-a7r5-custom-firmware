#ifndef R5_FILTER_FILE_H
#define R5_FILTER_FILE_H
#include <stdint.h>
#include <stddef.h>
#define R5F_HEADER 128u
#define R5F_RECORD 2452u
#define R5F_MAX (R5F_HEADER + 12u*R5F_RECORD)
#define R5F_COMPACT 2392u
struct r5f_entry {
    uint32_t offset, crc;
    char short_name[24], full_name[64];
};
/* Only names, offsets and record checksums survive boot. No color parameters. */
struct r5f_index {
    uint8_t header[R5F_HEADER];
    uint32_t mask;
    struct r5f_entry entry[12];
};
struct r5f_reader {
    void *context;
    /* Exact-position read; returns 0 and actual bytes, including EOF. */
    int (*read_at)(void *,uint32_t,uint8_t *,size_t,size_t *);
};
uint32_t r5f_crc(const uint8_t *,size_t);
int r5f_index_bytes(const uint8_t *,size_t,struct r5f_index *);
/* Validate indexed identity and only the selected record. On failure, compact
 * remains untouched. AP file owner must keep one fd throughout the operation. */
int r5f_read_one(const struct r5f_reader *,const struct r5f_index *,unsigned,
                uint8_t compact[R5F_COMPACT]);
/* Empty SD file is the deliberate clear action, represented by this canonical
 * v4 header on eMMC. */
void r5f_empty(uint8_t [R5F_HEADER]);
#endif
