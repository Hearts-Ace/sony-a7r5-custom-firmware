/* Minimal native option list. Batch SD import is a separate cold-boot job.
 * Row callbacks use the already published internal catalog; no SD enumeration,
 * durable writes, conversion or native sound RPC runs on the native UI path. */
#include "r5_sound_menu437.h"
extern const unsigned char r5_native_menu_template[0xc0];
extern const unsigned char r5_native_row_template[0x80];
extern void r5_native_menu_insert(void *,const void *,const void *);
extern void r5_native_row_insert(void *,const void *,const void *);
struct pair {uint64_t key;const void *pointer;};
unsigned char r5sound_menu_descriptor[0xc0] __attribute__((aligned(8)));
unsigned char r5sound_menu_rows[R5SOUND_ROW_COUNT][0x80] __attribute__((aligned(8)));
unsigned char r5sound_volume_descriptor[0xc0] __attribute__((aligned(8)));
static unsigned char volume_rows[R5SOUND_VOLUME_ROW_COUNT][0x80] __attribute__((aligned(8)));
static struct pair menu_pairs[2],row_pairs[R5SOUND_ROW_COUNT],volume_pairs[R5SOUND_VOLUME_ROW_COUNT];
static unsigned initialized,volume_staged,gui_revision;
static void copy(unsigned char *d,const unsigned char *s,unsigned n){while(n--)*d++=*s++;}
static void put32(unsigned char *d,unsigned off,uint32_t v){for(unsigned i=0;i<4;i++)d[off+i]=(unsigned char)(v>>(8*i));}
static void putptr(unsigned char *d,unsigned off,const void *v){uintptr_t x=(uintptr_t)v;for(unsigned i=0;i<sizeof x;i++)d[off+i]=(unsigned char)(x>>(8*i));}
static unsigned count(void){unsigned n=r5sound_count();return n>R5SOUND_MAX_FILES?R5SOUND_MAX_FILES:n;}
static void refresh(void){if(__atomic_load_n(&initialized,__ATOMIC_ACQUIRE))__atomic_store_n((uint32_t *)(void *)(r5sound_menu_descriptor+0x54),count()+1u,__ATOMIC_RELEASE);}
static unsigned yes(void){refresh();return 1;}
static unsigned no(void){return 0;}
unsigned r5sound_menu_selected(void){unsigned n=r5sound_selected();refresh();return n<=count()?n:0;}
/* Native setter is invoked while browsing. Only accepted alias at +88 commits. */
void r5sound_menu_stage(unsigned raw){(void)raw;}
int r5sound_menu_commit(unsigned alias){unsigned n=alias-R5SOUND_ROW_FIRST;if(n>=R5SOUND_ROW_COUNT||n>count())return -1;return r5sound_request(n);}
unsigned r5sound_volume_menu_get(void){unsigned v=volume_staged;if(!v)v=r5sound_volume_get();return (v>=1&&v<=10?v:5)-1;}
void r5sound_volume_menu_stage(unsigned raw){if(raw<10)volume_staged=raw+1;}
int r5sound_volume_menu_commit(unsigned alias){unsigned n=alias-R5SOUND_VOLUME_ROW_FIRST;int rc=n<10?r5sound_volume_enqueue(n+1):-1;volume_staged=0;return rc;}
unsigned r5sound_menu_gui_changed(void){unsigned revision=r5sound_revision(),changed=volume_staged||revision!=gui_revision;volume_staged=0;gui_revision=revision;return changed;}
unsigned r5sound_menu_row_available(unsigned id){unsigned n=id-R5SOUND_VOLUME_ROW_FIRST;if(n<R5SOUND_VOLUME_ROW_COUNT)return !r5sound_volume_blocked();n=id-R5SOUND_ROW_FIRST;return n<R5SOUND_ROW_COUNT&&n<=count();}
static void table(unsigned char *d,unsigned char rows[][0x80],struct pair *pairs,unsigned first,unsigned names,unsigned title,unsigned help,unsigned total,const void *get,const void *stage,const void *commit,const void *blocked){
 copy(d,r5_native_menu_template,0xc0);
 put32(d,0,title);put32(d,4,~0u);put32(d,8,~0u);
 put32(d,0x0c,help);put32(d,0x10,~0u);
 put32(d,0x18,0x20000001u);put32(d,0x1c,0x20000001u);
 put32(d,0x20,0x2edu);put32(d,0x24,0x4cfu);
 put32(d,0x54,total);putptr(d,0x58,rows);
 put32(d,0x60,0x020048ebu);put32(d,0x64,0x39fcu);
 putptr(d,0x70,(const void *)yes);putptr(d,0x78,get);
 putptr(d,0x80,stage);putptr(d,0x88,commit);
 putptr(d,0x90,0);putptr(d,0x98,0);putptr(d,0xa0,0);putptr(d,0xa8,blocked);putptr(d,0xb0,0);
 for(unsigned n=0;n<total;n++){
  unsigned char *r=rows[n];copy(r,r5_native_row_template,0x80);
  put32(r,0,first+n);put32(r,4,first+n);put32(r,8,names+n);
  put32(r,0xc,~0u);put32(r,0x10,help);put32(r,0x14,~0u);put32(r,0x18,0x4cfu);
  put32(r,0x20,~0u);put32(r,0x24,~0u);put32(r,0x28,~0u);put32(r,0x2c,~0u);
  put32(r,0x34,n);put32(r,0x38,0x39fcu);
  r[0x6c]=0x36;r[0x6d]=0;r[0x6e]=0x36;r[0x6f]=0;
  r[0x74]=0x86;r[0x75]=0x10;r[0x76]=0x12;r[0x77]=0;r[0x78]=0x4f;r[0x79]=0;put32(r,0x7c,0);
  pairs[n].key=first+n;pairs[n].pointer=r;
 }
}
static void initialize(void){
 if(__atomic_load_n(&initialized,__ATOMIC_ACQUIRE))return;
 table(r5sound_menu_descriptor,r5sound_menu_rows,row_pairs,R5SOUND_ROW_FIRST,R5SOUND_NAME_RESOURCE,R5SOUND_TITLE_RESOURCE,R5SOUND_HELP_RESOURCE,R5SOUND_ROW_COUNT,(const void*)r5sound_menu_selected,(const void*)r5sound_menu_stage,(const void*)r5sound_menu_commit,(const void*)no);
 table(r5sound_volume_descriptor,volume_rows,volume_pairs,R5SOUND_VOLUME_ROW_FIRST,R5SOUND_VOLUME_NAME_RESOURCE,R5SOUND_VOLUME_TITLE_RESOURCE,R5SOUND_VOLUME_HELP_RESOURCE,R5SOUND_VOLUME_ROW_COUNT,(const void*)r5sound_volume_menu_get,(const void*)r5sound_volume_menu_stage,(const void*)r5sound_volume_menu_commit,(const void*)r5sound_volume_blocked);
 menu_pairs[0]=(struct pair){R5SOUND_MENU_ID,r5sound_menu_descriptor};menu_pairs[1]=(struct pair){R5SOUND_VOLUME_MENU_ID,r5sound_volume_descriptor};
 __atomic_store_n(&initialized,1,__ATOMIC_RELEASE);refresh();
}
void r5sound_menu_catalog_changed(void){refresh();}
void r5sound_menu_register_extra(void *m){initialize();r5_native_menu_insert(m,menu_pairs,menu_pairs+2);}
void r5sound_rows_register_extra(void *m){initialize();r5_native_row_insert(m,row_pairs,row_pairs+R5SOUND_ROW_COUNT);r5_native_row_insert(m,volume_pairs,volume_pairs+R5SOUND_VOLUME_ROW_COUNT);}
const char *r5sound_menu_text(unsigned id){
 static const char levels[10][5]={"10%","20%","30%","40%","50%","60%","70%","80%","90%","100%"};
 if(id==R5SOUND_VOLUME_TITLE_RESOURCE)return "自定义快门声音量";
 if(id==R5SOUND_VOLUME_HELP_RESOURCE)return "独立音量10%–100%；默认50%";
 unsigned v=id-R5SOUND_VOLUME_NAME_RESOURCE;if(v<10)return levels[v];
 if(id==R5SOUND_TITLE_RESOURCE)return "自定义快门声";
 if(id==R5SOUND_HELP_RESOURCE){const char *s=r5sound_status();return s&&*s?s:"冷启动导入SD根目录R5S；选择后启用";}
 unsigned n=id-R5SOUND_NAME_RESOURCE;if(n>=R5SOUND_ROW_COUNT)return 0;
 if(!n)return "关闭";
 if(n>count())return "";
 const char *s=r5sound_name(n);return s?s:"";
}
