#include "r5_filter423.h"
#define LOAD(p) __atomic_load_n((p),__ATOMIC_ACQUIRE)
#define STORE(p,v) __atomic_store_n((p),(v),__ATOMIC_RELEASE)
struct names {char short_name[24],full_name[64];};
static struct names versions[16][12];
static uint32_t version_count;
static uint64_t names_header;
int r5_filter_names_publish(const struct r5_look_set *set) {
    uint64_t old=LOAD(&names_header);unsigned i,j,n,same=1;
    uint8_t compact[R5_FILTER_COMPACT];
    if(!set || (set->valid_mask&~4095u))return -1;
    for(i=0;i<12;i++)if((set->valid_mask&(1u<<i)) && !r5_filter_pack_compact(&set->look[i],compact))return -1;
    if(!set->valid_mask){STORE(&names_header,0);return 1;}
    if(old && (uint32_t)old==set->valid_mask) {
        n=(unsigned)(old>>32)-1;
        for(i=0;i<12;i++)if(set->valid_mask&(1u<<i)) {
            for(j=0;j<24;j++)if(versions[n][i].short_name[j]!=set->look[i].short_name[j])same=0;
            for(j=0;j<64;j++)if(versions[n][i].full_name[j]!=set->look[i].full_name[j])same=0;
        }
        if(same)return 1;
    }
    n=version_count;if(n>=16){STORE(&names_header,0);return -2;}
    for(i=0;i<12;i++) {
        for(j=0;j<24;j++)versions[n][i].short_name[j]=(set->valid_mask&(1u<<i))?set->look[i].short_name[j]:0;
        for(j=0;j<64;j++)versions[n][i].full_name[j]=(set->valid_mask&(1u<<i))?set->look[i].full_name[j]:0;
    }
    version_count=n+1;STORE(&names_header,((uint64_t)(n+1)<<32)|set->valid_mask);return 1;
}
static const struct names *get(unsigned number) {
    uint64_t h=LOAD(&names_header);uint32_t n=(uint32_t)(h>>32);
    if(number<1 || number>12 || !n || !((uint32_t)h&(1u<<(number-1))))return 0;
    return &versions[n-1][number-1];
}
const char *r5_filter_short_name(unsigned number){const struct names *p=get(number);return p?p->short_name:0;}
const char *r5_filter_full_name(unsigned number){const struct names *p=get(number);return p?p->full_name:0;}
uint32_t r5_filter_available_mask(void){return (uint32_t)LOAD(&names_header);}
