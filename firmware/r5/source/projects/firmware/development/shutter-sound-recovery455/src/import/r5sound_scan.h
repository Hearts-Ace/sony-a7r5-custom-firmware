#ifndef R5SOUND_SCAN_H
#define R5SOUND_SCAN_H
#include <stddef.h>
#include <stdint.h>

/* Original R5 AP wrappers, not the three-argument Fsys_FindFirst export.
 * They map the native raw END(2) to END(4). FILEINFO is borrowed storage;
 * there is no file/iterator handle to close. Never retain its name pointer. */
#define R5SOUND_FIND_INFO_BYTES 3112u
#define R5SOUND_FIND_SCRATCH_BYTES 4096u
#define R5SOUND_SCAN_ENTRY_LIMIT 4096u
#define R5SOUND_NAME_BYTES 255u
enum { R5SOUND_SCAN_OK=0,R5SOUND_SCAN_INVALID=1,R5SOUND_SCAN_CORRUPT=2,
       R5SOUND_SCAN_NATIVE=3,R5SOUND_SCAN_LIMIT=4,R5SOUND_SCAN_CANCELED=5,
       R5SOUND_SCAN_VISITOR=6 };
typedef int (*r5sound_scan_visit)(void *,const char *,size_t,uint64_t,uint8_t);
struct r5sound_scan_api {
 int (*first)(const char *,void *);
 int (*next)(void *);
 int (*current)(void *); /* optional cancellation/media witness */
 void *current_context;
};
struct r5sound_scan_result {
 uint32_t entries,packages,directories,other,unsafe;
 int32_t native_status,visitor_status;
};
/* Scan drive:/ root once, visit every safe *.R5S in native order. No allocation,
 * file open, conversion or CP query. callback nonzero is an explicit failure;
 * capacity limits in a catalog must not be reported as a complete import.
 * scratch must be 8-byte aligned and >=4096; names are UTF-8, <=255 bytes and
 * borrowed only for this callback. Zero/oversize packages still reach callback for
 * format/size rejection and diagnostic recording by the importer.
 * No elapsed-time guarantee is claimed for synchronous original Fsys calls. */
int r5sound_scan_root(const struct r5sound_scan_api *,char,void *,size_t,
                     r5sound_scan_visit,void *,struct r5sound_scan_result *);
int r5sound_scan_name(const char *,size_t);
#endif
