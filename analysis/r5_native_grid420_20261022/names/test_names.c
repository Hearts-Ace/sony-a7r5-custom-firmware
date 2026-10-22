#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
static unsigned mask,got_number,got_id,id_calls,char_calls;static void *got_sprite;
static const char *got_text;
static const char text[12][32]={"Look1","Look2","Look3","Look4","Look5","Look6","Look7","Look8","Look9","Look10","Look11","Look12"};
const char *r5_native12_name(unsigned n){got_number=n;return n>=1&&n<=12&&(mask&(1u<<(n-1)))?text[n-1]:0;}
void name_id(void *s,unsigned r){got_sprite=s;got_id=r;id_calls++;}
void name_char(void *s,const char *t){got_sprite=s;got_text=t;char_calls++;}
extern void r5_native12_text_label(void *,unsigned);extern unsigned r5_native12_number_for_resource(unsigned);
#define REQUIRE(c) do{if(!(c)){fprintf(stderr,"failure line%d\n",__LINE__);exit(1);}}while(0)
int main(void){static const unsigned ids[12]={0x21c6e0d,0x21c6e10,0x21c6e14,0x21c6e19,0x21c6e0e,0x21c6e0c,0x21c6e0b,0x21c6e0a,0x21c6e11,0x21c6e12,0x21c6e15,0x21c6e13};unsigned cases=0;
for(mask=0;mask<4096;mask++)for(unsigned i=0;i<12;i++){id_calls=char_calls=0;got_number=0;got_text=0;got_id=0;got_sprite=0;r5_native12_text_label((void*)(uintptr_t)0x12345678,ids[i]);REQUIRE(got_number==i+1);REQUIRE(got_sprite==(void*)(uintptr_t)0x12345678);if(mask&(1u<<i)){REQUIRE(char_calls==1&&id_calls==0&&got_text==text[i]);}else REQUIRE(id_calls==1&&char_calls==0&&got_id==ids[i]);cases++;}
for(unsigned i=0;i<65536;i++){unsigned r=0x2000000+i;REQUIRE(r5_native12_number_for_resource(r)==0);id_calls=char_calls=got_number=0;r5_native12_text_label((void*)(uintptr_t)1,r);REQUIRE(id_calls==1&&!char_calls&&!got_number&&got_id==r);cases++;}
printf("{\"passed\":true,\"cases\":%u,\"all4096Masks\":true,\"nativeResourceCallsAreFixtures\":true}\n",cases);return 0;}
