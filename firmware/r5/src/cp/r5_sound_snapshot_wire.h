#ifndef R5_SOUND_SNAPSHOT_WIRE_H
#define R5_SOUND_SNAPSHOT_WIRE_H
/* Shared AP/CP little-endian wire. Epoch is an AP opaque echo only: it is
 * deliberately not claimed to witness CP cold boot or a fresh DMM session. */
#define R5SS_SNAPSHOT_CLASS 0xe6u
#define R5SS_SNAPSHOT_VERSION 1u
#define R5SS_SNAPSHOT_MAGIC 0x31535352u /* RSS1 */
#define R5SS_SNAPSHOT_REQUEST 1u
#define R5SS_SNAPSHOT_RETIRE_QUERY 2u
#define R5SS_SNAPSHOT_GAIN_BIND 3u
#define R5SS_SNAPSHOT_ACK 0x81u
#define R5SS_SNAPSHOT_REQUEST_BYTES 32u
#define R5SS_SNAPSHOT_REPLY_BYTES 192u
#define R5SS_SNAPSHOT_AP_QUEUE 0x80020002u
#define R5SS_SNAPSHOT_CP_QUEUE 0x90030001u
#define R5SS_SNAPSHOT_FIELD_COUNT 22u
enum {
 R5SS_SNAP_O_CLASS=0,R5SS_SNAP_O_VERSION=1,R5SS_SNAP_O_OP=2,
 R5SS_SNAP_O_LENGTH=3,R5SS_SNAP_O_MAGIC=4,R5SS_SNAP_O_SERIAL=8,
 R5SS_SNAP_O_EPOCH=12,R5SS_SNAP_O_BASELINE_SEQUENCE=16,R5SS_SNAP_O_CRC=28,
 R5SS_SNAP_O_BUSY_MASK=32,R5SS_SNAP_O_CHANGED_MASK=36,
 R5SS_SNAP_O_STABLE=40,R5SS_SNAP_O_OBSERVED_IDLE=44,
 R5SS_SNAP_O_RETIREMENT=48,R5SS_SNAP_O_INITIAL_REJECTS=52,
 R5SS_SNAP_O_CP_WITNESS=R5SS_SNAP_O_INITIAL_REJECTS, /* legacy offset alias; no boot witness */
 R5SS_SNAP_O_FIELD_COUNT=56,R5SS_SNAP_O_KIND17_EXISTS=60,
 R5SS_SNAP_O_FIELDS=64,R5SS_SNAP_O_COMPLETION_SEQUENCE=152,
 R5SS_SNAP_O_COMPLETION_RESULT=156,
 R5SS_SNAP_O_KIND17_PHYS_LO=160,R5SS_SNAP_O_KIND17_PHYS_HI=164,
 R5SS_SNAP_O_KIND17_ENCODED_BYTES=168,R5SS_SNAP_O_KIND17_CPU_ALIAS=172,
 R5SS_SNAP_O_PENDING17_BEFORE=176,R5SS_SNAP_O_PENDING17_AFTER=180,
 R5SS_SNAP_O_INITIAL_OWNER_SAFE=184,R5SS_SNAP_O_KIND17_DESCRIPTOR_VALID=188
};
/* OP3 uses16/20/24 as physicalLo/physicalHi/encodedBytes. A stable matching
 * native descriptor with no actor/MMIO/pending17 ownership binds tag+serial;
 * reply184 is its acceptance flag. OP1/OP2 retain their original semantics. */
/* OP1 observes only. OP2 is guarded by the original6549DC completion witness:
 * exactly one native kind17 Start is outstanding; AP reads the baseline before
 * synchronous Start, then awaits completion advance and native actor cleanup.
 * AP MUST NOT treat OBSERVED_IDLE or STABLE as RETIRED. No boot proof is added. */
enum { R5SS_RETIREMENT_UNKNOWN=0,R5SS_RETIREMENT_RETIRED=1,
       R5SS_RETIREMENT_BUSY=2 };
/* Read-only initial-registration diagnostics. These are not playback policy
 * or a CP cold-boot witness. INITIAL_OWNER_SAFE is true exactly when zero. */
enum { R5SS_INITIAL_REGISTRY_BEFORE=1u<<0,R5SS_INITIAL_REGISTRY_AFTER=1u<<1,
       R5SS_INITIAL_DESCRIPTOR=1u<<2,R5SS_INITIAL_EXISTS17=1u<<3,
       R5SS_INITIAL_LOOKUP17=1u<<4,R5SS_INITIAL_PENDING17=1u<<5,
       R5SS_INITIAL_ACTOR=1u<<6,R5SS_INITIAL_MMIO=1u<<7 };
unsigned r5ss_snapshot_crc(const unsigned char *,unsigned);
int r5ss_cp_snapshot_make_reply(const unsigned char *,unsigned,unsigned,unsigned char *);
int r5ss_cp_snapshot_consume(const unsigned char *,unsigned);
#endif
