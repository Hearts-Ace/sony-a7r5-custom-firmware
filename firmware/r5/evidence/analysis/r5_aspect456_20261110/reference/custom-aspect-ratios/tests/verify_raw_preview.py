#!/usr/bin/env python3
"""真实CP SonyCrop/header→AVCAM RAW及HEIF辅助stage，局部预览裁切验证。"""
from pathlib import Path
import json,struct,sys
F=Path(__file__).resolve().parents[1];sys.path[:0]=[str(F),str(F/'tests')]
from verify_raw_heif import *
WORK=0x20161000
from verify_raw_crop_tags import RawExif,prepare,HEADER,ORIGINALS,CROPS
import verify_raw_heif as RH
import argparse,hashlib
F=Path(__file__).resolve().parents[1]
SCN=((1616,1000),(1616,680),(1344,1080),(1616,872))
THM=((320,200),(320,136),(256,208),(320,176))
SCN_XY=((0,40),(0,200),(136,0),(0,104))
THM_XY=((0,6),(0,38),(32,2),(0,18))
THM_FIT=((0,10,160,100),(0,26,160,68),(8,0,144,120),(0,16,160,88))
sha=lambda b:hashlib.sha256(b).hexdigest()

class M(Consumers):
 def hook(self,u,at,size,data):
  if at==0x206378 and getattr(self,"failure",None) and u.reg_read(A.UC_ARM64_REG_W1)==self.failure[0]:return self.ret(self.failure[1])
  if at==0x207de0:return self.ret()
  if at in(0x207048,0x2071e8,0x207264):self.stages.append([hex(at),u.reg_read(A.UC_ARM64_REG_X0),u.reg_read(A.UC_ARM64_REG_X1)])
  return super().hook(u,at,size,data)
def headers(selection,formats,full):
 r=RawExif(cp,cr);task=prepare(r,1,selection,full,formats,1);header,_=r.header(task,True);GEN=HEADER+0x20000;PACKET=task+0x5b3c;r.u.mem_map(GEN,0x10000);r.u.mem_write(PACKET,bytes(0x268))
 def native(pc,args):
  for reg,v in zip((C.UC_ARM_REG_R0,C.UC_ARM_REG_R1,C.UC_ARM_REG_R2,C.UC_ARM_REG_R3),args):r.u.reg_write(reg,v)
  r.u.reg_write(C.UC_ARM_REG_SP,STACK+0xff00);r.u.reg_write(C.UC_ARM_REG_LR,STOP|1);r.u.emu_start(pc|1,STOP,count=1000000);assert r.u.reg_read(C.UC_ARM_REG_PC)==STOP
 native(0xade81a,(PACKET,GEN));native(0xade8a2,(PACKET,GEN,*full));native(0xade8ac,(PACKET,GEN,1616,1080));native(0xade8b6,(PACKET,GEN,*full))
 for pc in(0xade6f8,0xade71e,0xade726,0xade72e):native(pc,(PACKET,77,0))
 return header,bytes(r.u.mem_read(GEN,0x10000)),bytes(r.u.mem_read(PACKET,0x268))

class FullProducer(Producer):
 def __init__(self,raw,patch,full,index):
  self.full,self.index=full,index;super().__init__(raw,patch)
 def hook(self,u,pc,size,data):
  if pc==0x48b9d8:self.size=self.full
  return super().hook(u,pc,size,data)
 def native(self,pc,arg):
  if pc==0xae7522:
   w,h=self.full;self.u.mem_write(TASKS+0x5f78,struct.pack('<6H',(w+127)&~127,h,w,h,0,0))
   for off in(0x5984,0x598c):self.u.mem_write(TASKS+off,bytes([self.index]))
  return super().native(pc,arg)

