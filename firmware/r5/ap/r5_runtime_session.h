#ifndef R5_RUNTIME_SESSION_H
#define R5_RUNTIME_SESSION_H
#include <stdint.h>
void r5_session_cold(void);
int r5_session_cold_start(void);
uint32_t r5_session_epoch(void);
uint32_t r5_session_event_epoch(void);
int r5_session_current(void);
int r5_session_prepare(void);
void r5_session_finish(void);
void r5_stage421_power(const uint32_t *);
uint32_t r5_session_token(uint32_t);
void *r5_stage421_loop(void *);
#endif
