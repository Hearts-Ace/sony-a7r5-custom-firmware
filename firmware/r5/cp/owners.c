/* Native-object parameter leases. This module has no allocation, timeout,
 * implicit eviction or global-current fallback in any image consumer. */
#include "context.h"
#include "control.h"
#include "owners.h"
#define LOAD(p) __atomic_load_n((p),__ATOMIC_ACQUIRE)
#define STORE(p,v) __atomic_store_n((p),(v),__ATOMIC_RELEASE)
#define FN(a,t) ((t)(uintptr_t)(a))
#define CLAIMED 0x80000000u
extern void od_grid_forget_range(uintptr_t,uint32_t);
static unsigned task_index(uintptr_t object){
 uintptr_t base=*(volatile uint32_t *)0x1112c64u;
 unsigned count=*(volatile uint32_t *)0x1112c58u;
 if(!base||!count||count>OD_TASKS||object<base||object-base>=count*0x6688u)return OD_TASKS;
 uintptr_t offset=object-base;
 /* Covers native fields embedded in this object, not only its base.
  * The caller's source/target field must lie inside the actual pool range. */
 unsigned index=0;
 for(unsigned bit=256;bit;bit>>=1){uintptr_t step=0x6688u*bit;if(offset>=step){offset-=step;index+=bit;}}
 return index<count?index:OD_TASKS;
}
int od_pool_field(uintptr_t field){return task_index(field)<OD_TASKS;}
static uint32_t *pool_owner(uintptr_t field){
 unsigned index=task_index(field);
 return index<OD_TASKS?&OD_STATE->owners.tasks[index]:0;
}
const struct od_context *od_ticket_pin(uint32_t t,struct r5g_lease *lease){
 *lease=r5g_pin(&OD_STATE->submit.pool,t);return lease->data;
}
void od_work_drop(struct r5g_lease *lease){r5g_drop(&OD_STATE->submit.pool,lease);}
const struct od_context *od_field_pin(uintptr_t field,struct r5g_lease *out){
 *out=(struct r5g_lease){0,0};
 uint32_t *owner=pool_owner(field);
 if(owner){(void)r5g_owner_read(&OD_STATE->submit.pool,owner,out);return out->data;}
 for(unsigned i=0;i<OD_OWNER_FIELDS;i++){
  struct od_field_owner *f=&OD_STATE->owners.fields[i];
  if(LOAD(&f->field)!=field)continue;
  if(r5g_owner_read(&OD_STATE->submit.pool,&f->ticket,out)!=R5G_OK)return 0;
  if(LOAD(&f->field)==field)return out->data;
  od_work_drop(out);return 0;
 }
 return 0;
}
const struct od_context *od_work_pin(const uint32_t *work,struct r5g_lease *out){
 if(!work||!work[0]){*out=(struct r5g_lease){0,0};return 0;}
 return od_field_pin(work[0],out);
}
int od_field_take(uintptr_t field,struct r5g_lease *owned){
 if(!field||(field&CLAIMED))return 0;
 uint32_t *owner=pool_owner(field);
 if(owner){r5g_owner_replace(&OD_STATE->submit.pool,owner,owned);return 1;}
 struct od_field_owner *empty=0;
 for(unsigned i=0;i<OD_OWNER_FIELDS;i++){
  struct od_field_owner *f=&OD_STATE->owners.fields[i];
  uint32_t key=LOAD(&f->field);
  if(key==field){
   if(!__atomic_compare_exchange_n(&f->field,&key,field|CLAIMED,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))return 0;
   uint32_t keep=owned->ticket;
   r5g_owner_replace(&OD_STATE->submit.pool,&f->ticket,owned);
   STORE(&f->field,keep?field:0);return 1;
  }
  if(!key&&!empty)empty=f;
 }
 /* Stock writes need no empty registry entry. Existing references are
  * retired at the native replacement boundary above. */
 if(!owned->ticket)return 1;
 if(!empty)return 0;
 uint32_t key=0;
 if(!__atomic_compare_exchange_n(&empty->field,&key,field|CLAIMED,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))return 0;
 r5g_owner_replace(&OD_STATE->submit.pool,&empty->ticket,owned);
 STORE(&empty->field,field);return 1;
}
int od_field_copy(uintptr_t dst,uintptr_t src){
 struct r5g_lease lease;od_field_pin(src,&lease);
 int result=od_field_take(dst,&lease);od_work_drop(&lease);return result;
}
void od_field_clear(uintptr_t field){
 uint32_t *owner=pool_owner(field);struct r5g_lease zero={0,0};
 if(owner){r5g_owner_replace(&OD_STATE->submit.pool,owner,&zero);return;}
 for(unsigned i=0;i<OD_OWNER_FIELDS;i++){
  struct od_field_owner *f=&OD_STATE->owners.fields[i];uint32_t key=LOAD(&f->field);
  if(key!=field)continue;
  if(!__atomic_compare_exchange_n(&f->field,&key,field|CLAIMED,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))return;
  r5g_owner_replace(&OD_STATE->submit.pool,&f->ticket,&zero);
  STORE(&f->field,0);return;
 }
}
void od_task_retire(uintptr_t pool,uintptr_t task){
 /* The only production caller is inside the acquired native pool lock and
  * immediately before the free-list write. Never trust its outer bool. */
 if(pool==0x1112c54u){od_field_clear(task);od_grid_forget_range(task,0x6688u);}
}
void od_owners_pool_reset(uintptr_t pool){
 if(pool!=0x1112c54u)return;
 uintptr_t base=*(volatile uint32_t *)0x1112c64u;unsigned count=*(volatile uint32_t *)0x1112c58u;
 if(base&&count<=OD_TASKS)od_grid_forget_range(base,count*0x6688u);
 struct r5g_lease zero={0,0};
 for(unsigned i=0;i<OD_TASKS;i++)r5g_owner_replace(&OD_STATE->submit.pool,&OD_STATE->owners.tasks[i],&zero);
}
void od_color_accept(void){
 struct r5g_lease next;
 if(r5g_owner_read(&OD_STATE->submit.pool,&OD_STATE->submit.current,&next)!=R5G_OK)return;
 (void)od_field_take(0x157aa10u+0xa40u,&next);od_work_drop(&next);
}
static void *memcopy(void *dst,const void *src,uint32_t size){
 return FN(0x5f51bcu,void *(*)(void *,const void *,uint32_t))(dst,src,size);
}
void *od_settings_snapshot(void *dst,const void *src,uint32_t size){
 struct r5g_lease lease;od_field_pin((uintptr_t)src+0xa40u,&lease);
 void *result=memcopy(dst,src,size);
 (void)od_field_take((uintptr_t)dst+0xa40u,&lease);
 od_work_drop(&lease);return result;
}
/* These wrappers compose with the optional aspect module at its original
 * guards and call the same aspect targets before returning to the owner code. */
