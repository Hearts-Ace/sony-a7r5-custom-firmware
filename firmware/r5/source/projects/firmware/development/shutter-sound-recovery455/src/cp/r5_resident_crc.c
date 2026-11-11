/* Exact CP wire CRC algorithm from the canonical shared header. */
#include <stdint.h>
#include <stddef.h>
uint32_t r5_wire_crc(const uint8_t *p,size_t n){uint32_t c=~0u;size_t i;unsigned j;for(i=0;i<n;i++){c^=i>=28&&i<32?0:p[i];for(j=0;j<8;j++)c=(c>>1)^((0u-(c&1u))&0xedb88320u);}return ~c;}
