#ifndef R5SOUND_CATALOG_H
#define R5SOUND_CATALOG_H
#include <stddef.h>
#include <stdint.h>
#include "sound_core.h"
#include "r5sound_package.h"
#define R5SOUND_MAX_FILES 60u
#define R5SOUND_INDEX_BYTES (32u+R5SOUND_MAX_FILES*296u)
typedef struct {char name[256];uint8_t sha[32];uint32_t bytes,card;} r5sound_entry;
typedef struct {uint32_t count;r5sound_entry entries[R5SOUND_MAX_FILES];} r5sound_catalog;
/* One finite storage owner. Names passed to IO are generated basenames only.
 * read: 0 success, 1 confirmed absent, negative error. Atomic write includes
 * temporary-file readback and directory sync. No CP/native sound operation. */
typedef struct {
 void *ctx;
 int (*read)(void *,const char *,uint8_t *,size_t,size_t *);
 int (*write_atomic)(void *,const char *,const uint8_t *,size_t);
 int (*remove)(void *,const char *);
 void (*log)(void *,const char *,const char *,int,uint32_t,uint32_t);
 /* Read and validate only the requested precompiled volume from one open
  * immutable blob. expected_sha is the complete fixed-header identity. */
 int (*audio)(void *,const char *,const uint8_t *,size_t,unsigned,
              uint8_t *,size_t,size_t *);
} r5sound_storage;
enum {R5SOUND_OK=0,R5SOUND_ABSENT=1,R5SOUND_BAD=-1,R5SOUND_IO=-2,R5SOUND_FULL=-3};
void r5sound_blob_name(const uint8_t sha[32],char out[76]);
int r5sound_catalog_decode(const uint8_t *,size_t,r5sound_catalog *);
size_t r5sound_catalog_encode(const r5sound_catalog *,uint8_t *,size_t);
int r5sound_catalog_load(const r5sound_storage *,r5sound_catalog *,uint8_t *,size_t);
/* Validated files are saved one at a time, never held as a full audio bank.
 * Full catalog returns FULL; caller must retain old manifest, not truncate. */
int r5sound_catalog_add(const r5sound_storage *,r5sound_catalog *,unsigned,
 const char *,size_t,const uint8_t *,size_t);
int r5sound_catalog_publish(const r5sound_storage *,r5sound_catalog *,
 const r5sound_catalog *,uint8_t *,size_t);
int r5sound_catalog_audio(const r5sound_storage *,const r5sound_entry *,unsigned,
 uint8_t *,size_t,size_t *);
int r5sound_selection_load(const r5sound_storage *,const r5sound_catalog *,unsigned *);
int r5sound_selection_save(const r5sound_storage *,const r5sound_catalog *,unsigned);
int r5sound_volume_load(const r5sound_storage *,unsigned *);
int r5sound_volume_save(const r5sound_storage *,unsigned);
#endif
