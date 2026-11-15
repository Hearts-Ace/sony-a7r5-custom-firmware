#ifndef R5SOUND_STORE_H
#define R5SOUND_STORE_H
#include "r5sound_catalog.h"
#include "r5_native_lut_directory.h"
void r5sound_storage_bind(r5sound_storage *,struct r5_lut_directory *);
void r5sound_log(unsigned,const char *,const char *,int,const uint32_t *,unsigned);
#endif
