import struct
TRAMP=0x108f40
RX=0x1196000

def branch(at,target,link=False):
    delta=target-at-8
    assert not delta%4 and -(1<<25)<=delta<(1<<25)
    return struct.pack('<I',(0xeb000000 if link else 0xea000000)|((delta>>2)&0xffffff))

def mov16(reg,value,top=False):
    return struct.pack('<I',(0xe3400000 if top else 0xe3000000)|((value&0xf000)<<4)|(reg<<12)|(value&0xfff))

def trampoline():
    result=bytearray(struct.pack('<I',0xe92d4010)) # push{r4,lr}, preserve8bytealignment
    result+=branch(TRAMP+len(result),0x108768,True) # original final native map
    result+=struct.pack('<II',0xe92d500f,0xe10f4000) # save originalmapr0-r3,r12,LR;MRSr4,CPSR
    result+=mov16(0,RX&65535)+mov16(0,RX>>16,True)
    result+=struct.pack('<III',0xe1a02000,0xe3a01a01,0xe3a0300f) # r2=r0;r1=4096;r3=15
    result+=branch(TRAMP+len(result),0x108768,True)
    result+=struct.pack('<III',0xe8bd500f,0xe128f004,0xe8bd8010) # restoreargs/flags/r4;returnPCfromoutercall
    assert len(result)==52
    return bytes(result)
