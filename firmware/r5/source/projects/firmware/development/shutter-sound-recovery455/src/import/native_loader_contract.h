#ifndef R5SS_NATIVE_LOADER_CONTRACT_H
#define R5SS_NATIVE_LOADER_CONTRACT_H
#include <stdint.h>
#include <stddef.h>

/* Static ABI recovered from the original R5 sequence_boot path. Native calls
 * may block on OSAL replies: worker use only. Names describe fields proved by
 * instructions; reserved fields must be zero, not borrowed from M4 addresses. */
typedef struct {uint32_t id,side;} r5ss_dmm_claim_request;
typedef struct {
 uint32_t id;int32_t handle;uint64_t physical;
 uint32_t bytes,reserved,status,pad;
} r5ss_dmm_extent;
typedef struct {uint32_t handle;} r5ss_dmm_release_request;
typedef struct {
 const char *path;uint64_t physical;uint32_t bytes;
 uint8_t flag20,reserved[3];
} r5ss_mem_map_request;
typedef struct {
 void *view;uint32_t view_bytes;int32_t fd;
 void *map_base;uint32_t map_bytes,reserved28,status,pad;
} r5ss_mem_map_reply;
typedef struct {void *map_base;uint32_t map_bytes;int32_t fd;} r5ss_mem_unmap_request;
typedef struct {const char *path;void *buffer;uint64_t capacity;} r5ss_file_read_request;
typedef struct {uint32_t status,pad;uint64_t actual;} r5ss_file_read_reply;
typedef struct {
 uint32_t source_handle,source_offset,dest_handle,dest_offset,bytes;
} r5ss_native_copy_request;
typedef struct {
 uint8_t enabled,pad1[3];uint32_t kind;uint64_t physical,bytes;
 uint32_t priority,field28,continuous,cont_length,cont_first_length,pad44;
} r5ss_table_request;

_Static_assert(sizeof(void *)==8,"R5 native contract is LP64");
_Static_assert(offsetof(r5ss_dmm_extent,status)==24,"claim status");
_Static_assert(sizeof(r5ss_dmm_extent)==32,"claim extent");
_Static_assert(offsetof(r5ss_mem_map_reply,status)==32,"map status");
_Static_assert(sizeof(r5ss_mem_map_reply)==40,"map reply");
_Static_assert(sizeof(r5ss_mem_unmap_request)==16,"unmap request");
_Static_assert(sizeof(r5ss_file_read_request)==24,"file request");
_Static_assert(offsetof(r5ss_file_read_reply,actual)==8,"file actual");
_Static_assert(sizeof(r5ss_native_copy_request)==20,"copy request");
_Static_assert(sizeof(r5ss_table_request)==48,"table request");
_Static_assert(offsetof(r5ss_table_request,physical)==8,"table physical");
_Static_assert(offsetof(r5ss_table_request,cont_first_length)==40,"table continuous");

/* Claim returns status at +24; side0 is AP, side1 CP. A handle is owned only
 * after successful original RPC response. The original loader claims 70817
 * on each side and uses the actual returned extent, never a fixed address. */
extern void r5ss_native_dmm_claim(const r5ss_dmm_claim_request *,r5ss_dmm_extent *);
extern void r5ss_native_dmm_release(const r5ss_dmm_release_request *,uint32_t *status);
extern void r5ss_native_mem_map(const r5ss_mem_map_request *,r5ss_mem_map_reply *);
extern void r5ss_native_mem_unmap(const r5ss_mem_unmap_request *,uint32_t *status);
extern void r5ss_native_file_read(const r5ss_file_read_request *,r5ss_file_read_reply *);
extern void r5ss_native_copy(const r5ss_native_copy_request *,uint32_t *status);
extern void r5ss_native_set_table(const r5ss_table_request *,uint32_t *status);
/* Original AP352135C generic synchronous IPC helper, also used for read-only
 * DMM cmd28/2A. Original queue/ACK/assert behavior remains native. For SYSND,
 * 0329 operation1 starts, operation2 stops; 032A is gain and is never Stop. */
extern void r5ss_native_sysnd_command(uint32_t destination,const void *request,
                                    uint32_t bytes,void *reply,uint32_t reply_bytes);
extern uint32_t r5ss_native_sysnd_result(uint32_t native_status);
extern void r5ss_native_sysnd_start(const uint32_t request[3],int32_t *status);
#endif
