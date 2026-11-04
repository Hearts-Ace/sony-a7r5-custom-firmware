#include "r5_shutter.h"
#include <string.h>
static int enter(r5ss_scheduler*s){uint32_t z=0;return __atomic_compare_exchange_n(&s->gate,&z,1,0,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED);}
static void leave(r5ss_scheduler*s){__atomic_store_n(&s->gate,0,__ATOMIC_RELEASE);}
static int equal(r5ss_exposure a,r5ss_exposure b){return a.seq==b.seq&&a.member==b.member&&a.ordinal==b.ordinal;}
void r5ss_init(r5ss_scheduler*s){if(s)memset(s,0,sizeof(*s));}
int r5ss_expose(r5ss_scheduler*s,r5ss_exposure e){
 if(!s)return R5SS_INVALID;
 if(!enter(s)){__atomic_add_fetch(&s->contended,1,__ATOMIC_RELAXED);return R5SS_BUSY;}
 for(uint32_t i=0;i<s->used;i++)if(equal(e,s->seen[i])){s->duplicates++;leave(s);return R5SS_OK;}
 s->seen[s->next]=e;s->next=(s->next+1)&63;if(s->used<64)s->used++;
 if(s->audible&&s->wanted_generation&&!s->fault){if(s->serial!=__atomic_load_n(&s->consumed,__ATOMIC_ACQUIRE))s->coalesced++;__atomic_add_fetch(&s->serial,1,__ATOMIC_RELEASE);s->accepted++;}
 leave(s);return R5SS_OK;
}
int r5ss_configure(r5ss_scheduler*s,uint32_t gen,uint32_t audible){
 if(!s||audible>1)return R5SS_INVALID;if(!enter(s))return R5SS_BUSY;
 if(gen!=s->wanted_generation||audible!=s->audible){__atomic_store_n(&s->consumed,s->serial,__ATOMIC_RELEASE);s->wanted_generation=gen;s->audible=audible;}
 leave(s);return R5SS_OK;
}
int r5ss_session(r5ss_scheduler*s){
 if(!s)return R5SS_INVALID;if(!enter(s))return R5SS_BUSY;
 s->installed_generation=0;s->fault=0;s->stop_sent=0;__atomic_store_n(&s->consumed,s->serial,__ATOMIC_RELEASE);s->used=s->next=0;leave(s);return R5SS_OK;
}
int r5ss_reset_retired(r5ss_scheduler*s){
 if(!s)return R5SS_INVALID;if(!enter(s))return R5SS_BUSY;
 if(s->audible||s->wanted_generation){leave(s);return R5SS_INVALID;}
 s->installed_generation=0;s->fault=0;s->stop_sent=0;
 __atomic_store_n(&s->consumed,s->serial,__ATOMIC_RELEASE);
 s->used=s->next=0;leave(s);return R5SS_OK;
}
static int failed(r5ss_scheduler*s){if(!enter(s))return R5SS_BUSY;__atomic_store_n(&s->fault,1,__ATOMIC_RELEASE);s->failures++;__atomic_store_n(&s->consumed,s->serial,__ATOMIC_RELEASE);leave(s);return R5SS_NATIVE;}
int r5ss_tick(r5ss_scheduler*s,const r5ss_ops*o){
 if(!s||!o||!o->poll||!o->stop||!o->authorize||!o->install||!o->start)return R5SS_INVALID;
 if(!enter(s))return R5SS_BUSY;
 uint32_t gen=s->wanted_generation,serial=s->serial,audible=s->audible,pending=serial!=__atomic_load_n(&s->consumed,__ATOMIC_ACQUIRE),fault=s->fault,stop=s->stop_sent,installed=s->installed_generation;leave(s);
 if(fault)return R5SS_NATIVE;
 int r=o->poll(o->ctx);if(r<0)return failed(s);
 if(r>0){
  if((pending||!audible||!gen||gen!=installed)&&!stop){
   int stopped=o->stop(o->ctx);if(stopped<0)return failed(s);if(stopped)return R5SS_BUSY;
   /* All scheduler/config operations are on one worker. Only expose races. */
   s->stop_sent=1;s->stops++;
  }
  return R5SS_BUSY;
 }
 s->stop_sent=0;
 if(!audible||!gen||!pending)return R5SS_OK;
 if(gen!=installed){r=o->install(o->ctx,gen);if(r<0)return failed(s);if(r>0)return R5SS_BUSY;s->installed_generation=gen;}
 /* Snapshot latest event after any asynchronous install. */
 serial=__atomic_load_n(&s->serial,__ATOMIC_ACQUIRE);
 r=o->authorize(o->ctx);if(r<0)return failed(s);if(!r){__atomic_store_n(&s->consumed,serial,__ATOMIC_RELEASE);return R5SS_OK;}
 r=o->start(o->ctx,gen,serial);if(r<0)return failed(s);if(r>0)return R5SS_BUSY;
 __atomic_store_n(&s->consumed,serial,__ATOMIC_RELEASE);s->starts++;return R5SS_OK;
}
