#include "r5_native_transport.h"
/* Linker resolves these to original AP PLT VAs using CALL26, preserving PIE
 * load bias. Never encode a native virtual address as a function pointer. */
extern int r5_osal_alloc(uint32_t,void **,uint32_t,uint32_t);
extern int r5_osal_send(uint32_t,void *);
extern int r5_osal_free(uint32_t,void *);
extern void r5_osal_set_src(void *,uint32_t);
int r5_native_ap_send(void *context,const uint8_t *packet,size_t length) {
    uint8_t *msg=0;size_t i;int rc,freed;(void)context;
    if(!packet||!length||length>4096)return -1024;
    rc=r5_osal_alloc(0x90030001u,(void **)&msg,(uint32_t)length,0);
    if(rc)return rc;
    if(!msg)return -1024;
    r5_osal_set_src(msg,0x80020002u);
    for(i=0;i<length;i++)msg[i]=packet[i];
    rc=r5_osal_send(0x90030001u,msg);
    if(!rc)return 0;
    freed=r5_osal_free(0x90030001u,msg);
    return freed?freed:rc;
}