def scenario(image,selection,index,formats,prepared=False):
 full=ORIGINALS[index];w,h=full;RH.FRAMES[21]=Raster.texture((w+127)&~127,h,231)
 header,gen,desc=headers(selection if 2 in formats else 0,formats if 2 in formats else(2,0),full)
 producer=FullProducer(cp,cr,full,index);packet=bytearray(producer.packet(selection,formats));packet[0x314:0x450]=desc[0x12c:0x268]
 m=M(image,True);m.stages=[];m.construct_import(bytes(packet),formats,selection);RAWHEADER=0x20180000
 m.u.mem_write(RAWHEADER,header);m.u.mem_write(META,gen);m.u.mem_write(CTX+0x840,struct.pack('<Q',RAWHEADER if 2 in formats else 0));m.u.mem_write(CTX+0x81c,struct.pack('<I',int(4 in formats)))
 if 2 in formats:
  m.invoke(0x1f5388,(CTX+0x440,RAWHEADER,0x2001c000));extra=struct.unpack('<Q',m.u.mem_read(0x2001c090,8))[0]
  require(extra==RAWHEADER+0x13fdc,'real CP descriptor→RAW getter differs')
  expected=full if not selection else CROPS[selection-4][index][:2]
  require(tuple(struct.unpack('<II',m.u.mem_read(extra+0x248,8)))==tuple(expected),'frozen SonyCrop differs')
 if prepared:
  slot=1 if formats[0]==2 else 16
  for off,mode in((0x410 if slot==1 else 0x428,3),(0x3f8,1),(0x404,2)):
   require(m.invoke(ar['symbols']['aspect_crop_geometry'],(CTX+off,selection|(0x100 if mode!=3 else 0),0,CTX+off))==1,'prepared geometry fixture invalid')
 shared=bytes(m.u.mem_read(CTX+0x3bc,0x3c));protected=bytes(m.u.mem_read(RAWHEADER+0x13fdc+0x230,0x20))
 plan=m.invoke(0x1f455c,(CTX+0x440,WORK,WORK+4));m.u.mem_write(CTX+0x7f0,struct.pack('<I',plan));item=0x2001d000;m.u.mem_write(item,struct.pack('<Q',CTX));m.preparing=True
 if 2 in formats:require(m.invoke(0x206f70,(item,))==0,'actual native RAW EMB stage failed')
 if 4 in formats:require(m.invoke(0x207128,(item,))==0,'actual native HEIF aux stage failed')
 m.preparing=False
 require(bytes(m.u.mem_read(CTX+0x3bc,0x3c))==shared,'original YC / HEIF HEVC views changed')
 require(bytes(m.u.mem_read(RAWHEADER+0x13fdc+0x230,0x20))==protected,'Default/SonyCrop changed')
 raw_after=bytes(m.u.mem_read(RAWHEADER,len(header)))
 require(all(first==second for at,(first,second)in enumerate(zip(header,raw_after))if not 0x14a2c<=at<0x14a34),'non-embedded RAW header changed')
 require(len(m.stages)==len(m.pixel_requests),'actual stage/driver counts differ')
 expected_main=full if not selection else CROPS[selection-4][index][:2];expected_scn=(1616,1080)if not selection else SCN[selection-4]
 rows=[]
 for call,request in zip(m.stages,m.pixel_requests):
  mode=call[2];expected=expected_main if mode==3 else expected_scn if mode==1 else(160,120)
  require(tuple(request['pixel_WH'])==tuple(expected),'native stage visible WH differs')
  source=request['source'];target=request['target'];source_wh=expected_main if mode==3 else expected_scn if mode==1 else(320,212)if not selection else THM[selection-4]
  require(tuple(source[4:6])==tuple(source_wh),'source stretched or cropped twice')
  if selection:
   expected_xy=CROPS[selection-4][index][2:]if mode==3 else SCN_XY[selection-4]if mode==1 else THM_XY[selection-4]
   require(tuple(source[2:4])==tuple(expected_xy),'source ROI is not the selected centered crop')
  require(target[2:4]==[0,0],'target valid origin not zero')
  if mode==2:
   require(target[4:6]==[160,120]and target[8]<=160 and target[9]<=120,'THM canvas/fit invalid')
   require(tuple(target[6:10])==((0,7,160,106)if not selection else THM_FIT[selection-4]),'THM selected view is not centered with the expected black bars')
  rows.append(dict(callsite=call[0],slot=call[1],mode=mode,**request))
 if any(call[2]==3 for call in m.stages):require(tuple(struct.unpack('<II',m.u.mem_read(RAWHEADER+0x14a2c,8)))==tuple(expected_main),'native RAW IFD2 not synchronized')
 return dict(selection=selection,full_WH=list(full),formats=list(formats),prepared=prepared,native_plan=plan,requests=rows,shared_sha256=sha(shared),native_allocation_classes=[x['target_class']for x in m.resource_calls if x['native']=='209fe4'],DefaultCrop_SonyCrop_unchanged=True,original_YC_HEIF_HEVC_aux_unchanged=True)

