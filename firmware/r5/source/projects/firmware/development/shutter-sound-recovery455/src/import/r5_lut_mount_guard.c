#include "r5_lut_mount_guard.h"
struct span {const uint8_t *p;size_t n;};
static int equals(struct span s,const char *text) {
    size_t i;for(i=0;i<s.n;i++) if(!text[i] || s.p[i]!=(uint8_t)text[i]) return 0;
    return !text[s.n];
}
static int writable(struct span s) {
    size_t start=0,i;unsigned rw=0;
    for(i=0;i<=s.n;i++) if(i==s.n || s.p[i]==',') {
        struct span option={s.p+start,i-start};
        if(!option.n || equals(option,"ro")) return 0;
        if(equals(option,"rw") && ++rw!=1) return 0;
        start=i+1;
    }
    return rw==1;
}
static int decimal(struct span s) {
    size_t i;if(!s.n)return 0;
    for(i=0;i<s.n;i++) if(s.p[i]<'0'||s.p[i]>'9') return 0;
    return 1;
}
static int device(struct span s) {
    size_t i;for(i=0;i<s.n;i++) if(s.p[i]==':') {
        struct span major={s.p,i},minor={s.p+i+1,s.n-i-1};
        return decimal(major)&&decimal(minor);
    }
    return 0;
}
static int line(const uint8_t *p,size_t n,int *target) {
    struct span fields[64];size_t i=0,start,count=0,separator=0;
    if(!n || n>4096 || p[0]==' ' || p[n-1]==' ')return -1;
    while(i<n) {
        if(count==64)return -1;
        start=i;
        while(i<n&&p[i]!=' ') {
            if(p[i]<33 || p[i]>126)return -1;
            i++;
        }
        fields[count].p=p+start;fields[count].n=i-start;
        if(equals(fields[count],"-")) {
            if(separator)return -1;
            separator=count;
        }
        count++;
        if(i<n && (++i==n || p[i]==' '))return -1;
    }
    if(count<10 || separator<6 || count!=separator+4 || !decimal(fields[0]) ||
       !decimal(fields[1]) || !device(fields[2]) || fields[3].p[0]!='/' ||
       fields[4].p[0]!='/')return -1;
    if(!equals(fields[4],"/usr/data/lut"))return 0;
    (*target)++;
    return equals(fields[3],"/") && writable(fields[5]) &&
        equals(fields[separator+1],"vfat") && equals(fields[separator+2],"/dev/nflasha30") &&
        writable(fields[separator+3]) ? 0 : -1;
}
int r5_lut_mountinfo_check(const uint8_t *p,size_t n) {
    size_t i,start=0;unsigned lines=0;int targets=0;
    if(!p || !n || n>65536 || p[n-1]!='\n')return -1;
    for(i=0;i<n;i++)if(p[i]=='\n') {
        if(++lines>512 || line(p+start,i-start,&targets))return -1;
        start=i+1;
    }
    return targets==1 ? 0 : -1;
}
