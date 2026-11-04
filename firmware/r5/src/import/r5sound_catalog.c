/* Sound persistence is deliberately independent of playback ownership. */
#include "r5sound_catalog.h"
#include <string.h>
#define ROW 296u
static uint32_t catalog_get(const uint8_t*p){return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void catalog_put(uint8_t*p,uint32_t x){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(x>>(8*i));}
static void catalog_logit(const r5sound_storage*s,const char*stage,const char*name,int rc,uint32_t a,uint32_t b){if(s->log)s->log(s->ctx,stage,name,rc,a,b);}
void r5sound_blob_name(const uint8_t sha[32],char out[76]){
 static const char hex[]="0123456789abcdef";memcpy(out,"R5SN_",5);
 for(unsigned i=0;i<32;i++){out[5+2*i]=hex[sha[i]>>4];out[6+2*i]=hex[sha[i]&15];}
 memcpy(out+69,".R5S",5);
}
static int valid_entry(const r5sound_entry*e){
 size_t n=0;while(n<256&&e->name[n])n++;
 if(n==256||!ss_valid_name(e->name,n)||e->card>1||e->bytes<R5SOUND_PACKAGE_HEADER_BYTES+320u||e->bytes>R5SOUND_PACKAGE_MAX_BYTES)return 0;
 for(size_t i=n;i<256;i++)if(e->name[i])return 0;
 return 1;
}
int r5sound_catalog_decode(const uint8_t*p,size_t n,r5sound_catalog*c){
 if(!p||!c||n<32||memcmp(p,"R5SNDIDX",8)||catalog_get(p+8)!=2||catalog_get(p+12)>R5SOUND_MAX_FILES||catalog_get(p+16)!=ROW||catalog_get(p+20)!=n||catalog_get(p+24)!=ss_crc32(p+32,n-32)||catalog_get(p+28))return R5SOUND_BAD;
 uint32_t count=catalog_get(p+12);if(n!=32+(size_t)count*ROW)return R5SOUND_BAD;
 /* Validate every row before publishing any catalog state. */
 for(unsigned i=0;i<count;i++){
  const uint8_t*q=p+32+i*ROW;r5sound_entry e;
  memcpy(e.name,q,256);memcpy(e.sha,q+256,32);e.bytes=catalog_get(q+288);e.card=catalog_get(q+292);
  if(!valid_entry(&e))return R5SOUND_BAD;
  for(unsigned j=0;j<i;j++)if(e.card==catalog_get(p+32+j*ROW+292)&&!memcmp(e.name,p+32+j*ROW,256))return R5SOUND_BAD;
 }
 memset(c,0,sizeof(*c));c->count=count;
 for(unsigned i=0;i<count;i++){
  const uint8_t*q=p+32+i*ROW;r5sound_entry*e=&c->entries[i];
  memcpy(e->name,q,256);memcpy(e->sha,q+256,32);e->bytes=catalog_get(q+288);e->card=catalog_get(q+292);
 }
 return 0;
}
size_t r5sound_catalog_encode(const r5sound_catalog*c,uint8_t*p,size_t cap){
 if(!c||!p||c->count>R5SOUND_MAX_FILES)return 0;
 size_t n=32+(size_t)c->count*ROW;if(cap<n)return 0;
 memset(p,0,n);memcpy(p,"R5SNDIDX",8);catalog_put(p+8,2);catalog_put(p+12,c->count);catalog_put(p+16,ROW);catalog_put(p+20,(uint32_t)n);
 for(unsigned i=0;i<c->count;i++){
  const r5sound_entry*e=&c->entries[i];if(!valid_entry(e))return 0;
  uint8_t*q=p+32+i*ROW;memcpy(q,e->name,256);memcpy(q+256,e->sha,32);catalog_put(q+288,e->bytes);catalog_put(q+292,e->card);
 }
 catalog_put(p+24,ss_crc32(p+32,n-32));return n;
}
int r5sound_catalog_load(const r5sound_storage*s,r5sound_catalog*c,uint8_t*p,size_t cap){
 if(!s||!s->read||!c||!p)return R5SOUND_BAD;
 size_t n=0;int rc=s->read(s->ctx,"R5SOUND.IDX",p,cap,&n);
 if(rc==1){memset(c,0,sizeof(*c));return R5SOUND_ABSENT;}
 if(rc)return R5SOUND_IO;
 return r5sound_catalog_decode(p,n,c);
}
int r5sound_catalog_add(const r5sound_storage*s,r5sound_catalog*c,unsigned card,const char*name,size_t nb,const uint8_t*package,size_t bytes){
 r5sound_package_info info;
 if(!s||!s->write_atomic||!c||c->count>R5SOUND_MAX_FILES||card>1||!ss_valid_name(name,nb))return R5SOUND_BAD;
 int valid=r5sound_package_validate(package,bytes,&info);
 if(valid)return valid==-2?R5SOUND_IO:R5SOUND_BAD;
 if(c->count==R5SOUND_MAX_FILES){catalog_logit(s,"CAPACITY",name,R5SOUND_FULL,c->count,0);return R5SOUND_FULL;}
 for(unsigned i=0;i<c->count;i++)if(c->entries[i].card==card&&c->entries[i].name[nb]==0&&!memcmp(c->entries[i].name,name,nb))return R5SOUND_BAD;
 /* The fixed header commits to all ten payload hashes. Its SHA identity
  * permits later selection to verify one volume without hashing other nine. */
 r5sound_entry e;memset(&e,0,sizeof e);memcpy(e.name,name,nb);e.card=card;e.bytes=(uint32_t)bytes;if(ss_sha256(package,R5SOUND_PACKAGE_HEADER_BYTES,e.sha))return R5SOUND_IO;
 char path[76];r5sound_blob_name(e.sha,path);
 int rc=s->write_atomic(s->ctx,path,package,bytes);catalog_logit(s,"PACKAGE_SAVE",e.name,rc,e.bytes,card);
 if(rc)return R5SOUND_IO;
 c->entries[c->count++]=e;return 0;
}
static int compare(const r5sound_entry*a,const r5sound_entry*b){if(a->card!=b->card)return a->card<b->card?-1:1;for(unsigned i=0;i<256;i++){if((unsigned char)a->name[i]!=(unsigned char)b->name[i])return (unsigned char)a->name[i]<(unsigned char)b->name[i]?-1:1;if(!a->name[i])return 0;}return 0;}
int r5sound_catalog_publish(const r5sound_storage*s,r5sound_catalog*c,const r5sound_catalog*old,uint8_t*p,size_t cap){
 if(!s||!s->write_atomic||!c||!c->count)return R5SOUND_BAD;
 for(unsigned i=1;i<c->count;i++){r5sound_entry e=c->entries[i];unsigned j=i;while(j&&compare(&e,&c->entries[j-1])<0){c->entries[j]=c->entries[j-1];j--;}c->entries[j]=e;}
 size_t n=r5sound_catalog_encode(c,p,cap);if(!n)return R5SOUND_BAD;
 int rc=s->write_atomic(s->ctx,"R5SOUND.IDX",p,n);catalog_logit(s,"CATALOG_SAVE",0,rc,c->count,(uint32_t)n);
 if(rc)return R5SOUND_IO;
 /* Only the previous cold-start manifest's known blobs may be retired.
  * Orphans from a failed transaction are not guessed or broadly unlinked. */
 if(old&&s->remove)for(unsigned i=0;i<old->count;i++){
  unsigned keep=0;for(unsigned j=0;j<c->count;j++)if(!memcmp(old->entries[i].sha,c->entries[j].sha,32))keep=1;
  if(!keep){char path[76];r5sound_blob_name(old->entries[i].sha,path);int r=s->remove(s->ctx,path);if(r)catalog_logit(s,"OLD_PACKAGE_REMOVE",old->entries[i].name,r,i,0);}
 }
 return 0;
}
int r5sound_catalog_audio(const r5sound_storage*s,const r5sound_entry*e,unsigned volume,uint8_t*p,size_t cap,size_t*n){
 if(!s||!s->audio||!e||!p||!n||!valid_entry(e)||volume<1||volume>10||cap<R5SOUND_STAGING_BYTES)return R5SOUND_BAD;
 char path[76];r5sound_blob_name(e->sha,path);
 return s->audio(s->ctx,path,e->sha,e->bytes,volume,p,cap,n)?R5SOUND_IO:0;
}
int r5sound_selection_load(const r5sound_storage*s,const r5sound_catalog*c,unsigned*out){
 uint8_t p[48];size_t n=0;if(!s||!s->read||!c||!out)return R5SOUND_BAD;
 *out=0;int rc=s->read(s->ctx,"R5SOUND.SEL",p,sizeof p,&n);if(rc==1)return 0;
 if(rc||n!=48||memcmp(p,"R5SNDSEL",8)||catalog_get(p+8)!=1||catalog_get(p+44)!=ss_crc32(p,44))return R5SOUND_BAD;
 for(unsigned i=0;i<c->count;i++)if(!memcmp(p+12,c->entries[i].sha,32)){*out=i+1;break;}
 return 0;
}
int r5sound_selection_save(const r5sound_storage*s,const r5sound_catalog*c,unsigned index){
 if(!s||!s->write_atomic||!c||index>c->count)return R5SOUND_BAD;
 uint8_t p[48]={0};memcpy(p,"R5SNDSEL",8);catalog_put(p+8,1);if(index)memcpy(p+12,c->entries[index-1].sha,32);catalog_put(p+44,ss_crc32(p,44));
 return s->write_atomic(s->ctx,"R5SOUND.SEL",p,sizeof p)?R5SOUND_IO:0;
}

/* One shutter slot. Like M4 the independent volume is a checksummed sidecar;
 * R5 reuses the existing worker's verified atomic-file transaction. */
int r5sound_volume_load(const r5sound_storage*s,unsigned*out){
 uint8_t p[20];size_t n=0;if(!s||!s->read||!out)return R5SOUND_BAD;
 *out=5;int rc=s->read(s->ctx,"R5SOUND.VOL",p,sizeof p,&n);if(rc==1)return 0;
 if(rc||n!=20||memcmp(p,"R5SNDVOL",8)||catalog_get(p+8)!=1||catalog_get(p+12)<1||catalog_get(p+12)>10||catalog_get(p+16)!=ss_crc32(p,16))return R5SOUND_BAD;
 *out=catalog_get(p+12);return 0;
}
int r5sound_volume_save(const r5sound_storage*s,unsigned step){
 if(!s||!s->write_atomic||step<1||step>10)return R5SOUND_BAD;
 uint8_t p[20];memcpy(p,"R5SNDVOL",8);catalog_put(p+8,1);catalog_put(p+12,step);catalog_put(p+16,ss_crc32(p,16));
 return s->write_atomic(s->ctx,"R5SOUND.VOL",p,sizeof p)?R5SOUND_IO:0;
}
