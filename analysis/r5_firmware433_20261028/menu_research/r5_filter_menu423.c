/* 4.23 private-menu foundation. No camera or media IO in any UI callback.
 * Native registry constructor and vtable remaps are listed in menu_hooks.json.
 * This file does not claim a complete two-column screen; the final renderer
 * and return-event integration must be established separately before release. */
#include "r5_filter_menu423.h"
extern unsigned r5_filter_selected(void);
extern int r5_filter_request(unsigned);
extern uint32_t r5_filter_available_mask(void);
extern const char *r5_filter_short_name(unsigned);
extern const char *r5_filter_full_name(unsigned);
extern const char *r5_filter_page_text425(unsigned);
extern const unsigned char r5_native_menu_template[0xc0];
extern const unsigned char r5_native_row_template[0x80];
extern void r5_native_menu_insert(void *,const void *,const void *);
extern void r5_native_row_insert(void *,const void *,const void *);
extern unsigned r5_native_menu_normalize(void *,unsigned);
extern unsigned r5_native_row_normalize(void *,unsigned);
extern unsigned r5_native_row_available(void *,unsigned);
extern unsigned r5_native_row_available_direct(void *,unsigned);
extern unsigned r5_native_row_parent(void *,unsigned);
extern void name_id(void *,unsigned);
extern void name_char(void *,const char *);
unsigned char r5_filter_menu_descriptor[0xc0] __attribute__((aligned(8)));
unsigned char r5_filter_menu_rows[R5_FILTER_ROW_COUNT][0x80] __attribute__((aligned(8)));
struct pair {uint64_t key;const void *pointer;};
static struct pair menu_pair,row_pairs[R5_FILTER_ROW_COUNT];
static unsigned initialized;
static void copy(unsigned char *d,const unsigned char *s,unsigned n){while(n--)*d++=*s++;}
static void put32(unsigned char *d,unsigned off,uint32_t v){
 d[off]=(unsigned char)v;d[off+1]=(unsigned char)(v>>8);d[off+2]=(unsigned char)(v>>16);d[off+3]=(unsigned char)(v>>24);
}
static void putptr(unsigned char *d,unsigned off,const void *v){
 uintptr_t n=(uintptr_t)v;unsigned i;for(i=0;i<sizeof n;i++)d[off+i]=(unsigned char)(n>>(8*i));
}
static unsigned yes(void){return 1;}
static unsigned no(void){return 0;}
static void initialize(void){
 unsigned n;unsigned char *d=r5_filter_menu_descriptor;
 if(initialized)return;
 copy(d,r5_native_menu_template,0xc0);
 put32(d,0,R5_FILTER_TITLE_RESOURCE);
 /* Reuse stock Creative Look descriptor 0x5858b08 +0x0c. The menu
  * glyph and Fn fallback glyph share the existing native image resource. */
 put32(d,4,~0u);put32(d,8,~0u);put32(d,0x0c,0x021c6410u);put32(d,0x10,~0u);
 put32(d,0x18,~0u);put32(d,0x1c,~0u);
 /* 0x2ed is native scr7001_1005, the ordinary row-selection screen.
  * d4 in the copied source template is the dedicated DRO screen. */
 put32(d,0x20,0xd9u);put32(d,0x24,0xd9u);
 put32(d,0x54,R5_FILTER_ROW_COUNT);putptr(d,0x58,r5_filter_menu_rows);
 put32(d,0x60,0x021c6410u);put32(d,0x64,0x39fcu);
 putptr(d,0x70,(const void *)yes);
 putptr(d,0x78,(const void *)r5_filter_menu_selected);
 putptr(d,0x80,(const void *)r5_filter_menu_select);
 putptr(d,0x88,(const void *)r5_filter_menu_select);
 putptr(d,0x90,0);putptr(d,0x98,0);putptr(d,0xa0,0);
 putptr(d,0xa8,(const void *)no);putptr(d,0xb0,0);
 menu_pair.key=R5_FILTER_MENU_ID;menu_pair.pointer=d;
 for(n=0;n<R5_FILTER_ROW_COUNT;n++){
  unsigned char *r=r5_filter_menu_rows[n];copy(r,r5_native_row_template,0x80);
  put32(r,0,R5_FILTER_ROW_FIRST+n);put32(r,4,R5_FILTER_ROW_FIRST+n);
  put32(r,8,R5_FILTER_SHORT_RESOURCE+n);put32(r,0xc,~0u);
  put32(r,0x10,~0u);put32(r,0x14,~0u);
  /* +0x18 is the screen opened after selecting this row, not its parent.
   * The independent native parent map is wrapped below. Sentinel 0x4cf
   * makes native 1005 Enter close once and then call descriptor +0x88. */
  put32(r,0x18,0x4cfu);
  put32(r,0x20,~0u);put32(r,0x24,~0u);put32(r,0x28,~0u);put32(r,0x2c,~0u);
  put32(r,0x34,n);put32(r,0x38,0x39fcu);
  /* Native null primary/secondary prohibition and sub-row sentinels. */
  r[0x74]=0x86;r[0x75]=0x10;r[0x76]=0x12;r[0x77]=0;
  r[0x78]=0x4f;r[0x79]=0;put32(r,0x7c,0);
  /* 0x36 is the native nullable callback-index sentinel, not a PID getter. */
  r[0x6c]=0x36;r[0x6d]=0;r[0x6e]=0x36;r[0x6f]=0;
  row_pairs[n].key=R5_FILTER_ROW_FIRST+n;row_pairs[n].pointer=r;
 }
 initialized=1;
}
void r5_filter_menu_register(void *m,const void *begin,const void *end){
 initialize();r5_native_menu_insert(m,begin,end);r5_native_menu_insert(m,&menu_pair,&menu_pair+1);
}
void r5_filter_rows_register(void *m,const void *begin,const void *end){
 initialize();r5_native_row_insert(m,begin,end);r5_native_row_insert(m,row_pairs,row_pairs+R5_FILTER_ROW_COUNT);
}
unsigned r5_filter_menu_normalize(void *self,unsigned id){
 return id==R5_FILTER_MENU_ID?id:r5_native_menu_normalize(self,id);
}
unsigned r5_filter_row_normalize(void *self,unsigned id){
 return id-R5_FILTER_ROW_FIRST<R5_FILTER_ROW_COUNT?id:r5_native_row_normalize(self,id);
}
static unsigned row_available(unsigned id){
 unsigned n=id-R5_FILTER_ROW_FIRST;
 return n==0 || (n<R5_FILTER_ROW_COUNT && ((r5_filter_available_mask()>>(n-1))&1u));
}
unsigned r5_filter_row_available(void *self,unsigned id){
 return id-R5_FILTER_ROW_FIRST<R5_FILTER_ROW_COUNT?row_available(id):r5_native_row_available(self,id);
}
unsigned r5_filter_row_available_direct(void *self,unsigned id){
 return id-R5_FILTER_ROW_FIRST<R5_FILTER_ROW_COUNT?row_available(id):r5_native_row_available_direct(self,id);
}
unsigned r5_filter_row_parent(void *self,unsigned id){
 return id-R5_FILTER_ROW_FIRST<R5_FILTER_ROW_COUNT?R5_FILTER_MENU_ID:r5_native_row_parent(self,id);
}
unsigned r5_filter_menu_selected(void){return r5_filter_selected();}
void r5_filter_menu_select(unsigned n){
 if(n-R5_FILTER_ROW_FIRST<R5_FILTER_ROW_COUNT)n-=R5_FILTER_ROW_FIRST;
 if(n<R5_FILTER_ROW_COUNT && (n==0 || ((r5_filter_available_mask()>>(n-1))&1u)))
  (void)r5_filter_request(n);
}
const char *r5_filter_menu_text(unsigned id){
 unsigned n;
 const char *page=r5_filter_page_text425(id);if(page)return page;
 if(id==R5_FILTER_TITLE_RESOURCE)return "自定义滤镜";
 n=id-R5_FILTER_SHORT_RESOURCE;
 if(n<R5_FILTER_ROW_COUNT)return n?r5_filter_short_name(n):"关闭";
 n=id-R5_FILTER_FULL_RESOURCE;
 if(n<R5_FILTER_ROW_COUNT)return n?r5_filter_full_name(n):"关闭";
 return 0;
}
void r5_filter_menu_name_draw(void *sprite,unsigned id){
 const char *s=r5_filter_menu_text(id);
 if(s)name_char(sprite,s);else name_id(sprite,id);
}
