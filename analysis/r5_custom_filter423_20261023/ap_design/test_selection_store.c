#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "r5_filter_selection423.h"
#include "r5_lut_directory.h"
static unsigned calls,fault,fault_at;static int error_no;static uint8_t active[25],stage[25];static size_t active_n,stage_n,pos;static int open_mode;
static int hit(unsigned kind){calls++;return fault==kind && (!fault_at||calls==fault_at);}
static int openat_fixture(int d,const char*n,int flags,unsigned mode){(void)mode;assert(d==9);if(hit(1))return -1;pos=0;
 if(flags==0x80c1){assert(!strcmp(n,R5_FILTER_SELECTION_PENDING));open_mode=2;stage_n=0;return 11;}
 open_mode=!strcmp(n,R5_FILTER_SELECTION_FILE)?0:1;if((open_mode?stage_n:active_n)==0){error_no=2;return -1;}return 10;}
static intptr_t read_fixture(int fd,void*out,size_t n){(void)fd;size_t len=open_mode?stage_n:active_n;if(hit(2))return -1;if(pos==len)return 0;if(n>3)n=3;if(n>len-pos)n=len-pos;memcpy(out,(open_mode?stage:active)+pos,n);pos+=n;return n;}
static intptr_t write_fixture(int fd,const void*p,size_t n){assert(fd==11);if(hit(3))return 0;if(n>2)n=2;memcpy(stage+stage_n,p,n);stage_n+=n;return n;}
static int close_fixture(int fd){(void)fd;return hit(4)?-1:0;}
static int sync_fixture(int fd){return hit(fd==9?6:5)?-1:0;}
static int rename_fixture(int d,const char*a,int e,const char*b){assert(d==9&&e==9&&!strcmp(a,R5_FILTER_SELECTION_PENDING)&&!strcmp(b,R5_FILTER_SELECTION_FILE));if(hit(7))return -1;memcpy(active,stage,stage_n);active_n=stage_n;stage_n=0;return 0;}
static int unlink_fixture(int d,const char*n,int flags){assert(d==9&&!flags&&!strcmp(n,R5_FILTER_SELECTION_PENDING));if(hit(8)){error_no=5;return -1;}stage_n=0;return 0;}
static int *errno_fixture(void){return &error_no;}
int main(void){struct r5_lut_directory d={0};unsigned out=99,total=0;d.fd=9;d.phase=2;d.api.openat=openat_fixture;d.api.read=read_fixture;d.api.write=write_fixture;d.api.close=close_fixture;d.api.sync=sync_fixture;d.api.renameat=rename_fixture;d.api.unlinkat=unlink_fixture;d.api.error_number=errno_fixture;
 assert(r5_filter_selection_load(&d,&out)==R5_ABSENT && out==99);total++;
 for(unsigned n=0;n<=12;n++){calls=0;assert(!r5_filter_selection_save(&d,n));assert(!r5_filter_selection_load(&d,&out)&&out==n);total++;}
 uint8_t original[25];memcpy(original,active,25);
 for(unsigned off=0;off<24;off++){active[off]^=1;out=99;assert(r5_filter_selection_load(&d,&out)==R5_INVALID&&out==99);active[off]^=1;total++;}
 for(unsigned f=1;f<=8;f++){fault=f;calls=0;int status=r5_filter_selection_save(&d,7);assert(status==(f==6||f==7?3:2));if(f!=6)assert(active_n==24&&!memcmp(active,original,24));else memcpy(active,original,25);fault=0;total++;}
 active_n=23;out=99;assert(r5_filter_selection_load(&d,&out)==R5_INVALID&&out==99);active_n=25;assert(r5_filter_selection_load(&d,&out)==R5_INVALID);total+=2;
 assert(r5_filter_selection_save(&d,13)==1);total++;
 printf("{\"passed\":true,\"camera_io\":false,\"cases\":%u,\"scope\":\"selection sidecar short IO, corruption, save failures and publication uncertainty\"}\n",total);return 0;}
