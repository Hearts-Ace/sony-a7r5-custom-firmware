/* Two text columns over the source-bound native setting-value list.
 * Native list owns primary strings, row backgrounds and scrolling. Extra
 * strings use the same native constructor, parent attachment and destructor.
 * All callbacks run on the native UI path; no filesystem or CP IO here. */
#include "r5_filter_menu423.h"
#include <stddef.h>
extern void r5_native_list_update_original(void *);
extern void r5_native_list_destroy_original(void *);
extern void r5_native_string_construct(void *,const void *);
extern void r5_native_string_destroy(void *);
extern void r5_native_child_attach(void *,void *);
extern int r5_osal_alloc(uint32_t,void **,uint32_t,uint32_t);
extern int r5_osal_free(uint32_t,void *);
#define STRING_SIZE 0xa50u
#define PARAM_SIZE 0x650u
#define ROWS 7u
struct extra {
 struct extra *next;
 void *owner;
 unsigned char strings[ROWS][STRING_SIZE] __attribute__((aligned(8)));
};
static struct extra *extras;
static unsigned allocation_failures;
static uint32_t get32(const void *v,unsigned off){return *(const uint32_t *)((const unsigned char *)v+off);}
static void set32(void *v,unsigned off,uint32_t n){*(uint32_t *)((unsigned char *)v+off)=n;}
static void copy(void *v,const void *s,unsigned n){unsigned char *d=v;const unsigned char *p=s;while(n--)*d++=*p++;}
static void run(void *obj,unsigned off){void **vt=*(void ***)obj;((void (*)(void *))vt[off/8])(obj);}
static struct extra *find(void *owner){struct extra *e;for(e=extras;e;e=e->next)if(e->owner==owner)return e;return 0;}
static struct extra *create(void *owner){
 struct extra *e=0;unsigned i;unsigned char context[0x30]={0};
 if(r5_osal_alloc(0x90030001u,(void **)&e,sizeof *e,0)||!e){allocation_failures++;return 0;}
 e->owner=owner;e->next=extras;
 copy(context,(unsigned char *)owner+0x1b8,0x18);
 set32(context,0x20,get32(owner,0x1d0));set32(context,0x28,get32(owner,0x1d4));
 for(i=0;i<ROWS;i++){
  r5_native_string_construct(e->strings[i],context);
  r5_native_child_attach(e->strings[i],owner);
 }
 extras=e;return e;
}
static void hide(struct extra *e){unsigned i;for(i=0;i<ROWS;i++){e->strings[i][0x204]=0;run(e->strings[i],0x150);}}
void r5_filter_list_update(void *owner){
 struct extra *e;unsigned i;unsigned char *v=owner;
 r5_native_list_update_original(owner);
 e=find(owner);
 /* row zero is always OFF. This private resource cannot occur in stock rows. */
 if(get32(v,0x334)!=R5_FILTER_SHORT_RESOURCE){if(e)hide(e);return;}
 if(!e)e=create(owner);
 for(i=0;i<ROWS;i++){
  unsigned char *primary=*(unsigned char **)(v+0x289a8+i*8);
  unsigned char *p=primary+0x1d8;unsigned id=get32(p,0x30),n=id-R5_FILTER_SHORT_RESOURCE;
  if(n>=R5_FILTER_ROW_COUNT){if(e){e->strings[i][0x204]=0;run(e->strings[i],0x150);}continue;}
  if(e){
   unsigned char *full=e->strings[i]+0x1d8;unsigned width=get32(p,0x20);
   copy(full,p,PARAM_SIZE);
   set32(full,0x18,get32(p,0x18)+128u);
   set32(full,0x20,width>128u?width-128u:0);
   set32(full,0x30,R5_FILTER_FULL_RESOURCE+n);
   *(void **)(full+0x38)=0;
   /* Each TextSprite receives its own clipped native rectangle. */
   set32(p,0x20,112u);
   run(primary,0x148);run(primary,0x150);
   run(e->strings[i],0x148);run(e->strings[i],0x150);
  }else{
   /* Allocation failure remains an operable native list with full names. */
   set32(p,0x30,R5_FILTER_FULL_RESOURCE+n);run(primary,0x150);
  }
 }
}
void r5_filter_list_destroy(void *owner){
 struct extra **link=&extras,*e;unsigned i;
 while((e=*link)!=0){if(e->owner==owner){
  *link=e->next;
  for(i=ROWS;i;i--)r5_native_string_destroy(e->strings[i-1]);
  (void)r5_osal_free(0x90030001u,e);break;
 }link=&e->next;}
 r5_native_list_destroy_original(owner);
}