def failure_probe(image,mode,error):
 formats=(2,4);full=ORIGINALS[0];RH.FRAMES[21]=Raster.texture(9600,6336,231)
 header,gen,desc=headers(5,formats,full);packet=bytearray(FullProducer(cp,cr,full,0).packet(5,formats));packet[0x314:0x450]=desc[0x12c:0x268]
 m=M(image,True);m.stages=[];m.construct_import(bytes(packet),formats,5);m.u.mem_write(0x20180000,header);m.u.mem_write(META,gen);m.u.mem_write(CTX+0x840,struct.pack('<Q',0x20180000));m.u.mem_write(CTX+0x7f0,struct.pack('<I',8));m.u.mem_write(0x2001d000,struct.pack('<Q',CTX));m.preparing=True;m.failure=(mode,error)
 shared=bytes(m.u.mem_read(CTX+0x3bc,0x3c));result=m.invoke(0x206f70 if mode==3 else 0x207128,(0x2001d000,))
 require(result==5,'native prepare failure not propagated by stage')
 require(bytes(m.u.mem_read(CTX+0x3bc,0x3c))==shared,'failure modified shared source')
 require(len(m.pixel_requests)==int(mode==2),'failed prepare reached its hardware driver')
 return dict(mode=mode,injected_native_error=error,stage_result=result,completed_driver_requests=len(m.pixel_requests),shared_unchanged=True)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();require(not a.output.exists(),'refuse overwrite')
 cp=(a.build/'cp/cpapp-b.bin').read_bytes();cr=json.loads((a.build/'cp/patch.json').read_text());av=(a.build/'avcam/av-cam.bin').read_bytes();ar=json.loads((a.build/'avcam/patch.json').read_text());require(sha(cp)==cr['output_sha256']and sha(av)==ar['sha256'],'component SHA differs')
 baseline=bytearray(av);sites=(0x207048,0x2071e8,0x207264)
 for at in sites:
  row=next(x for x in ar['patches']if x['offset']==at);before=bytes.fromhex(row['before']);after=bytes.fromhex(row['after']);require(len(before)==len(after)==4 and baseline[at:at+4]==after,'native prepare callsite preimage differs');baseline[at:at+4]=before
 baseline=bytes(baseline);rows=[];controls=[];negatives=[]
 for selection in range(4,8):
  for index in range(3):
   for formats in((2,0),(2,1),(1,2),(2,4),(4,2),(4,0)):rows.append(scenario(av,selection,index,formats))
   for formats in((2,4),(4,2)):rows.append(scenario(av,selection,index,formats,True))
 for formats in((2,0),(2,1),(1,2),(2,4),(4,2),(4,0)):
  first=scenario(baseline,0,0,formats);second=scenario(av,0,0,formats);require(first==second,'native control changed');controls.append(second)
 for selection in range(4,8):
  for formats in((2,4),(4,2),(4,0)):
   try:scenario(baseline,selection,0,formats)
   except AssertionError as e:negatives.append(dict(selection=selection,formats=list(formats),error=str(e)))
   else:raise AssertionError('reverted native prepare accepted cropped expectation')
 failures=[failure_probe(av,mode,error)for mode in(3,1,2)for error in(1,2)]
 result=dict(passed=True,prepare_failure_cases=len(failures),failure_rows=failures,CP_sha256=sha(cp),AVCAM_sha256=sha(av),test_sha256=sha(Path(__file__).read_bytes()),cases=len(rows),native_controls=len(controls),reverted_callsite_rejections=len(negatives),rows=rows,control_rows=controls,negative_rows=negatives,camera_io=False,device_tested=False,native=['CP SonyCrop/generic/header offsets→actual full AVCAM constructor/getters','actual natural plan and RAW/HEIF auxiliary stage selection','native prepare/resize/commit and IFD2 setters'],models=['full-WH parameter library/YC/resources are explicit fixtures','CPU grayscale/fit model consumes actual native driver request','resource import/allocation descriptors/release boundary modeled, not complete DMM lifecycle'],limits=['no hardware encoder, final file, card or AP playback','RAW-only/JPG plans that skip AVCAM are preserved controls; CP JPEG request tests cover their previews','prepared-view geometry is an explicit valid-input control','standard Exif and final per-record metadata isolation are separate writer evidence'])
 a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k]for k in('passed','cases','native_controls','reverted_callsite_rejections')}))
