/* 4.29: private Creative-Look D9 shell. Source-bound Sony widgets, no new
 * global resources or changes to the factory Creative Look model. */
#include "r5_filter_menu423.h"
#include <stdint.h>
#include <stddef.h>
extern char r5_filter_page_anchor[];
extern unsigned r5_filter_selected(void);
extern unsigned r5_filter_available_mask(void);
extern int r5_filter_request(unsigned);
extern unsigned r5_filter_command_state(void);
extern unsigned r5_filter_command_sequence(void);
extern const char *r5_filter_short_name(unsigned);
extern int usleep(unsigned);
/* Parent callback runs on the UI thread after the worker commits. */
#define PAGE 0xd9u
#define STATUS_TEXT 0x02ff4501u
#define TITLE_TEXT 0x02ff4502u
#define ROW_TEXT 0x02ff4510u
#define NUM_WIDGETS 34u
struct style {uint32_t w[13];};
struct entry {uint32_t type,pad;uint64_t param;};
struct page_state {
 unsigned initialized,active,focus,status,pending_sequence,closing;
 uintptr_t controller,presenter,manager,parent;
 uint64_t cvt[10],pvt[12];
 struct style styles[2][NUM_WIDGETS];
 uint8_t masks[NUM_WIDGETS];
 /* Private preallocated pool: native factories have a non-NULL contract.
  * Keep R5 parent objects isolated instead of sharing their original pool. */
 uint64_t controller_storage[0x308/8],presenter_storage[0x5a10/8];
};
static struct page_state g;
static uintptr_t last_parent;
typedef uint64_t (*F0)(void);
typedef uint64_t (*F1)(uint64_t);
typedef uint64_t (*F2)(uint64_t,uint64_t);
typedef uint64_t (*F3)(uint64_t,uint64_t,uint64_t);
typedef uint64_t (*F6)(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t);
typedef uint64_t (*F8)(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t);
typedef uint64_t (*FC)(uint64_t,uint32_t,uint64_t,uint64_t,uint32_t,uint64_t,uint64_t,uint64_t);
static uintptr_t bias(void){return (uintptr_t)r5_filter_page_anchor-0x9000000u;}
static uintptr_t A(uintptr_t n){return n+bias();}
static uint32_t r32(uintptr_t p){return *(const uint32_t *)p;}
static uintptr_t r64(uintptr_t p){return *(const uintptr_t *)p;}
static void w32(uintptr_t p,uint32_t v){*(uint32_t *)p=v;}
static void w64(uintptr_t p,uintptr_t v){*(uintptr_t *)p=v;}
static void copy(void *d,const void *s,unsigned n){unsigned char *a=d;const unsigned char *b=s;while(n--)*a++=*b++;}
static void zero(void *d,unsigned n){unsigned char *a=d;while(n--)*a++=0;}
static unsigned mid(void){return r32(((F0)A(0x28a8720))());}
static uint64_t none(uint64_t a,uint64_t b){(void)a;(void)b;return 0;}
/* Native lifecycle ownership survives MID changes and the close request.
 * Only private input/project require the currently interactive menu. */
static unsigned owned(uintptr_t c){return c && c==g.controller && g.manager && r32(c+0x178)==PAGE && r64(c+0x180)==g.manager;}
static unsigned valid(void){return g.active && !g.closing && owned(g.controller) && mid()==R5_FILTER_MENU_ID;}
static void setrect(struct style *s,unsigned x,unsigned y,unsigned w,unsigned h){s->w[10]=x|(y<<16);s->w[11]=w|(h<<16);}
static unsigned orientation(unsigned layout){return layout==0?1u:0u;}
static int project(uintptr_t p);
static uint64_t refresh(uint64_t p,uint64_t paint);
static uint64_t dispatch(uint64_t c,uint64_t message,uint64_t event);
static uint64_t exit_page(uint64_t c,uint64_t message);
static uint64_t relayout(uint64_t p,uint64_t layout);
/* Preallocated objects match the M4 native-pool lifetime: native cleanup,
 * clear ownership, retain storage for the next native construction. */
