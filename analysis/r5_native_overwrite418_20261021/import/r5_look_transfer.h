#ifndef R5_LOOK_TRANSFER_H
#define R5_LOOK_TRANSFER_H
#include "r5_boot_bank.h"

/* Experimental new envelope ABI; 0xe7 is explicitly added, never inferred as
 * an unused native opcode. 32 bytes includes the native eight-byte prefix.
 * Bytes: class, version, opLE16, "R5LX", token/mask/slot/payloadCRC/seq/msgCRC.
 * PUT adds 1172 compact bytes (name32 plus all1140 color bytes). ACK adds state/status/received_mask (12 bytes).
 * msgCRC is IEEE CRC32 over the entire packet with bytes28..31 set to zero. */
#define R5_TRANSFER_CLASS 0xe7u
#define R5_TRANSFER_HEADER 32u
#define R5_TRANSFER_VALUES 1172u
#define R5_TRANSFER_MAX (R5_TRANSFER_HEADER+R5_TRANSFER_VALUES)
#define R5_TRANSFER_ACK 44u
enum r5_transfer_op { R5_X_BEGIN=1, R5_X_PUT=2, R5_X_SEAL=3, R5_X_ACK=0x80 };
enum r5_transfer_status { R5_X_OK=0, R5_X_BAD_PACKET=1, R5_X_BAD_STATE=2,
    R5_X_BAD_VALUES=3, R5_X_BAD_DIGEST=4, R5_X_NOT_READY=5 };

/* Explicit new CP BSS region, 24 bytes. Zero only on the validated cold path.
 * One attempt per cold boot, no reset/retry API. Never bank.reserved. */
struct r5_transfer_cp { uint32_t token,mask,payload_crc,last_slot,phase,error; };

int r5_transfer_is_envelope(const uint8_t *, size_t);
/* Returns 1 if consumed (valid/invalid new envelope), 0 for original dispatch.
 * Trusted native adapter has checked source queue0x80020002 and actual length.
 * ACK bytes are an output contract, not evidence of a real transmitted ACK. */
int r5_transfer_cp_receive(struct r5_transfer_cp *, struct r5_boot_bank *,
    const uint8_t *, size_t, uint8_t ack[R5_TRANSFER_ACK]);
uint32_t r5_transfer_bank_crc(const struct r5_boot_bank *);
int r5_boot_bank_put_compact(struct r5_boot_bank *,uint32_t,unsigned,
    const uint8_t[R5_TRANSFER_VALUES]);

/* No ambient clock or unbounded retry. Caller serializes access
 * to this relocatable context and supplies monotonic timestamps and deadline.
 * Native sender must use wait=0 and propagate allocation/send/free failures.
 * A successful send never activates the mask. Only a matching SEALED ACK does. */
struct r5_transfer_ap {
    const struct r5_look_set *set;
    uint32_t token,mask,payload_crc,slot,sequence,phase,error;
    /* Only a fully validated NOT_READY SEAL ACK permits a delayed retry of
     * SEAL itself. BEGIN/PUT and the original deadline are never replayed. */
    uint64_t deadline,last_now,retry_at;
};
struct r5_transfer_io { void *context; int (*send)(void *,const uint8_t *,size_t); };
int r5_transfer_ap_begin(struct r5_transfer_ap *,const struct r5_look_set *,
    uint32_t token,uint32_t payload_crc,uint64_t now,uint64_t deadline);
/* 0=pending,1=sealed,-1=error; packet is caller-owned1204-byte scratch. */
int r5_transfer_ap_step(struct r5_transfer_ap *,const struct r5_transfer_io *,
    uint64_t now,uint8_t packet[R5_TRANSFER_MAX]);
int r5_transfer_ap_ack(struct r5_transfer_ap *,const uint8_t *,size_t,uint64_t now);
uint32_t r5_transfer_ap_active_mask(const struct r5_transfer_ap *);
#endif
