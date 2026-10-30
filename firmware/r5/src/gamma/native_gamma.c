#include "native_gamma.h"
static unsigned base(unsigned i){return ((i<6?0x1f008860u:0x1a594693u)>>((i%6)*5))&31u;}
static unsigned group(unsigned i){return i==2?0:i>=10?9:i>=3?i-1:i;}
static __attribute__((always_inline)) inline void cp(void *to,const void *from,unsigned n){uint8_t *d=to;const uint8_t *s=from;while(n--)*d++=*s++;}
int r5_native_gamma418_begin(struct r5_native_gamma418 *g){
 const uint32_t (*table)[7]=(const void *)0x107e968u;
 const uint32_t (*route)[2]=(const void *)0x107eefcu;
 unsigned i,j,k,id,p;uintptr_t lo=(uintptr_t)g,hi=lo+sizeof(*g);
 if(!g||(lo&3u)||hi<lo||!(hi<=0x107e968u||lo>=0x107efacu)||!(hi<=0xdcc514u||lo>=0xdcc6e4u)||g->ready)return -1;
 /* No pointer table reference is published during this private construction. */
 g->ready=0;g->mask=0;cp(g->table,table,51*7*4);cp(g->route,route,22*2*4);
 cp(g->normal_route,(const void *)0xdcc514u,58*2*4);
 for(i=0;i<12;i++){
  unsigned b=base(i),a=route[b][0],v=route[b][1];
  for(k=0;k<3;k++){
   id=k==2?v:a;p=k?6:0;if(!table[id][p])return -2;
   /* ST/NT and BW/SE share all three original records. Preserve the native
    * source checks and every route, but initialize each record group once. */
   if(i!=2&&i!=11)cp(g->record[group(i)][k],(const void *)(uintptr_t)table[id][p],576);
  }
  id=51+2*i;
  for(j=0;j<7;j++){g->table[id][j]=(uint32_t)(uintptr_t)g->record[group(i)][j==6?1:0];g->table[id+1][j]=j==6?(uint32_t)(uintptr_t)g->record[group(i)][2]:0;}
 }
 g->ready=0x4186b11u;return 0;
}
static int valid_curve(const struct r5_native_gamma418 *g,const uint32_t y[129]){
 unsigned i;uint32_t prev=0;uintptr_t p=(uintptr_t)y,a=(uintptr_t)g;
 if(!g||g->ready!=0x4186b11u||!y||(p&3u)||p>UINT32_MAX-515u||
    (p<a+sizeof(*g)&&p+516u>a))return -1;
 for(i=0;i<129;i++){if(y[i]>131071u||(i&&y[i]<prev)||(!i&&y[i]))return -2;prev=y[i];}
 return 0;
}
int r5_native_gamma418_put(struct r5_native_gamma418 *g,uint32_t one,const uint32_t y[129]){
 unsigned k;int status;
 if(one<1||one>12)return -1;
 if((status=valid_curve(g,y)))return status;
 for(k=0;k<3;k++)cp(g->record[group(one-1)][k],y,516);
 g->mask|=1u<<(one-1);return 0;
}
int r5_native_gamma423_put(struct r5_native_gamma418 *g,const uint32_t y[129]){
 unsigned n;
 if(valid_curve(g,y))return -1;
 for(n=0;n<30;n++)cp((uint8_t *)g->record+n*576u,y,516);
 g->mask|=4095u;return 0;
}
int r5_native_gamma418_seal(struct r5_native_gamma418 *g){
 unsigned i;
 if(!g||g->ready!=0x4186b11u||(g->mask&~4095u))return -1;
 /* Only supplied targets change their native routes; every other base keeps
  * its original IDs, including aliases and all special native semantics. */
 for(i=0;i<12;i++)if(g->mask&(1u<<i)){
  unsigned b=base(i);g->route[b][0]=51+2*i;g->route[b][1]=52+2*i;
 }
 if(g->mask&1u){g->normal_route[0][0]=51;g->normal_route[0][1]=52;}
 __atomic_store_n(&g->ready,0x4186a11u,__ATOMIC_RELEASE);return 0;
}
