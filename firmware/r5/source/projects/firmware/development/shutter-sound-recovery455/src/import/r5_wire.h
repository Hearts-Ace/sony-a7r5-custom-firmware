#ifndef R5_WIRE_H
#define R5_WIRE_H
#include <stdint.h>
#include <stddef.h>
static inline uint32_t r5_wire_get(const uint8_t *p){return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static inline void r5_wire_put(uint8_t *p,uint32_t x){p[0]=(uint8_t)x;p[1]=(uint8_t)(x>>8);p[2]=(uint8_t)(x>>16);p[3]=(uint8_t)(x>>24);}
static inline uint32_t r5_wire_crc(const uint8_t *p,size_t n){uint32_t c=~0u;size_t i;unsigned j;for(i=0;i<n;i++){c^=i>=28&&i<32?0:p[i];for(j=0;j<8;j++)c=(c>>1)^((0u-(c&1u))&0xedb88320u);}return ~c;}
#endif
