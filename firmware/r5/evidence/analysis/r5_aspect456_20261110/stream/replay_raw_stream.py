"""Actual final CP RAW header bytes feed final AVCAM native RAW getter/preview.
CPU grayscale/driver resource models are explicit fixtures, not hardware encode.
"""
from pathlib import Path
import sys,json,struct,hashlib,argparse,types
H=Path(__file__).resolve().parent;P=H.parent
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--avcam',type=Path,default=P/'reference-review/candidate-c/avcam/av-cam.bin');a=p.parse_args();assert not a.output.exists()
sys.path[:0]=[str(P/'reference-review/tests')]
import verify_raw_preview_local as L
CTX,WORK,require=L.CTX,L.WORK,L.require
from unicorn import arm_const as A
from unicorn import arm64_const as R
CP=P/'cp/integrated-o/cp/cp423.NONINSTALLABLE.bin';AV=a.avcam.resolve();raw=AV.read_bytes();sha=lambda b:hashlib.sha256(b).hexdigest()
# Reuse only fixture definitions before its test loop. This executes no tests,
# writes no output and uses the exact final source file identified in receipt.
fixture=P/'cp/verify_raw_emb.py';source=fixture.read_text();saved=sys.argv;sys.argv=['rawfixture','--build',str(P/'cp/integrated-o'),'--output',str(H/'unused-no-write.json')];module=types.ModuleType('rawfixture');module.__file__=str(fixture)
try:exec(compile(source[:source.index("for mode in ('good'")],str(fixture),'exec'),module.__dict__)
finally:sys.argv=saved
rows=[]
for selection in range(4,8):
 for index,full in enumerate(L.FULLS):
  for formats in ((2,4),(4,2)):
   u,seen=module.fresh('good');task=module.TASK;put=module.put;put(u,module.STATE,selection,selection,70);u.mem_write(module.STATE+12,bytes([selection]));u.mem_write(task+0x30,struct.pack('<2H',*full));u.mem_write(task+0x234,struct.pack('<2H',*full));u.mem_write(task+0x6072,struct.pack('<2H',32,20));put(u,task+0x38,1);u.mem_write(task+0x726,b'\x0e');put(u,task+0x5980,formats[0]);put(u,task+0x5988,formats[1]);off=0x5984 if formats[0]==2 else 0x598c;u.mem_write(task+off,b'\0\2');put(u,task+0x98,1);u.mem_write(module.HEADER,b'\xa5'*0x18000);module.call(u,0x48a00a,0x48a00e,module.HEADER);header=bytes(u.mem_read(module.HEADER,0x15000));target=struct.unpack_from('<2I',header,0x14a2c)
   w,h=full;L.RH.FRAMES[21]=L.Raster.texture((w+127)&~127,h,231);packet=bytearray(0x800);struct.pack_into('<I',packet,0,2)
   for i,fmt in enumerate(formats):
    struct.pack_into('<I',packet,0x1b0+i*12,fmt);packet[0x1b4+i*12]=index;struct.pack_into('<HH',packet,0x1b6+i*12,*(target if fmt==4 else full))
   for at,g,res,unit in zip((0xcc,0xec,0x10c),(((w+127)&~127,h,w,h,0,0),L.GEOMETRIES[1],L.GEOMETRIES[2]),L.RESOURCE_IDS,(0x2345,0x50b0b,0x50b0c)):
    cw,ch,vw,vh,x,y=g;base=0x1e8+at;struct.pack_into('<6H',packet,base,cw,ch,vw,vh,x,y);struct.pack_into('<5I',packet,base+0xc,1,res,0,(cw*ch*10+3)//4,unit)
   # Produce the actual CP RAW template descriptor consumed by AVCAM's getter.
   # Its header-relative offsets are outputs of native setters, not fixture constants.
   gen=module.HEADER+0x20000;cp_packet=task+0x5b3c;u.mem_map(gen,0x10000);u.mem_write(cp_packet,bytes(0x268))
   def native(pc,args):
    for r,v in zip((A.UC_ARM_REG_R0,A.UC_ARM_REG_R1,A.UC_ARM_REG_R2,A.UC_ARM_REG_R3),args):u.reg_write(r,v)
    u.reg_write(A.UC_ARM_REG_CPSR,0x13);u.reg_write(A.UC_ARM_REG_SP,module.SP);u.reg_write(A.UC_ARM_REG_LR,module.STOP|1);u.emu_start(pc|1,module.STOP,count=1000000);require(u.reg_read(A.UC_ARM_REG_PC)==module.STOP,'CP RAW descriptor setter did not return')
   native(0xade81a,(cp_packet,gen));native(0xade8a2,(cp_packet,gen,*full));native(0xade8ac,(cp_packet,gen,1616,1080));native(0xade8b6,(cp_packet,gen,*full))
   for pc in(0xade6f8,0xade71e,0xade726,0xade72e):native(pc,(cp_packet,77,0))
   descriptor=bytes(u.mem_read(cp_packet,0x268));packet[0x314:0x450]=descriptor[0x12c:0x268]
   m=L.M(raw,True);m.stages=[];m.construct_import(bytes(packet),formats,selection);rh=0x20180000;m.u.mem_write(rh,header);m.u.mem_write(CTX+0x840,struct.pack('<Q',rh));m.u.mem_write(CTX+0x81c,struct.pack('<I',1));m.u.mem_write(CTX+0x7f0,struct.pack('<I',m.invoke(0x1f455c,(CTX+0x440,WORK,WORK+4))))
   m.invoke(0x1f5388,(CTX+0x440,rh,0x2001c000));extra=struct.unpack('<Q',m.u.mem_read(0x2001c090,8))[0];require(extra==rh+0x13fdc,('native getter extra pointer differs',hex(extra),header[:32].hex(),formats,index));require(tuple(struct.unpack('<II',m.u.mem_read(extra+0xa50,8)))==target,'CP EMB not read by native getter');source_wh=tuple(struct.unpack('<II',m.u.mem_read(extra+0x248,8)));require(source_wh==full,'SonyCrop unexpectedly changed')
   item=0x2001d000;m.u.mem_write(item,struct.pack('<Q',CTX));shared=bytes(m.u.mem_read(CTX+0x3bc,0x3c));m.preparing=True;result=m.invoke(0x206f70,(item,));m.preparing=False;require(result==0,'RAW preview stage failed');require(bytes(m.u.mem_read(CTX+0x3bc,0x3c))==shared,'shared YC modified');require(bytes(m.u.mem_read(rh,0x15000))==header,'header mutated');require(len(m.pixel_requests)>0,'no natural RAW+HEIF resize')
   main=[r for c,r in zip(m.stages,m.pixel_requests)if c[2]==3];require(main and tuple(main[0]['pixel_WH'])==target,'encoded preview WH does not match actual CP EMB')
   rows.append(dict(selection=selection,size_enum=index,formats=formats,CP_EMB_WH=target,CP_SonyCrop_WH=source_wh,CPheader_sha256=sha(header),CP_RAW_descriptor_sha256=sha(descriptor),native_getter_extra=hex(extra),native_plan=m.word(CTX+0x7f0),requests=m.pixel_requests,header_exact_after=True,shared_YC_exact=True))
report=dict(passed=True,schema='r5-cp-rawheader-avcam-stream/1',cases=len(rows),rows=rows,CP_sha256=sha(CP.read_bytes()),AVCAM_sha256=sha(raw),script_sha256=sha(Path(__file__).read_bytes()),fixture_sources={str(p):sha(p.read_bytes())for p in {fixture,*[Path(m.__file__).resolve() for m in sys.modules.values() if getattr(m,'__file__',None) and str(Path(m.__file__).resolve()).startswith(str(P)) and str(m.__file__).endswith('.py')]}},actual=['finalCP48a00a guard→completeRAWheaderproducer→onlyEMBWHupdate','actual CP ade81a/ade8a2/ade8ac/ade8b6/ade6f8/ade71e/ade726/ade72e produce RAW descriptor; exact descriptor12c:268 copied to AVCAMpacket314:450','exactCPheader copied to AVCAM; actual1f5388 getter returns extra pointer andEMB','actualnatural plan→206f70→native prepare/resize/commit request'],fixtures=['RAW effective size/rawtype/formats/native pool and TTBR inputs','packet transport copies actual CP-produced EMB WH and native RAW WH','reference resource allocation/driver returns and CPU grayscale resize consume actual native requests'],limits=['not hardwareencoding/Bayer/card/fullIPC or actualcamera','onlyRAW+HEIF twoorders are naturalAVCAMpreview routes; RAW-only/JPEG sharedCPpreview checked separately'])
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(rows))))
