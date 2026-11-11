/* Source-bound CP adapter. Link/test allocation is specified by the builder.
 * Never pass custom IDs to the original RAW/AF/dimension machinery.
 */
#include <stdint.h>
#include "crop_core.h"

extern volatile uint32_t aspect_selected_custom;
/* Native pool3F488C/3F4A36: at most490 objects, stride60A8. One byte per
 * native slot covers its complete capacity using less RAM than64 pointer/ID
 * pairs. No private fields are written inside the native task object.
 */
static uint8_t task_ids[490];
static uint32_t frozen_id, frozen_request;
extern uint32_t aspect_divide(uint32_t,uint32_t);

static void barrier(void) { __asm__ volatile ("dmb ish" ::: "memory"); }
static uint32_t read32(uintptr_t p) { return *(const volatile uint32_t *)p; }

static uint32_t task_index(uintptr_t task)
{
    uintptr_t base=read32(0xfc1730);
    uint32_t count=read32(0xfc1724);
    if (!base || !count || count>490 || task<base) return 490;
    uint32_t offset=task-base,index=aspect_divide(offset,0x60a8);
    if (index>=count || index*0x60a8!=offset) return 490;
    return index;
}

/* Native pool list construction completes before any object can be popped.
 * Clear once at that original serialized point, including same-base reuse;
 * lookups themselves never reset another task's state.
 */
void aspect_pool_reset(uintptr_t pool)
{
    if (pool==0xfc1720) {
        ((void (*)(void *,uint32_t))0x5866ac)(task_ids,sizeof(task_ids));
        barrier();
    }
}

uint32_t aspect_task_id(uintptr_t task)
{
    uint32_t index=task_index(task);
    if (index>=490) return 0;
    barrier();uint32_t id=task_ids[index];
    return id>=4 && id<=7 ? id : 0;
}

void aspect_task_clear(uintptr_t task)
{
    uint32_t index=task_index(task);
    if (index<490) {task_ids[index]=0;barrier();}
}

/* ImageParam_Capture is allocated from the native pool by3EF354/A05BC0.
 * At the checked pool-release siteA06184, keep the original lock/list/free
 * operation and retire the sidecar only when that operation succeeds.
 * This also covers owners that never reach normal Stage_Notify cleanup.
 */
uint32_t aspect_pool_release(uintptr_t pool,uintptr_t task)
{
    uint32_t result=((uint32_t (*)(uintptr_t,uintptr_t))0xa0623d)(pool,task);
    if (result) aspect_task_clear(task);
    return result;
}

/* Wrap only A049B0: native GFW snapshot, unchanged 0xD14 bytes. */
void *aspect_freeze_copy(void *destination, const void *source, uint32_t length)
{
    uint32_t id=0;
    if ((uintptr_t)destination == 0x11c1f90 &&
        (uintptr_t)source == 0x10fe5d0 && length == 0xd14 &&
        read32((uintptr_t)source+0xa8) == 2) id=aspect_selected_custom;
    frozen_id = id >= 4 && id <= 7 ? id : 0;
    frozen_request=read32(0x11c1f68);
    barrier();
    return ((void *(*)(void *, const void *, uint32_t))0x585fb8)
        (destination, source, length);
}

/* Wrap only A03142. Original copy writes every native field first. */
void aspect_capture_copy(void *destination, const void *source)
{
    ((void (*)(void *, const void *))0x3ed2b9)(destination, source);
    uintptr_t task=(uintptr_t)destination-0x20;
    aspect_task_clear(task);
    barrier();
    uint32_t id=frozen_id;
    if ((uintptr_t)source != 0x11c1f90 || read32(task+0x24) != 2 ||
        read32(task+0x5550) != frozen_request || id < 4 || id > 7) return;
    uint32_t index=task_index(task);
    if (index<490) {task_ids[index]=(uint8_t)id;barrier();}
}

/* Crop only the MainEnc request copy, after LUT/pixel development has finished.
 * Source task geometry and RAW buffers are never modified here.
 */
void *aspect_jpeg_request_copy(void *destination, const void *source, uint32_t length,
                              uintptr_t task)
{
    void *result=((void *(*)(void *, const void *, uint32_t))0x585fb8)
        (destination, source, length);
    uint32_t id=aspect_task_id(task);
    uintptr_t offset=(uintptr_t)source-task;
    if (length == sizeof(aspect_geometry) && id && (offset==0x5988 || offset==0x59ec)
        && (read32(task+0x53e8)==1 || read32(task+0x53f0)==1))
        aspect_crop_geometry((const aspect_geometry *)source,id|(offset==0x59ec ? ASPECT_GEOMETRY_AUX : 0),0,
                             (aspect_geometry *)destination);
    return result;
}

