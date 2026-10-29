#ifndef R5_RUNTIME_SESSION_H
#define R5_RUNTIME_SESSION_H
#include <stdint.h>
/* One worker owns resets; power callback only closes admission/records events. */
void r5_session_cold(void);
/* First admitted worker session only; independent of early power-event epochs. */
int r5_session_cold_start(void);
uint32_t r5_session_epoch(void);
uint32_t r5_session_event_epoch(void);
int r5_session_current(void);
int r5_session_admit(void);
void r5_session_leave(void);
int r5_session_prepare(void);
void r5_session_finish(void);
void r5_stage421_power(const uint32_t *);
int r5_session_new_transfer(void);
uint32_t r5_session_token(uint32_t);
void r5_stage421_probe_reset(void);
void r5_stage421_transfer_reset(void);
void r5_stage421_log_reset(void);
void *r5_stage421_loop(void *);
#endif
