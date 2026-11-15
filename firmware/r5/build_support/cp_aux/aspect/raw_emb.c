/* RAW Bayer/DefaultCrop/SonyCrop remain native. Only the embedded JPEG's
 * size declaration follows the per-photo crop already used by its encoder.
 * R5 callsite48a00a passes packet=task+5b3c, header and frozen task.
 */
#include <stdint.h>
#include "crop_core.h"
extern uint32_t aspect_task_id(uintptr_t);
static void put32(uint8_t *p,uint32_t x) {
    p[0]=(uint8_t)x;p[1]=(uint8_t)(x>>8);p[2]=(uint8_t)(x>>16);p[3]=(uint8_t)(x>>24);
}
uint32_t aspect_raw_emb_build(void *packet,uint8_t *header,uintptr_t task) {
    uint32_t result=((uint32_t(*)(void*,void*,uintptr_t))0xade83du)(packet,header,task);
    uint32_t id=aspect_task_id(task);
    if (!id) return result;
    const uint16_t *full=(const uint16_t *)(task+0x234);
    aspect_geometry source={(uint16_t)((full[0]+127u)&~127u),full[1],full[0],full[1],0,0},crop;
    if (!aspect_crop_geometry(&source,id,0,&crop)) return result;
    put32(header+0x14a2c,crop.width);put32(header+0x14a30,crop.height);
    return result;
}