/* Stage_ThmResize's final zero-fill call, before either native SDF dispatch.
 * The request PINs have the original canvas/physical ownership and contain
 * ten halfwords each. Keep the 160x120 thumbnail canvas; crop source ROI and
 * recompute the centered image within that canvas. Native fill/flags survive.
 */
void *aspect_thumbnail_request_clear(void *destination,uint32_t length,uintptr_t task)
{
    void *result=((void *(*)(void *,uint32_t))0x5866ac)(destination,length);
    uint32_t id=aspect_task_id(task);
    if (!id || length!=0x20 || (read32(task+0x3c)&4)
        || (read32(task+0x53e8)!=1 && read32(task+0x53f0)!=1)) return result;
    uint16_t *input=(uint16_t *)((uint8_t *)destination-0xbc);
    uint16_t *output=(uint16_t *)((uint8_t *)destination-0x34);
    aspect_geometry geo={input[0],input[1],input[4],input[5],input[2],input[3]};
    if (!aspect_crop_geometry(&geo,id|ASPECT_GEOMETRY_AUX,0,&geo)) return result;
    uint32_t w=output[4],h=output[5],fw=w,fh=h;
    if (w*geo.height <= h*geo.width) fh=aspect_divide(w*geo.height,geo.width);
    else fw=aspect_divide(h*geo.width,geo.height);
    fw&=~3u;fh&=~1u;
    if (!fw || !fh) return result;
    input[2]=geo.x;input[3]=geo.y;input[4]=input[8]=geo.width;input[5]=input[9]=geo.height;
    output[6]=(w-fw)/2u;output[7]=(h-fh)/2u;output[8]=fw;output[9]=fh;
    return result;
}

/* Called after original GetImageSize at the two Stage_Notify sites only.
 * Format values here are CP native domains: 1 JPEG, 2 RAW, 4 HEIF.
 * Source: av-cam+1EBF70 reads the actual CP packet+1B0 and logs it using
 * 417045: "stl_file_format1:%d (0:NONE 1:JPEG 2:RAW 4:HEIF)".
 * Earlier route-report names of type-2/type-4 bodies were incorrect.
 */
uint32_t aspect_notify_dimensions(uint16_t *wh, uintptr_t task, uint32_t format)
{
    if (!wh || (format != 1 && format != 4)) return 0;
    uint32_t id=aspect_task_id(task);
    if (!id) return 0;
    aspect_geometry source={ (uint16_t)((wh[0]+127u)&~127u),wh[1],wh[0],wh[1],0,0 };
    aspect_geometry crop;
    if (!aspect_crop_geometry(&source,id,0,&crop)) return 0;
    wh[0]=crop.width; wh[1]=crop.height;
    return 1;
}

/* Native HEIF path: CP B+CC -> packet+2B4 -> CamMP ctx+3BC -> imported YC
 * ctx+410 -> native SDF input PIN. The RAW pixel geometry precedes these YC
 * fields and is preserved. RAW auxiliary descriptors also alias this union;
 * their later native import/resize lifecycle needs separate verification.
 * SCN/THM source geometry is copied in the same HEIF-specific union. Native
 * LIRO output geometry must be paired with this adapter (separate manifest).
 */
void *aspect_heif_packet_copy(void *destination, const void *source, uint32_t length,
                             uintptr_t task)
{
    void *result=((void *(*)(void *,const void *,uint32_t))0x5861f8)
        (destination,source,length);
    if (length!=0x25c || (uintptr_t)source!=task+0x55a4 ||
        (read32(task+0x53e8)!=4 && read32(task+0x53f0)!=4)) return result;
    uint32_t id=aspect_task_id(task);
    if (id) {
        aspect_geometry *geo=(aspect_geometry *)((uint8_t *)destination+0xcc);
        aspect_crop_geometry(geo,id,0,geo);
        geo=(aspect_geometry *)((uint8_t *)destination+0xec);
        aspect_crop_geometry(geo,id|ASPECT_GEOMETRY_AUX,0,geo);
        geo=(aspect_geometry *)((uint8_t *)destination+0x10c);
        aspect_crop_geometry(geo,id|ASPECT_GEOMETRY_AUX,0,geo);
    }
    return result;
}
