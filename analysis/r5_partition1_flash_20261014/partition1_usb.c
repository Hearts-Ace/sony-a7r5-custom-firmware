#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <IOKit/IOKitLib.h>
#include <IOKit/IOCFPlugIn.h>
#include <IOKit/usb/IOUSBLib.h>
#include <CoreFoundation/CoreFoundation.h>
#include <CommonCrypto/CommonDigest.h>
static IOUSBInterfaceInterface300 **usb; static UInt8 inp,outp;
static int allowed(const char *s) {
    return !strncmp(s,"getvar:",7) || !strcmp(s,"oem partition") || !strcmp(s,"oem partition dump nflasha1") || !strcmp(s,"oem partition dump nflasha 0 0x80") || !strcmp(s,"oem partition dump nflasha 0x80 0xbf80") || !strcmp(s,"oem dumpbrom") || !strncmp(s,"upload:/",8) || !strncmp(s,"download:/",10) || !strcmp(s,"flash:nflasha1") || !strcmp(s,"reboot");
}
static unsigned char staged[524288]; static unsigned long staged_size;
static int load_download(const char *path) {
    int fd=open(path,O_RDONLY);if(fd<0){perror("download input");return -1;}
    ssize_t n=read(fd,staged,sizeof(staged)); unsigned char extra;
    if(n<=0 || read(fd,&extra,1)!=0){close(fd);return -1;}close(fd);staged_size=(unsigned long)n;
    unsigned char digest[CC_SHA256_DIGEST_LENGTH]; char hex[65];
    CC_SHA256(staged,(CC_LONG)staged_size,digest);
    for(int i=0;i<32;i++)sprintf(hex+2*i,"%02x",digest[i]);hex[64]=0;
    if(strcmp(hex,"73b5132671588e04fa27a9bb86fa58a296a805f43020506123d717bc7dc7c388") && strcmp(hex,"3eeeb2a3794b5e43bcf301c61efcd97f9edd6abe57d33fa5a56a81f8e9ab1abf")){fprintf(stderr,"Rejected staged image hash %s\n",hex);return -1;}
    printf("APPROVED_SPARSE %lu bytes SHA256 %s\n",staged_size,hex);return 0;
}
static int readbuf(void *b,UInt32 *n) {
    IOReturn r=(*usb)->ReadPipeTO(usb,inp,b,n,5000,5000);
    if(r) {fprintf(stderr,"ReadPipeTO=0x%08x\n",r);return -1;}return 0;
}
static int command(const char *arg) {
    char download_cmd[32];int downloading=!strncmp(arg,"download:/",10);
    if(downloading){if(load_download(arg+9))return -1;snprintf(download_cmd,sizeof(download_cmd),"download:%08lx",staged_size);}
    const char *cmd=downloading?download_cmd:(!strncmp(arg,"upload:",7)?"upload":arg);
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
        if(!memcmp(b,"DATA",4) && downloading && n==12) {
            char *end=NULL;unsigned long wanted=strtoul((char*)b+4,&end,16);
            if(wanted!=staged_size || end!=(char*)b+12){fprintf(stderr,"Unexpected download length\n");return -1;}
            for(unsigned long pos=0;pos<staged_size;){UInt32 chunk=(UInt32)(staged_size-pos);if(chunk>65536)chunk=65536;
                IOReturn wr=(*usb)->WritePipeTO(usb,outp,staged+pos,chunk,5000,5000);
                if(wr){fprintf(stderr,"Download WritePipeTO=0x%08x\n",wr);return -1;}pos+=chunk;}
            downloading=0;continue;
        }
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
