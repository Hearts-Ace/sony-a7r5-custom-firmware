#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <IOKit/IOKitLib.h>
#include <IOKit/IOCFPlugIn.h>
#include <IOKit/usb/IOUSBLib.h>
#include <CoreFoundation/CoreFoundation.h>
static IOUSBInterfaceInterface300 **usb; static UInt8 inp,outp;
static int allowed(const char *s) {
    return !strncmp(s,"getvar:",7) || !strcmp(s,"oem help") || !strcmp(s,"oem partition") || !strcmp(s,"oem cetus") || !strcmp(s,"oem cetus dumpbrom") || !strcmp(s,"oem cetus dumpnor") || !strncmp(s,"oem cetus dumpnor:",18) || !strcmp(s,"oem dumpbrom") || !strncmp(s,"oem partition dump nflasha",25) || !strncmp(s,"upload:/",8) || !strcmp(s,"reboot");
}
static int readbuf(void *b,UInt32 *n) {
    IOReturn r=(*usb)->ReadPipeTO(usb,inp,b,n,5000,5000);
    if(r) {fprintf(stderr,"ReadPipeTO=0x%08x\n",r);return -1;}return 0;
}
static int command(const char *arg) {
    const char *cmd=!strncmp(arg,"upload:",7)?"upload":arg;
    printf("COMMAND %s\n",cmd);fflush(stdout);
    IOReturn r=(*usb)->WritePipeTO(usb,outp,(void*)cmd,(UInt32)strlen(cmd),5000,5000);
    if(r){fprintf(stderr,"WritePipeTO=0x%08x\n",r);return -1;}
    unsigned long saved_bytes=0; const char *saved_path=NULL;
    for(int replies=0;replies<256;replies++) {
        unsigned char b[65537];UInt32 n=64;
        if(readbuf(b,&n))return -1;b[n]=0;
        if(n<4){fprintf(stderr,"Short response %u\n",n);return -1;}
        printf("REPLY %.*s\n",(int)n,b);fflush(stdout);
        if(!memcmp(b,"OKAY",4)){if(saved_path){printf("SAVED %lu bytes %s\n",saved_bytes,saved_path);fflush(stdout);}return 0;}
        if(!memcmp(b,"FAIL",4))return -1;
        if(!memcmp(b,"INFO",4))continue;
        if(!memcmp(b,"DATA",4) && !strncmp(arg,"upload:/",8) && n==12) {
            unsigned long total=strtoul((char*)b+4,NULL,16),done=0,next_progress=64UL*1024*1024;
            if(!total || total>2147483648UL) return -1;
            int f=open(arg+7,O_WRONLY|O_CREAT|O_EXCL,0600);if(f<0){perror("output");return -1;}
            while(done<total){UInt32 chunk=(UInt32)(total-done);if(chunk>65536)chunk=65536;
                if(readbuf(b,&chunk) || !chunk || chunk>total-done){close(f);return -1;}
                if(write(f,b,chunk)!=chunk){close(f);return -1;}done+=chunk;if(done>=next_progress){printf("PROGRESS %lu/%lu bytes %s\n",done,total,arg+7);fflush(stdout);next_progress+=64UL*1024*1024;}}
            if(fsync(f)!=0){close(f);return -1;}if(close(f)!=0)return -1;saved_bytes=done;saved_path=arg+7;continue;
        }
        fprintf(stderr,"Unexpected response\n");return -1;
    }return -1;
}
int main(int argc,char **argv) {
    setbuf(stdout,NULL);
    for(int i=1;i<argc;i++)if(!allowed(argv[i])){fprintf(stderr,"Rejected command: %s\n",argv[i]);return 2;}
    io_iterator_t it; io_service_t svc;
    if(IOServiceGetMatchingServices(kIOMainPortDefault,IOServiceMatching(kIOUSBInterfaceClassName),&it))return 3;
    while((svc=IOIteratorNext(it))){IOCFPlugInInterface **p=NULL;SInt32 score;
        IOReturn r=IOCreatePlugInInterfaceForService(svc,kIOUSBInterfaceUserClientTypeID,kIOCFPlugInInterfaceID,&p,&score);IOObjectRelease(svc);
        if(r || !p)continue;
        IOUSBInterfaceInterface300 **iface=NULL;HRESULT hr=(*p)->QueryInterface(p,CFUUIDGetUUIDBytes(kIOUSBInterfaceInterfaceID300),(LPVOID*)&iface);(*p)->Release(p);
        if(hr || !iface)continue;
        UInt16 vid,pid;UInt8 cls,sub,proto;
        (*iface)->GetDeviceVendor(iface,&vid);(*iface)->GetDeviceProduct(iface,&pid);(*iface)->GetInterfaceClass(iface,&cls);(*iface)->GetInterfaceSubClass(iface,&sub);(*iface)->GetInterfaceProtocol(iface,&proto);
        if(vid==0x18d1 && pid==0x4ee0 && cls==255 && sub==66 && proto==3){if(usb){fprintf(stderr,"Multiple targets\n");return 4;}usb=iface;}else (*iface)->Release(iface);
    }IOObjectRelease(it);
    if(!usb){fprintf(stderr,"No configured fastboot interface\n");return 5;}
    IOReturn r=(*usb)->USBInterfaceOpen(usb);if(r){fprintf(stderr,"USBInterfaceOpen=0x%08x\n",r);return 6;}
    UInt8 count;(*usb)->GetNumEndpoints(usb,&count);
    for(UInt8 p=1;p<=count;p++){UInt8 dir,num,type,interval;UInt16 packet;(*usb)->GetPipeProperties(usb,p,&dir,&num,&type,&packet,&interval);
        printf("PIPE %u dir=%u endpoint=%u type=%u packet=%u\n",p,dir,num,type,packet);
        if(type==kUSBBulk){if(dir==kUSBIn)inp=p;else outp=p;}}
    int result=0;if(!inp || !outp)result=7;
    for(int i=1;!result && i<argc;i++)if(command(argv[i]))result=8;
    (*usb)->USBInterfaceClose(usb);(*usb)->Release(usb);return result;
}
