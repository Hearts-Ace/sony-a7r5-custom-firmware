#ifndef R5_FILTER_RUNTIME423_H
#define R5_FILTER_RUNTIME423_H
#include <stdint.h>
struct r5_lut_directory;
unsigned r5_filter_selected(void);
unsigned r5_filter_pending(void);
int r5_filter_request(unsigned);
/* UI command states persist until another accepted request: idle/pending/success/failure.
 * The UI must not close or publish a success while state is pending/failed. */
unsigned r5_filter_command_state(void);
unsigned r5_filter_command_sequence(void);
int r5_filter_reload_request(void);
void r5_filter_refresh_construct425(void *,const void *);
void r5_filter_refresh_execute425(void *);
void r5_filter_load_selection(struct r5_lut_directory *);
void r5_filter_bank_ready(uint32_t alias,uint32_t crc,uint32_t mask);
void r5_filter_service(void);
int r5_filter_inbound(const uint8_t *,uint32_t);
#endif