extern void *od_aspect_freeze(void *,const void *,uint32_t);
extern void od_aspect_capture(void *,const void *);
void *od_freeze_snapshot(void *dst,const void *src,uint32_t size){
 struct r5g_lease lease;od_field_pin((uintptr_t)src+0xa40u,&lease);
 void *result=od_aspect_freeze(dst,src,size);
 if(size==0xdbc)(void)od_field_take((uintptr_t)dst+0xa40u,&lease);
 od_work_drop(&lease);return result;
}
void od_capture_snapshot(void *dst,const void *src){
 struct r5g_lease lease;od_field_pin((uintptr_t)src+0xa40u,&lease);
 od_aspect_capture(dst,src);
 (void)od_field_take((uintptr_t)dst+0x104u,&lease);od_work_drop(&lease);
}
void od_native_frame_end(uintptr_t frame,uint32_t extent){
 for(unsigned i=0;i<OD_OWNER_FIELDS;i++){
  uintptr_t field=LOAD(&OD_STATE->owners.fields[i].field);
  if(field>=frame&&field-frame<extent)od_field_clear(field);
 }
 od_grid_forget_range(frame,extent);
}

/* Exact 0x54-byte native pending container copies retain raw-color owner at
 * container+0x10. Destination may be another fixed snapshot or a stack scope;
 * its caller must retire stack fields before the native frame is reused. */
void *od_pending_snapshot(void *dst,const void *src,uint32_t size){
 struct r5g_lease lease;od_field_pin((uintptr_t)src+0x10u,&lease);
 void *result=memcopy(dst,src,size);
 if(size==0x54)(void)od_field_take((uintptr_t)dst+0x10u,&lease);
 od_work_drop(&lease);return result;
}
