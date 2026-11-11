#!/usr/bin/env python3
"""RAW EMB dimensions -> actual getter -> native local resize, excluding crop tags."""
from pathlib import Path
import argparse,hashlib,json,struct,sys
H=Path(__file__).resolve().parents[1];REF=H.parent/'reference/custom-aspect-ratios';sys.path[:0]=[str(REF),str(REF/'tests')]
from verify_raw_preview import M,RH,Raster
from verify_raw_heif import *
WORK=0x20161000
P=(((9504,5872),(6240,3856),(4752,2936)),((9504,3976),(6240,2608),(4752,1992)),((7920,6336),(5200,4160),(3968,3168)),((9504,5136),(6240,3376),(4752,2568)))
SCN=((1616,1000),(1616,680),(1344,1080),(1616,872));THM=((320,200),(320,136),(256,208),(320,176));FULLS=((9504,6336),(6240,4160),(4752,3168))
SHA=lambda b:hashlib.sha256(b).hexdigest()
def scenario(raw,selection,index,formats,symbols,failure=None):
 full=FULLS[index];w,h=full;RH.FRAMES[21]=Raster.texture((w+127)&~127,h,231)
 target=P[selection-4][index] if selection else full
 packet=bytearray(0x800);struct.pack_into('<I',packet,0,2)
 for i,fmt in enumerate(formats):
  struct.pack_into('<I',packet,0x1b0+i*12,fmt);packet[0x1b4+i*12]=index
  struct.pack_into('<HH',packet,0x1b6+i*12,*(target if fmt==4 else full))
 # Exact native ae7522 descriptor contract: allocated YC resources remain full-frame.
 for at,g,res,unit in zip((0xcc,0xec,0x10c),(((w+127)&~127,h,w,h,0,0),GEOMETRIES[1],GEOMETRIES[2]),RESOURCE_IDS,(0x2345,0x50b0b,0x50b0c)):
  cw,ch,vw,vh,x,y=g;base=0x1e8+at
  struct.pack_into('<6H',packet,base,cw,ch,vw,vh,x,y)
  struct.pack_into('<5I',packet,base+0xc,1,res,0,(cw*ch*10+3)//4,unit)
 template=0x314;struct.pack_into('<I',packet,template+4,0x100);struct.pack_into('<HH',packet,template+0x10,*full);struct.pack_into('<I',packet,template+0x44,0x1000)
 struct.pack_into('<I',packet,0x1e8+0x240,0x13fbc)
 struct.pack_into('<I',packet,0x1e8+0x250,0x14a2c)
 m=M(raw,True);m.stages=[];m.construct_import(bytes(packet),formats,selection);rawhead=0x20180000
 m.u.mem_write(rawhead,struct.pack('<II',*full)+bytes(0x15000-8));m.u.mem_write(rawhead+0x13fdc+0x248,struct.pack('<II',*full));m.u.mem_write(rawhead+0x14a2c,struct.pack('<II',*target))
 m.u.mem_write(CTX+0x840,struct.pack('<Q',rawhead));m.u.mem_write(CTX+0x81c,struct.pack('<I',int(4 in formats)))
 m.invoke(0x1f5388,(CTX+0x440,rawhead,0x2001c000));extra=struct.unpack('<Q',m.u.mem_read(0x2001c090,8))[0]
 actual_id=m.invoke(symbols['aspect_avcam_raw_crop'],(CTX,WORK,WORK+4));require(actual_id==selection,('RAW EMB getter failed',actual_id,selection,hex(extra),hex(rawhead),hex(m.word(CTX+0x440+0xa4)),hex(m.word(CTX+0x440+0x224))))
 m.u.mem_write(CTX+0x7f0,struct.pack('<I',m.invoke(0x1f455c,(CTX+0x440,WORK,WORK+4))))
 item=0x2001d000;m.u.mem_write(item,struct.pack('<Q',CTX));before=bytes(m.u.mem_read(rawhead,0x15000));shared=bytes(m.u.mem_read(CTX+0x3bc,0x3c));m.preparing=True
 if failure:m.failure=failure
 result=m.invoke(0x206f70 if not failure or failure[0]==3 else 0x207128,(item,));require(result==(5 if failure else 0),'native RAW EMB stage failed');m.preparing=False
 require(bytes(m.u.mem_read(CTX+0x3bc,0x3c))==shared,'shared YC changed')
 after=bytes(m.u.mem_read(rawhead,0x15000));require(after==before,('RAW header changed while viewing',[(hex(i),x,y)for i,(x,y)in enumerate(zip(before,after))if x!=y][:30]))
 if failure:
  require(len(m.pixel_requests)==int(failure[0]==2),'failed prepare reached hardware driver')
  return dict(failure_mode=failure[0],injected_error=failure[1],result=result,completed_driver_requests=len(m.pixel_requests),shared_unchanged=True,header_unchanged=True)
 requests=[]
 for call,req in zip(m.stages,m.pixel_requests):
  mode=call[2];expect=target if mode==3 else(SCN[selection-4]if selection else(1616,1080))if mode==1 else(160,120)
  require(tuple(req['pixel_WH'])==expect,('unexpected RAW local preview WH',formats,index,mode,req['pixel_WH'],expect))
  requests.append(dict(callsite=call[0],mode=mode,**req))
 require(len(m.stages)==len(requests),'stage count')
 return dict(selection=selection,index=index,formats=formats,target=target,plan=m.word(CTX+0x7f0),requests=requests,SonyCrop=full,header_unchanged=True)
def getter_probe(raw,symbols,embedded,sony,base=True,raw_format=True):
 m=M(raw,True);addr=0x20180000;m.u.mem_write(addr,bytes(0x15000));m.u.mem_write(addr+0x13fdc+0x248,struct.pack('<II',*sony));m.u.mem_write(addr+0x14a2c,struct.pack('<II',*embedded))
 m.u.mem_write(CTX+0x440+0xa4,struct.pack('<I',2 if raw_format else 4));m.u.mem_write(CTX+0x440+0x224,bytes(4));m.u.mem_write(CTX+0x440+0xb4+0x164,struct.pack('<I',0x13fbc));m.u.mem_write(CTX+0x840,struct.pack('<Q',addr if base else 0))
 value=m.invoke(symbols['aspect_avcam_raw_crop'],(CTX,WORK,WORK+4));expected=next((i+4 for i,row in enumerate(P)if embedded in row),0)if base and raw_format else 0
 require(value==expected,('RAW crop getter scope',embedded,sony,base,raw_format,value,expected));return dict(EMB_WH=embedded,SonyCrop=sony,header_present=base,RAW_present=raw_format,recognized_ratio=value)
def main(a):
 raw=a.avcam.read_bytes();r=json.loads(a.report.read_text());require(SHA(raw)==r['sha256'],'hash mismatch');rows=[]
 for selection in range(4,8):
  for index in range(3):
   for formats in((2,4),(4,2),(2,0),(2,1),(1,2)):rows.append(scenario(raw,selection,index,formats,r['symbols']))
 controls=[scenario(raw,0,0,formats,r['symbols'])for formats in((2,4),(4,2),(2,0),(2,1),(1,2))]
 failures=[scenario(raw,5,0,(2,4),r['symbols'],(mode,error))for mode in(3,1,2)for error in(1,2)]
 getters=[getter_probe(raw,r['symbols'],embedded,sony,base,fmt)for embedded,sony,base,fmt in[(P[0][0],FULLS[0],True,True),(FULLS[0],P[0][0],True,True),((9504,3512),P[0][0],True,True),(P[0][0],FULLS[0],False,True),(P[0][0],FULLS[0],True,False)]]
 result=dict(passed=True,cases=len(rows),native_controls=len(controls),failure_cases=len(failures),getter_cases=len(getters),AVCAM_sha256=SHA(raw),rows=rows,control_rows=controls,failure_rows=failures,getter_rows=getters,camera_io=False,device_tested=False,
 native=['actual1f4160 format constructors and1f5388 RAW header getter','actual natural plan and206f70 RAW EMB stage','nativeprepare/resize/commit requests'],models=['packet/RAWheader EMB target is explicit CP boundary fixture; SonyCropfullframe','YC resources, allocation, driver returns and CPUgrayscale resize are reference models'],limits=['No encoder/card/rawfile or complete scheduler','CPheader source separately verified byCPagent'])
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k]for k in('passed','cases','native_controls','failure_cases','getter_cases')}))
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in('avcam','report','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();require(not a.output.exists(),'exists');main(a)
