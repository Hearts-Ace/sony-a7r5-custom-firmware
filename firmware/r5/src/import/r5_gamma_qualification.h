#ifndef R5_GAMMA_QUALIFICATION_H
#define R5_GAMMA_QUALIFICATION_H
#include <stdint.h>
/* Conservative primary-request contract, called BEFORE any custom CC1/B13.
 * Returns zero for unsupported routes. The caller still owns the same Q and
 * must verify its selected-colour core, generation, bank token and carrier. */
uint32_t r5_gamma_route_eligible(const void *route,uint32_t base);
uint32_t r5_gamma_request_eligible(const void *request,uint32_t base,uint32_t before_adapter);
#endif
