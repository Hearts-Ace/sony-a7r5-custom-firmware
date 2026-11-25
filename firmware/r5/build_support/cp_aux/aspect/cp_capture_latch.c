#define ASPECT_STATE 0x1a394a0u
/* Source-bound CP adapter. Link/test allocation is specified by the builder.
 * Never pass custom IDs to the original RAW/AF/dimension machinery.
 */
#include <stdint.h>
#include "crop_core.h"

#define aspect_selected_custom (*(volatile uint32_t *)(ASPECT_STATE))
/* Native R5 pool: at most490 objects, stride6688. One byte per
 * native slot covers its complete capacity using less RAM than64 pointer/ID
 * pairs. No private fields are written inside the native task object.
 */
#define task_ids ((uint8_t *)(ASPECT_STATE+12u))
#define frozen_id (*(uint32_t *)(ASPECT_STATE+4u))
#define frozen_request (*(uint32_t *)(ASPECT_STATE+8u))
#define aspect_cp_sequence (*(volatile uint32_t *)(ASPECT_STATE-8u))
#define frozen_sequence (*(volatile uint32_t *)(ASPECT_STATE-4u))
#define aspect_cp_selection aspect_selected_custom
#define POOL 0x1112c54u
#define GFW 0x157aa10u
#define REQUEST 0x163f3c8u
#define SNAPSHOT 0x163f3f0u
#define REQUEST_ID 0x5ae8u
extern uint32_t aspect_divide(uint32_t,uint32_t);

static void barrier(void) { __asm__ volatile ("dmb ish" ::: "memory"); }
static uint32_t read32(uintptr_t p) { return *(const volatile uint32_t *)p; }
static uint32_t acquire(const volatile uint32_t *p) { return __atomic_load_n(p, __ATOMIC_ACQUIRE); }

static uint32_t task_index(uintptr_t task)
{
    uintptr_t base=read32(0x1112c64);
    uint32_t count=read32(0x1112c58);
    if (!base || !count || count>490 || task<base) return 490;
    uint32_t offset=task-base,index=aspect_divide(offset,0x6688);
    if (index>=count || index*0x6688!=offset) return 490;
    return index;
}

/* Native pool list construction completes before any object can be popped.
 * Clear once at that original serialized point, including same-base reuse;
 * lookups themselves never reset another task's state.
 */
void aspect_pool_reset(uintptr_t pool)
{
    if (pool==0x1112c54) {
        ((void (*)(void *,uint32_t))0x5f58b0)(task_ids,490u);
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

/* Reference R5: retire only after native linked-list insertion succeeds. */
uint32_t aspect_pool_release(uintptr_t pool, uintptr_t task)
{
    uint32_t available = pool == POOL ? read32(POOL + 8) : 0;
    uint32_t result = ((uint32_t (*)(uintptr_t, uintptr_t))0xae08c9u)(pool, task);
    /* 原生范围检查即使内部等待失败也返回 1；按真实插回链表的结果退休。
     * 此调用点处于原生外层池锁内，尚未向下一分配者释放所有权。 */
    if (result && pool == POOL && read32(POOL) == task && read32(POOL + 8) == available + 1)
        aspect_task_clear(task);
    return result;
}

/* Reference R5: publish only a stable, complete 0xdbc native snapshot. */
void *aspect_freeze_copy(void *destination, const void *source, uint32_t length)
{
    uint32_t sequence = acquire(&aspect_cp_sequence);
    uint32_t id = acquire(&aspect_cp_selection);
    uint32_t request = read32(REQUEST);
    void *result = ((void *(*)(void *, const void *, uint32_t))0x5f51bcu)(destination, source, length);
    if ((uintptr_t)source != GFW || (uintptr_t)destination != SNAPSHOT || length != 0xdbc
        || (sequence & 1u) || sequence != acquire(&aspect_cp_sequence)
        || read32(REQUEST) != request || read32(SNAPSHOT + 0xcc) != 2 || id < 4 || id > 7) id = 0;
    /* 私有编号只会由已准入的接收路径发布；这里不再有可失败分配。 */
    uint32_t publication = frozen_sequence;
    frozen_sequence = publication + 1;
    barrier();
    frozen_request = request;
    frozen_id = id;
    barrier();
    frozen_sequence = publication + 2;
    return result;
}

/* Reference R5: bind only a stable frozen publication and matching request. */
void aspect_capture_copy(void *destination, const void *source)
{
    ((void (*)(void *, const void *))0x4596f5u)(destination, source);
    uintptr_t task = (uintptr_t)destination - 0x20;
    aspect_task_clear(task);
    uint32_t sequence = acquire(&frozen_sequence);
    uint32_t id = frozen_id, request = frozen_request;
    barrier();
    if ((sequence & 1u) || sequence != acquire(&frozen_sequence)
        || (uintptr_t)source != SNAPSHOT || read32(task + 0x24) != 2
        || read32(task + REQUEST_ID) != request || id < 4 || id > 7) return;
    uint32_t index = task_index(task);
    if (index < 490) {
        task_ids[index] = (uint8_t)id;
        barrier();
    }
}

/* Crop only the MainEnc request copy, after LUT/pixel development has finished.
 * Source task geometry and RAW buffers are never modified here.
 */
void *aspect_jpeg_request_copy(void *destination, const void *source, uint32_t length,
                              uintptr_t task)
{
    void *result=((void *(*)(void *, const void *, uint32_t))0x5f51bc)
        (destination, source, length);
    uint32_t id=aspect_task_id(task);
    uintptr_t offset=(uintptr_t)source-task;
    if (length == sizeof(aspect_geometry) && id && (offset==0x5f78 || offset==0x5fdc)
        && (read32(task+0x5980)==1 || read32(task+0x5988)==1 || read32(task+0x5980)==2 || read32(task+0x5988)==2))
        aspect_crop_geometry((const aspect_geometry *)source,id|(offset==0x5fdc ? ASPECT_GEOMETRY_AUX : 0),0,
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
    void *result=((void *(*)(void *,uint32_t))0x5f58b0)(destination,length);
    uint32_t id=aspect_task_id(task);
    if (!id || length!=0x20 || (read32(task+0x3c)&4)
        || (read32(task+0x5980)!=1 && read32(task+0x5988)!=1 && read32(task+0x5980)!=2 && read32(task+0x5988)!=2)) return result;
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


uint32_t aspect_cp_select(uint32_t wire) {
 if (wire>=5u && wire<=8u) {aspect_selected_custom=wire-1u;return 2u;}
 aspect_selected_custom=0;return wire;
}
