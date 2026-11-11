#ifndef R5_FILTER_SELECTION423_H
#define R5_FILTER_SELECTION423_H
#include <stddef.h>
#include <stdint.h>
#define R5_FILTER_SELECT_BYTES 32u
#define R5_FILTER_SELECT_CLASS 0xeau
#define R5_FILTER_SELECT_MAGIC 0x53463552u
#define R5_FILTER_SELECT_SET 1u
#define R5_FILTER_SELECT_ACK 0x81u
enum r5_filter_select_status {R5_F_OK=0,R5_F_BAD_PACKET=1,R5_F_NOT_READY=2,
    R5_F_STALE=3,R5_F_BAD_SELECTION=4,R5_F_BAD_BANK=5};
struct r5_filter_select_request {uint32_t sequence,selected,payload_crc,alias;};
/* Both fields are exact accepted transfer identity, including reused banks.
 * CRC32 over all 32 bytes with bytes28..31 zero; no native pointers admitted. */
int r5_filter_select_encode(const struct r5_filter_select_request *,uint8_t [32]);
int r5_filter_select_is_envelope(const uint8_t *,size_t);
/* Matching successful ACK returns 1; matching rejection returns -status;
 * malformed/foreign/mismatching ACK returns -256. Output is never published. */
int r5_filter_select_ack(const struct r5_filter_select_request *,const uint8_t *,size_t);
/* New sidecar independent from R5NATIVE.BIN. Only an acquired worker-owned
 * directory is admitted. Load preserves out on absence, I/O and invalid data. */
#define R5_FILTER_SELECTION_FILE "R5FILTER.BIN"
#define R5_FILTER_SELECTION_PENDING "R5FILTER.NEW"
#define R5_FILTER_SELECTION_BYTES 24u
struct r5_lut_directory;
int r5_filter_selection_load(struct r5_lut_directory *,unsigned *);
/* 0=durably published per POSIX fsync contract; 1=invalid input; 2=I/O before
 * rename; 3=publication uncertain (rename or directory fsync failed). Actual
 * device persistence is outside this host ABI proof. No render is activated. */
int r5_filter_selection_save(struct r5_lut_directory *,unsigned);
#endif