static void destroy(uint64_t p){if(g.presenter!=p)return;g.presenter=0;((F1)A(0x1cbfb80))(p);}
static void delete_presenter(uint64_t p){destroy(p);}
static void controller_destroy(uint64_t c){if(c!=g.controller)return;g.active=0;g.controller=0;((F1)A(0x22083ec))(c);}
static void controller_delete(uint64_t c){controller_destroy(c);}
static void setup(void){
 unsigned j,i;const unsigned visible[]={0,1,9,11,12,13,16,17,18,19,20,21,22,23,24,25,26,27,28};
 if(g.initialized)return;
 copy(g.cvt,(void *)A(0x58da650),sizeof g.cvt);
 copy(g.pvt,(void *)A(0x58ca660),sizeof g.pvt);
 g.cvt[2]=(uintptr_t)controller_destroy;g.cvt[3]=(uintptr_t)controller_delete;
 g.cvt[4]=(uintptr_t)dispatch;g.cvt[5]=(uintptr_t)none;g.cvt[6]=(uintptr_t)none;g.cvt[7]=(uintptr_t)exit_page;
 /* Object address point is &pvt[2]: +30 is a query, +40 is layout. */
 g.pvt[2]=(uintptr_t)destroy;g.pvt[3]=(uintptr_t)delete_presenter;g.pvt[4]=(uintptr_t)refresh;g.pvt[7]=(uintptr_t)none;g.pvt[10]=(uintptr_t)relayout;
 for(i=0;i<NUM_WIDGETS;i++)g.masks[i]=1;
 /* Background2 intentionally has no Widget, as in the M4 D9 implementation.
  * Mask0 constructs a real Widget; it does not itself mean transparency. */
 for(i=0;i<sizeof visible/sizeof visible[0];i++)g.masks[visible[i]]=0;
 for(j=0;j<2;j++){
  struct style *s=g.styles[j];copy(s,(void *)A(j?0x4060398:0x405fc78),sizeof g.styles[j]);
  /* Native No12 typography for readable full UTF8 names. */
  s[11].w[2]=s[12].w[2];s[11].w[6]=s[12].w[6];
  s[12].w[1]=TITLE_TEXT;s[11].w[1]=R5_FILTER_FULL_RESOURCE;
  s[14].w[1]=0; /* No reload text or touch widget in this page. */
  s[13]=s[11];s[13].w[9]=13u<<16;s[13].w[1]=STATUS_TEXT;
  if(j){
   setrect(&s[12],128,8,496,42);
   setrect(&s[11],128,72,496,184);setrect(&s[13],128,302,496,80);
  }else{
   setrect(&s[12],8,8,464,42);
   setrect(&s[11],8,74,464,184);setrect(&s[13],8,300,464,80);
  }
  for(i=0;i<7;i++){
   unsigned index=i?15+i:9,x=j?8:8,y=(j?64:64)+i*(j?46:70);
   s[index]=s[12];s[index].w[9]=index<<16;s[index].w[1]=ROW_TEXT+i;
   setrect(&s[index],x,y,j?112:150,j?42:62);
   s[22+i]=s[15];s[22+i].w[9]=(22+i)<<16;
   setrect(&s[22+i],x,y,j?112:150,j?42:62);
  }
  /* Right pane starts after the native left list; preview remains behind. */
  if(j){setrect(&s[11],136,74,488,180);setrect(&s[13],136,302,488,80);}
  else{setrect(&s[11],168,74,304,184);setrect(&s[13],168,300,304,80);}
 }
 g.initialized=1;
}
static unsigned char *param(struct entry *map,unsigned n,unsigned type){return map[n].type==type && map[n].param && !(map[n].param&7)?(unsigned char *)(uintptr_t)map[n].param:0;}
static int resource(struct entry *m,unsigned n,unsigned id,unsigned show){unsigned char *p=param(m,n,2);if(!p)return -1;w32((uintptr_t)p+0x30,id);w64((uintptr_t)p+0x38,0);p[0x2c]=show;return 0;}
static unsigned visible_row(unsigned row){
 unsigned list[13],n=1,i,at=0,first,mask=r5_filter_available_mask();list[0]=0;
 for(i=1;i<=12;i++)if(mask&(1u<<(i-1)))list[n++]=i;
 for(i=0;i<n;i++)if(list[i]==g.focus)at=i;
 first=at>3?at-3:0;if(n>7 && first>n-7)first=n-7;if(n<=7)first=0;
 return first+row<n?list[first+row]:~0u;
}
static int project(uintptr_t p){
 struct entry *m;unsigned char *v;unsigned i;
 if(p!=g.presenter || !valid())return 0;
 m=(struct entry *)r64(p+0x48);if(!m)return -1;
 for(i=0;i<7;i++){
  unsigned row=visible_row(i),index=i?15+i:9;
  if(resource(m,index,ROW_TEXT+i,row!=~0u)<0)return -1;
  v=param(m,22+i,0x14);if(!v)return -1;v[0x2c]=row!=~0u;
 }
 if(resource(m,11,R5_FILTER_FULL_RESOURCE+g.focus,1)<0 ||
    resource(m,12,TITLE_TEXT,1)<0 || resource(m,14,0,0)<0 || resource(m,13,STATUS_TEXT,g.status!=0)<0)return -1;
 v=param(m,15,0x14);if(!v)return -1;v[0x2c]=0;
 /* No native Creative Look adjustment, icon, arrow or footer widget is
  * instantiated. The right pane consists only of our full-name String. */
 return 1;
}
static uint64_t refresh(uint64_t p,uint64_t paint){uintptr_t v;if(project(p)!=1)return 0;v=r64(p+0x40);return ((F2)r64(r64(v)+0x20))(v,paint);}
static void close_page(void){
 uintptr_t c=g.controller,m;
 if(!valid() || g.closing)return;
 m=r64(c+0x180);g.closing=1;g.active=0;
 ((F2)r64(r64(m)+0x20))(m,c+0x178);
}
int r5_filter_parent_refresh425(void){
 uintptr_t p=g.parent,map,list;unsigned n,i;
 if(!valid() || !p || r64(p)!=A(0x58c1508) || r32(p+0x38)!=0x2d7u || !r64(p+0x28))return -1;
 /* Exact native 1004 presenter update rebuilds the parent value rows using
  * its native value-producing helper and the committed descriptor getter before the close request is queued. */
 ((F2)A(0x1d90de8))(p,1);
 /* Native 5B main list: producer 1bc3f64 enumerates the displayed menu IDs
  * at 74dc6e8, then writes each value resource at param+80+4*index.
  * Verify the current private row, rather than treating a void paint as ACK. */
 map=r64(p+0x30);if(!map || r32(map+11*16)!=0x5b)return -1;
 list=r64(map+11*16+8);n=r32(A(0x74dc830));if(!list || !n || n>82 || r32(list+0x3b20)!=n)return -1;
 for(i=0;i<n;i++)if(r32(A(0x74dc6e8)+i*4)==R5_FILTER_MENU_ID)
  return r32(list+0x80+i*4)==R5_FILTER_SHORT_RESOURCE+r5_filter_selected()?0:-1;
 return -1;
}
static unsigned wait_command(unsigned sequence){
 unsigned i,s;
 /* IO and E4 execution are worker-owned; UI waits with bounded yielding.
  * Never accept another transaction's completion. */
 for(i=0;i<2000;i++){
  if(sequence!=r5_filter_command_sequence())return 3;
  s=r5_filter_command_state();if(s!=1)return s;
  usleep(10000);
 }
 return 1;
}
static unsigned finish_command(unsigned state){
 if(state==1){g.status=4;return 0;}
 g.pending_sequence=0;
 /* Selection retains one synchronous completion gate:
  * commit, native parent value refresh/postcondition, then exactly one pop. */
 if(state==2){
  g.focus=r5_filter_selected();if(g.focus>12)g.focus=0;g.status=0;
  if(r5_filter_parent_refresh425()==0)close_page();else g.status=3;
 }else g.status=3;
 return 1;
}
static void submit(void){
 unsigned state;
 g.status=1;if(g.presenter)refresh(g.presenter,1);
 if(r5_filter_request(g.focus)!=0){g.status=3;return;}
 g.pending_sequence=r5_filter_command_sequence();state=wait_command(g.pending_sequence);
 (void)finish_command(state);
}
static unsigned next(unsigned direction){
 unsigned n=g.focus,mask=r5_filter_available_mask(),i;
 for(i=0;i<13;i++){
  if(direction){if(n==12)return 0xffffffffu;n++;}
  else{if(!n)return 0xffffffffu;n--;}
  if(!n || (mask&(1u<<(n-1))))return n;
 }
 return 0xffffffffu;
}
static uint64_t dispatch(uint64_t c,uint64_t message,uint64_t event){
 unsigned n,original=(unsigned)event;
 if(!owned(c))return ((F3)A(0x1a6d8cc))(c,message,event);
 /* The native dispatcher maps raw 01/04 transport IDs through two tables.
  * Preserve all other lifecycle messages and borrow the message only here. */
 if((event&0xff000000u)==0x01000000u || (event&0xff000000u)==0x04000000u)
  event=((F1)A(0x1b2932c))(event)|((F1)A(0x1b29374))(event);
 if(!valid()){
  /* Retired private inputs must never reach original Look setters. Native
   * display/close/orientation traffic still uses the actual D9 dispatcher. */
  if((event&0xffff0000u)==0x2010000u || (event&0xffff0000u)==0x2030000u || (event&0xffff0000u)==0x3010000u)return 1;
  return ((F3)A(0x1a6d8cc))(c,message,original);
 }
 /* A bounded wait may return while IO is still pending. Keep ownership of
  * that exact command: no back/second request until it completes. A later UI
  * event polls it and applies the same refresh-before-pop completion path. */
 if(g.pending_sequence && ((event&0xffff0000u)==0x2010000u || (event&0xffff0000u)==0x2030000u || (event&0xffff0000u)==0x3010000u)){
  if(g.pending_sequence!=r5_filter_command_sequence()){g.pending_sequence=0;g.status=3;goto done;}
  n=r5_filter_command_state();(void)finish_command(n);goto done;
 }
 if(event==0x3010002u && message && r32(message)==1 && r32(message+0x18)==PAGE && r32(message+0xc)>=22 && r32(message+0xc)<=28){
  n=visible_row(r32(message+0xc)-22);if(n!=~0u){g.focus=n;submit();}goto done;
 }
 switch((unsigned)event){
 case 0x2010000u:case 0x2010002u:n=next(0);if(n!=~0u)g.focus=n;break;
 case 0x2010003u:case 0x2010005u:n=next(1);if(n!=~0u)g.focus=n;break;
 case 0x2010006u:case 0x2010008u:case 0x2010009u:case 0x201000bu:break;
 case 0x201000cu:submit();break;
 case 0x201000fu:close_page();return 1;
 default:
  /* Private UI events must never enter original Creative Look setters. */
  if((event&0xffff0000u)==0x2010000u || (event&0xffff0000u)==0x2030000u || (event&0xffff0000u)==0x3010000u)return 1;
  return ((F3)A(0x1a6d8cc))(c,message,original);
 }
 done:if(g.presenter && g.active)refresh(g.presenter,1);return 1;
}
static uint64_t exit_page(uint64_t c,uint64_t message){(void)message;if(c==g.controller)g.active=0;return 0;}
uint64_t r5_filter_parent_presenter425(uint64_t i,uint64_t view,uint64_t context,uint64_t pi,uint64_t scene,uint64_t layout){
 uintptr_t p=((F6)A(0x1d90c7c))(i,view,context,pi,scene,layout);
 /* Capture the actually constructed parent, never a stale pool candidate. */
 if(p && scene==0x2d7u && r64(p)==A(0x58c1508) && r32(p+0x38)==0x2d7u)last_parent=p;
 return p;
}
uint64_t r5_filter_controller425(uint64_t i,uint64_t m,uint64_t c,uint64_t s,uint64_t p,uint64_t l){
 uintptr_t object;
 if(mid()!=R5_FILTER_MENU_ID)return ((F6)A(0x1d2e488))(i,m,c,s,p,l);
 if(g.active || i>5 || p>5)return 0;
 setup();g.parent=last_parent;
 object=(uintptr_t)g.controller_storage;
 zero((void *)object,0x308);
 ((F8)A(0x1d2e2f0))(object,m,c,s,p,i,PAGE,l);
 g.controller=object;g.manager=m;g.active=1;g.focus=r5_filter_selected();if(g.focus>12)g.focus=0;
 g.status=0;g.pending_sequence=0;g.closing=0;
 w64(object,(uintptr_t)&g.cvt[2]);return object;
}
uint64_t r5_filter_presenter425(uint64_t i,uint64_t view,uint64_t context,uint64_t pi,uint64_t scene,uint64_t layout){
 uintptr_t p,vt;struct style *style;
 if(mid()!=R5_FILTER_MENU_ID || !valid() || scene!=PAGE || r64(g.controller+0x180)!=g.manager)
  return ((F6)A(0x1e1e1a4))(i,view,context,pi,scene,layout);
 if(i>5 || pi>5)return 0;
 if(g.presenter)return 0;p=(uintptr_t)g.presenter_storage;
 zero((void *)p,0x5a10);style=g.styles[orientation((unsigned)layout)];vt=r64(view);
 w64(p,(uintptr_t)&g.pvt[2]);w32(p+8,layout);w64(p+0x10,(uintptr_t)style);w64(p+0x40,view);
 w64(p+0x48,((F1)r64(vt+0x30))(view));w32(p+0x50,scene);w64(p+0x59e0,context);w32(p+0x59e8,pi);
 ((F3)A(0x1b2ae4c))(p+0x4d30,(uintptr_t)style,NUM_WIDGETS);
 ((F3)A(0x1bc3304))(p+0x5388,(uintptr_t)style,NUM_WIDGETS);
 ((FC)r64(vt+0x10))(view,scene,(uintptr_t)style,NUM_WIDGETS,layout,(uintptr_t)g.masks,A(0x4060b40),A(0x4060ab8));
 g.presenter=p;if(project(p)!=1){g.status=3;return p;}
 ((F1)r64(vt+0x50))(view);((F2)r64(vt+0x20))(view,0);return p;
}
static uint64_t relayout(uint64_t p,uint64_t layout){
 uintptr_t v,vt;unsigned old;struct style *style;
 if(p!=g.presenter || !valid())return 0;
 old=r32(p+8);if(old==layout)return 0;w32(p+8,layout);v=r64(p+0x40);vt=r64(v);
 if(orientation(old)!=orientation(layout)){
  style=g.styles[orientation(layout)];w64(p+0x10,(uintptr_t)style);((F1)r64(vt+0x18))(v);
  ((FC)r64(vt+0x10))(v,PAGE,(uintptr_t)style,NUM_WIDGETS,layout,(uintptr_t)g.masks,A(0x4060b40),A(0x4060ab8));
  if(project(p)==1)((F1)r64(vt+0x50))(v);
 }else ((F2)r64(vt+0x60))(v,layout);
 return 0;
}
const char *r5_filter_page_text425(unsigned id){
 static char rows[7][96];unsigned i,n;const char *s;char *d;
 if(id>=ROW_TEXT && id<ROW_TEXT+7){
  i=id-ROW_TEXT;n=visible_row(i);if(n==~0u)return "";
  d=rows[i];*d++=n==g.focus?'>':(n==r5_filter_selected()?'*':' ');*d++=' ';
  s=n?r5_filter_short_name(n):"关闭";for(i=0;s[i] && i<90;i++)*d++=s[i];*d=0;return rows[id-ROW_TEXT];
 }
 if(id==TITLE_TEXT)return "自定义滤镜";
 if(id==STATUS_TEXT){switch(g.status){case 1:return "正在同步应用…";case 3:return "应用失败，请重试";case 4:return "处理超时，请等待后重试";default:return "";}}
 return 0;
}
