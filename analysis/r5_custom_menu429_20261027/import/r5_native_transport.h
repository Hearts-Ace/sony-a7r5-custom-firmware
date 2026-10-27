#ifndef R5_NATIVE_TRANSPORT_H
#define R5_NATIVE_TRANSPORT_H
#include <stddef.h>
#include <stdint.h>
/* Exact R5 4.04 AP PLT bindings. Never executed on the host/camera by builds.
 * Nonwaiting allocation; returns native allocation/send/free errors. This is
 * a queue submission primitive, never an application ACK or timeout proof. */
int r5_native_ap_send(void *,const uint8_t *,size_t);
#endif
