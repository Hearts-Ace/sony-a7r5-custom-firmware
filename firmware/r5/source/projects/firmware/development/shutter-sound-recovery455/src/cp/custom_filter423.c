/* Original resource24 receiver serializes control updates. Render readers
 * acquire one immutable view; SELECT never allocates or modifies a view. */
#include "r5_custom_filter423.h"
#include "r5_boot_bank.h"
#include "r5_look_transfer.h"
#include "r5_grid_diagnostics.h"
#define STATE ((const uint32_t *)(uintptr_t)0x1a39448u)
#define CONTROL ((uint32_t *)(uintptr_t)R5_FILTER423_CONTROL_VA)
#define ACTIVE ((uint32_t *)(uintptr_t)R5_FILTER423_ACTIVE_VA)
#define SEALED 0x35424c53u
void r5_filter423_accept(uint32_t alias,unsigned new_generation){
 if(CONTROL[0]!=alias||new_generation){CONTROL[0]=alias;CONTROL[1]=0;CONTROL[2]=0;}
}
int r5_filter423_select(const uint8_t *p,uint32_t n,uint8_t ack[32]){
 const struct r5_boot_bank *b;struct r5_filter423_view *v;
 unsigned i,status=R5_F_BAD_PACKET,selected;uint32_t seq;
 if(!p||n<8||p[0]!=R5_FILTER423_SELECT_CLASS||r5_diag_get(p+4)!=R5_FILTER423_SELECT_MAGIC)return 0;
 if(n!=32)return -1;
 selected=r5_diag_get(p+12);seq=r5_diag_get(p+8);
 if(p[1]!=1||p[2]!=1||p[3]!=32||!seq||!r5_diag_get(p+20)||r5_diag_get(p+24)||r5_diag_get(p+28)!=r5_diag_crc(p,32))goto reply;
 status=R5_F_NOT_READY;
 b=(const void *)(uintptr_t)STATE[0];
 if(STATE[1]!=28768u||!b||b->state!=SEALED)goto reply;
 status=R5_F_BAD_BANK;
 if(CONTROL[0]!=r5_diag_get(p+20)||r5_transfer_bank_crc(b)!=r5_diag_get(p+16))goto reply;
 status=R5_F_BAD_SELECTION;
 if(selected>12||(selected&&!(b->expected_mask&(1u<<(selected-1)))))goto reply;
 v=r5_filter423_view((struct r5_boot_bank *)(uintptr_t)b,selected);
 if(v->ready!=R5_FILTER423_MAGIC||v->bank!=(uintptr_t)b||v->selected!=selected)goto reply;
 status=R5_F_STALE;
 if(seq<CONTROL[1]||(seq==CONTROL[1]&&selected!=CONTROL[2]))goto reply;
 CONTROL[1]=seq;CONTROL[2]=selected;
 __atomic_store_n(ACTIVE,(uint32_t)(uintptr_t)v,__ATOMIC_RELEASE);status=R5_F_OK;
reply:
 for(i=0;i<32;i++)ack[i]=p[i];ack[2]=0x81;r5_diag_put(ack+24,status);
 r5_diag_put(ack+28,r5_diag_crc(ack,32));return 1;
}
