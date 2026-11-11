#!/usr/bin/env python3
"""原生HEIF request→MC image→硬件clip参数；不执行设备或编码。"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_avcam import Replay,require
from unicorn import arm64_const as A
CTX=0x20001000;GEO=0x20010000;INPUT=0x20011000;OUTPUT=0x20012000
PARAM=0x20013000;RESULT=0x20014000;META=0x20100000;MC=0x20050000
MSG=0x20160000;WORK=0x20161000;CONFIG=0x20162000;BASE=0xffffffc001000000
SIZES=((9504,6336),(6240,4160),(4752,3168))
TARGETS=(((9504,5872),(6240,3856),(4752,2936)),((9504,3976),(6240,2608),(4752,1992)),
         ((7920,6336),(5200,4160),(3968,3168)),((9504,5136),(6240,3376),(4752,2568)))
class Clip(Replay):
 def __init__(self,raw):
  super().__init__(raw);self.payload=None;self.lower=None;self.config=None;self.picture=None;self.resizes=[];self.allocations=[]
  for at in range(0x373400,0x3734c0,8):
   value=struct.unpack_from('<Q',raw,at)[0]
   if BASE<value<BASE+len(raw):self.u.mem_write(at,struct.pack('<Q',value-BASE))
 def ret(self,value=0):
  self.u.reg_write(A.UC_ARM64_REG_X0,value);self.u.reg_write(A.UC_ARM64_REG_PC,self.u.reg_read(A.UC_ARM64_REG_LR))
 def hook(self,u,at,size,data):
  if at in (0x1f7c84,0x20bd88,0x27a078,0x27a0b8,0x2621ac,0x2622c4,0x2003c0,0x207e14,0x209444,0x209c78,0x209e00):return self.ret()
  if at in (0x208658,0x2087c0,0x2088ac):return self.ret(1000000)
  if at==0x209fe4:
   owner,source,kind,si,di,out=[u.reg_read(getattr(A,'UC_ARM64_REG_X'+str(i)))for i in range(6)]
   self.allocations.append(kind)
   handle=201 if kind==0x4cb else 301
   u.mem_write(si+0x18,struct.pack('<QI',0x50000000 if source==201 else 0x40000000,160000000));u.mem_write(di+0x18,struct.pack('<QI',0x50000000 if kind==0x4cb else 0x60000000,74*1024*1024));u.mem_write(out,struct.pack('<I',handle))
   u.mem_write(owner,struct.pack('<IHH',handle,2,0));u.mem_write(owner+0x28,b'\1');return self.ret()
  if at in (0x1fb3c8,0x1fb6f8,0x1fb5e4):
   p=u.reg_read(A.UC_ARM64_REG_X2)
   self.resizes.append(dict(source=list(struct.unpack('<8H',u.mem_read(p+0x50,16))),target=list(struct.unpack('<10H',u.mem_read(p+0xd8,20)))))
   return self.ret(1)
  if at==0x1f8d14:return self.ret(1)
  if at==0x1f9a10:
   u.mem_write(u.reg_read(A.UC_ARM64_REG_X1),struct.pack('<I',7));return self.ret()
  if at==0x1f9a64:
   self.payload=bytes(u.mem_read(u.reg_read(A.UC_ARM64_REG_X3),0x58));return u.emu_stop()
  if at==0x1a9c84:
   self.lower=bytes(u.mem_read(u.reg_read(A.UC_ARM64_REG_X2),u.reg_read(A.UC_ARM64_REG_X3)));return u.emu_stop()
  if at==0x228530:
   self.config=bytes(u.mem_read(u.reg_read(A.UC_ARM64_REG_X2),0x118));return u.emu_stop()
  if at==0x2285bc:
   self.picture=bytes(u.mem_read(u.reg_read(A.UC_ARM64_REG_X2),0x228));return u.emu_stop()
  if at==0x26213c:return self.ret()
  if at==0x27a5d4:
   d,s,n=[u.reg_read(getattr(A,'UC_ARM64_REG_X'+str(i)))for i in range(3)]
   require(n<=4096,'memcpy异常');u.mem_write(d,bytes(u.mem_read(s,n)));return self.ret(d)
  if at in (0x27a5ec,0x2f67c):
   d,v,n=[u.reg_read(getattr(A,'UC_ARM64_REG_X'+str(i)))for i in range(3)]
   require(n<=0x70000,'memset异常');u.mem_write(d,bytes([v&255])*n);return self.ret(d)
  return super().hook(u,at,size,data)
 def invoke(self,start,args=(),stop=0x40000000,extra=()):
  sp=0x3001e000
  for i,v in enumerate(args):self.u.reg_write(getattr(A,'UC_ARM64_REG_X'+str(i)),v)
  for i,v in enumerate(extra):self.u.mem_write(sp+8*i,struct.pack('<Q',v))
  self.u.reg_write(A.UC_ARM64_REG_SP,sp);self.u.reg_write(A.UC_ARM64_REG_LR,0x40000000)
  self.u.emu_start(start,stop,count=300000)
  require(self.u.reg_read(A.UC_ARM64_REG_PC) in (stop,0x1f9a64,0x1a9c84,0x228530,0x2285bc),'原生路径未完成或未到指定边界')
  require(not self.errors,'原生diagnostic触发：'+str(self.errors))
  return self.u.reg_read(A.UC_ARM64_REG_X0)
def setup(m,formats,selection,size_enum=0,slot=1,slot_sizes=None):
 native=SIZES[size_enum];target=native if selection<4 else TARGETS[selection-4][size_enum]
 packet=bytearray(0x800);struct.pack_into('<I',packet,0,2)
 for i,fmt in enumerate(formats):
  size=slot_sizes[i] if slot_sizes else size_enum
  native_i=SIZES[size];target_i=native_i if selection<4 else TARGETS[selection-4][size]
  struct.pack_into('<I',packet,0x1b0+i*12,fmt);packet[0x1b4+i*12]=size
  struct.pack_into('<2H',packet,0x1b6+i*12,*(target_i if fmt==4 else native_i))
 template=0x1e8+0x12c;struct.pack_into('<I',packet,template+4,0x100);struct.pack_into('<I',packet,template+0x44,0x1000)
 m.u.mem_write(CTX,bytes(0x1000));m.u.mem_write(MSG,bytes(packet));m.run(0x1f4088,args=(CTX+0x440,MSG))
 m.u.mem_write(CTX+0x828,struct.pack('<Q',META));m.u.mem_write(CTX+0x41c,struct.pack('<I',101));m.u.mem_write(CTX+0x434,struct.pack('<I',102))
 m.u.mem_write(CTX+0x898,struct.pack('<Q',0x20020000))
 m.u.mem_write(INPUT,struct.pack('<IIQI',0,101 if slot==1 else 102,0x40000000,160000000))
 m.u.mem_write(OUTPUT,struct.pack('<IIQI',0,201,0x50000000,16000000));m.u.mem_write(PARAM,struct.pack('<3I',size_enum,1,0))
 m.u.mem_write(CTX+0x81c,struct.pack('<I',1))
 for k in range(6):m.u.mem_write(CTX+0x850+8*k,struct.pack('<Q',0x20020000+0x100*k))
 m.u.reg_write(A.UC_ARM64_REG_X21,slot)
 return (SIZES if selection<4 else TARGETS[selection-4])[slot_sizes[0 if slot==1 else 1]] if slot_sizes else target
def encode(m,mode,geometry):
 m.u.mem_write(GEO,struct.pack('<6H',*geometry));before=bytes(m.u.mem_read(CTX+0x3bc,0x80))
 m.invoke(0x200734,(0,mode,CTX,INPUT,GEO,OUTPUT,PARAM,RESULT))
 require(m.payload is not None,'未到真实10e request')
 require(bytes(m.u.mem_read(CTX+0x3bc,0x80))==before,'编码改写共享YC')
 return struct.unpack_from('<10H',m.payload,0x34)
def downstream(m):
 m.u.mem_write(MC,bytes(0x2800));node=0x20150000;sub=node+0x100;log=node+0x200;entry=node+0x1000
 m.u.mem_write(MC+0x2558,struct.pack('<Q',node));m.u.mem_write(node+0x18,m.payload[:8]);m.u.mem_write(node+0x20,struct.pack('<Q',sub))
 m.u.mem_write(MC+0x2668,struct.pack('<Q',log));m.u.mem_write(MC+0xf00,struct.pack('<I',1));m.u.mem_write(MC+0xf10,struct.pack('<Q',entry))
 m.u.mem_write(MSG,m.payload);m.invoke(0x1a944c,(MC,MSG));require(m.lower is not None and len(m.lower)==0x68,'未到2103/104 request')
 m.u.mem_write(MSG,m.lower[8:]);m.u.mem_write(MC+0xc9bf8,struct.pack('<Q',log));m.invoke(0x25d9bc,(MC,MSG,WORK),stop=0x25db8c)
 # 与25df2c/25df40队列的两次字节复制相同。
 m.u.mem_write(MSG+0x60,bytes(m.u.mem_read(WORK,0xb0)));m.invoke(0x25e7a4,(MC,MSG));require(m.config is not None,'未到MC encoder config')
 m.u.mem_write(CONFIG,m.config);m.invoke(0x21ee94,(MC,CONFIG,WORK,WORK+0x100),stop=0x21f168)
 hw=dict(enabled=m.u.mem_read(WORK+1,1)[0],origin=list(struct.unpack('<2I',m.u.mem_read(WORK+4,8))),source_param_geometry=list(struct.unpack_from('<10H',m.config,0xe0)),mc_config_hex=m.config.hex(),source_param_stop="0x21f168",source_param_hex=bytes(m.u.mem_read(WORK,0x40)).hex())
 # 真实每tile picture producer；这里只核原生生成的地址，不在固件手改物理地址。
 nx,ny,tw,th=struct.unpack('<4I',m.u.mem_read(MSG+0x60+0x9c,16));hw['tiles']=[]
 canvas=struct.unpack('<H',m.u.mem_read(MSG+0x1c,2))[0];physical=struct.unpack('<Q',m.u.mem_read(MSG+0x10,8))[0]
 for index in range(nx*ny):
  x,y,padx,pady=struct.unpack('<4I',m.u.mem_read(MSG+0x60+0xc+16*index,16))
  m.picture=None;m.invoke(0x2627b8,(MC,MSG,index));require(m.picture is not None,'未到原生tile picture边界')
  address=struct.unpack_from('<Q',m.picture,0x10)[0]
  require(address==physical+(y*((canvas+63)&~63)+x)*5//2,'tile原生地址步进错误')
  require(struct.unpack_from('<2H',m.picture,0x210)==(tw,th),'tile picture WH缺失')
  hw['tiles'].append(dict(index=index,offset=[x,y],padding=[padx,pady],physical_address=address,picture_packet_hex=m.picture.hex()))
 return hw
def verify(raw,old,report):
 # 四个真实caller均给x4传栈局部geometry，w21保持原生HEIF slot选择。
 for instruction,offset in ((0x20014c,0x28),(0x2010cc,0xd8),(0x201100,0x88),(0x201130,0x38)):
  require(struct.unpack_from('<I',raw,instruction)[0]==0x910003e4|(offset<<10),'caller局部geometry合同变化')
 callers=[]
 for at in range(0,0x306000,4):
  word=struct.unpack_from('<I',raw,at)[0]
  if word>>26==0b100101:
   delta=word&0x3ffffff;delta=delta-(1<<26) if delta&(1<<25) else delta
   if at+delta*4==0x1f977c:callers.append(at)
 require(callers==[0x200a68],'request producer出现未经核实caller')
 rows=[]
 for selection in range(4,8):
  for formats in ((4,0),(2,4),(4,2),(4,4),(1,4),(4,1)):
   for slot,fmt in zip((1,16),formats):
    if fmt!=4:continue
    m=Clip(raw);target=setup(m,formats,selection,slot=slot);output=encode(m,0,(9600,6336,9504,6336,0,0))
    require(output[4:6]==target and output[8:10]==target,'main valid/target WH不一致')
    hw=downstream(m);expected={4:(0,232),5:(0,1180),6:(792,0),7:(0,600)}[selection]
    require(tuple(output[2:4])==expected and hw['origin']==list(expected) and hw['enabled']==1,'main硬件clip错误')
    require(struct.unpack('<2I',m.u.mem_read(META+0x100+0x5c,8))==target,'主header WH未同步')
    require(struct.unpack('<2I',m.u.mem_read(META+0x1000+0x4b0,8))==target[::-1],'Sony FullImageSize WH未同步')
    rows.append(dict(selection=selection,formats=list(formats),slot=slot,mode=0,image_geometry=list(output),hardware=hw))
  for mode,geometry in ((1,(1664,1080,1616,1080,0,0)),(2,(384,216,320,212,0,0))):
   m=Clip(raw);setup(m,(2,4),selection,slot=16);output=encode(m,mode,geometry);hw=downstream(m)
   require(tuple(output[2:4])==tuple(hw['origin']),'aux clip未传透');require(output[4:6]==output[8:10],'aux valid/target WH不一致')
   rows.append(dict(selection=selection,formats=[2,4],slot=16,mode=mode,image_geometry=list(output),hardware=hw))
 # 两个原生采样枚举走各自原生image格式映射，ROI均透传。
 for selection in range(4,8):
  for mode,geometry in ((0,(9600,6336,9504,6336,0,0)),(1,(1664,1080,1616,1080,0,0))):
   m=Clip(raw);setup(m,(2,4),selection,slot=16);m.u.mem_write(CTX+0x88,struct.pack('<I',1))
   image=encode(m,mode,geometry);hw=downstream(m)
   require(hw['origin']==list(image[2:4]) and hw['enabled']==1,'采样枚举1的原生clip错误')
   rows.append(dict(selection=selection,formats=[2,4],slot=16,mode=mode,native_sampling_mode=1,image_geometry=list(image),hardware=hw))
 # M/S：HEIF-only源就是该尺寸；RAW配对从L源按自然plan7进入resize。
 for selection in range(4,8):
  for size_enum in (1,2):
   w,h=SIZES[size_enum];m=Clip(raw);target=setup(m,(4,0),selection,size_enum)
   output=encode(m,0,((w+127)&~127,h,w,h,0,0));hw=downstream(m)
   require(output[4:6]==target and hw['origin']==list(output[2:4]),'M/S HEIF-only clip错误')
   rows.append(dict(selection=selection,formats=[4,0],slot=1,mode=0,size_enum=size_enum,image_geometry=list(output),hardware=hw))
   for formats,slot in (((2,4),16),((4,2),1)):
    m=Clip(raw);target=setup(m,formats,selection,size_enum,slot)
    m.u.mem_write(CTX+(0x4e8 if formats[0]==2 else 0x668),struct.pack('<I',0))
    plan=m.invoke(0x1f455c,(CTX+0x440,WORK,WORK+4));m.u.mem_write(CTX+0x7f0,struct.pack('<I',plan))
    for off in (0x410,0x428):m.u.mem_write(CTX+off,struct.pack('<6H',9600,6336,9504,6336,0,0))
    item=0x20015000;m.u.mem_write(item,struct.pack('<Q',CTX));result=m.invoke(0x207378,(item,))
    require(result==0 and len(m.resizes)==1 and plan==7,'M/S自然plan7 resize未完成')
    require(m.allocations==[0x4cb],'M/S原生目标资源class改变')
    source=m.resizes[0]['source'];require(source[2:4]!=[0,0],'M/S resize未消费中心ROI')
    g=struct.unpack('<6H',m.u.mem_read(CTX+(0x410 if slot==1 else 0x428),12))
    require(g[2:4]==target and g[4:6]==(0,0),'M/S原生post未物化目标')
    require(g[0]*g[1]*5//2<=74*1024*1024,'M/S超出原生资源容量')
    owner=0x20016000;m.invoke(0x2079ec,(owner,))
    gathered=m.invoke(0x2003f0,(0,slot,0,0,CTX,owner,INPUT,GEO),extra=(OUTPUT,PARAM))
    require(gathered==0 and m.word(INPUT+4)==201,'原生gather未消费post后的目标handle')
    require(struct.unpack('<Q',m.u.mem_read(INPUT+8,8))[0]==0x50000000,'gather消费了resize前原资源')
    require(bytes(m.u.mem_read(GEO,12))==struct.pack('<6H',*g),'原生gather没有复制已物化geometry')
    m.u.reg_write(A.UC_ARM64_REG_X21,slot);output=encode(m,0,g);hw=downstream(m)
    require(output[4:6]==target and hw['origin']==[0,0] and hw['enabled']==0,'M/S重复裁切已物化输出')
    rows.append(dict(selection=selection,formats=list(formats),slot=slot,mode=0,size_enum=size_enum,native_plan=plan,resize=m.resizes[0],image_geometry=list(output),hardware=hw))
 # 相同Share handle不能把RAW首slot误当本次HEIF；4/4不同size按原生w21逐slot消费。
 for selection in range(4,8):
  m=Clip(raw);target=setup(m,(2,4),selection,slot=16)
  m.u.mem_write(CTX+0x434,struct.pack('<I',101));m.u.mem_write(INPUT+4,struct.pack('<I',101))
  image=encode(m,0,(9600,6336,9504,6336,0,0));require(image[4:6]==target,'相同handle误选RAW slot')
  rows.append(dict(selection=selection,formats=[2,4],slot=16,shared_handle=True,image_geometry=list(image)))
  for sizes in ((0,1),(1,0)):
   for slot in (1,16):
    m=Clip(raw);target=setup(m,(4,4),selection,slot=slot,slot_sizes=sizes)
    m.u.mem_write(CTX+0x434,struct.pack('<I',101));m.u.mem_write(INPUT+4,struct.pack('<I',101))
    for off in (0x410,0x428):m.u.mem_write(CTX+off,struct.pack('<6H',9600,6336,9504,6336,0,0))
    item=0x20015000;m.u.mem_write(item,struct.pack('<Q',CTX));m.u.mem_write(item+0x42,struct.pack('<H',0 if slot==1 else 1))
    result=m.invoke(0x207378,(item,));require(result==0,'双HEIF原生stage失败')
    g=struct.unpack('<6H',m.u.mem_read(CTX+(0x410 if slot==1 else 0x428),12))
    require(bool(m.resizes)==(sizes[0 if slot==1 else 1]!=0),'双HEIF不同size自然resize分派错误')
    owner=0x20016000;m.invoke(0x2079ec,(owner,))
    gathered=m.invoke(0x2003f0,(0,slot,0,0,CTX,owner,INPUT,GEO),extra=(OUTPUT,PARAM))
    require(gathered==0 and m.word(INPUT+4)==(201 if m.resizes else 101),'双slot同handle的gather选错资源')
    m.u.reg_write(A.UC_ARM64_REG_X21,slot);image=encode(m,0,g);hw=downstream(m)
    require(image[4:6]==target,'双HEIF选错slot尺寸')
    rows.append(dict(selection=selection,formats=[4,4],slot=slot,slot_sizes=list(sizes),shared_original_handle=True,native_plan=m.word(CTX+0x7f0),image_geometry=list(image),hardware=hw))
 controls=[]
 for selection in (2,4,5,6,7):
  geometries=[]
  for label,image in (('old',old),('new',raw)):
   m=Clip(image);target=setup(m,(2,4),selection,slot=16)
   geometry=(9600,6336,9504,6336,0,0)
   if label=='old' and selection>=4:
    x,y={4:(0,232),5:(0,1180),6:(792,0),7:(0,600)}[selection]
    geometry=(9600,6336,*target,x,y)
   geometries.append(encode(m,0,geometry))
  if selection==2:require(geometries[0]==geometries[1],'原厂request变化')
  else:require(geometries[0][2:6]==(0,0,0,0) and geometries[1][2:6]!=(0,0,0,0),'旧4.15未被负例拒绝')
  controls.append(dict(selection=selection,old=list(geometries[0]),new=list(geometries[1])))
 for selection in range(4,8):
  for size_enum in range(3):
   for dw,dh in ((-16,0),(16,0),(0,-8),(0,8)):
    outputs=[]
    for image in (old,raw):
     m=Clip(image);w,h=setup(m,(2,4),selection,size_enum,16)
     m.u.mem_write(CTX+0x7e8,struct.pack('<2H',w+dw,h+dh))
     outputs.append(encode(m,0,(9600,6336,9504,6336,0,0)))
    require(outputs[0]==outputs[1],'相邻尺寸被误判为私有比例')
    controls.append(dict(selection=selection,size_enum=size_enum,adjacent=[dw,dh],preserved=True))
  m=Clip(raw);setup(m,(2,4),selection,slot=16);m.u.mem_write(GEO,struct.pack('<6H',9600,6336,9504,6336,0,4))
  result=m.invoke(0x200734,(0,0,CTX,INPUT,GEO,OUTPUT,PARAM,RESULT))
  require(result==2 and m.payload is None,'非法私有源ROI静默回退')
  controls.append(dict(selection=selection,invalid_source_explicit_error=result))
 for aspect in (1,2,3):
  outputs=[]
  for image in (old,raw):
   m=Clip(image);setup(m,(2,4),4,slot=16);m.u.mem_write(CTX+0x66c,struct.pack('<I',aspect))
   before=bytes(m.u.mem_read(META,0x2000));outputs.append(encode(m,0,(9600,6336,9504,6336,0,0)))
   require(bytes(m.u.mem_read(META,0x2000))==before,'原厂aspect的metadata被更改')
  require(outputs[0]==outputs[1],'原厂aspect被误识别为私有')
  controls.append(dict(native_aspect=aspect,request_and_metadata_preserved=True))
 return dict(passed=True,camera_io=False,device_tested=False,rows=rows,controls=controls,
  native=['200734完整入口与1f977c完整request','1a944c真实输入geometry转发到2103/104','25d9bc真实tile目标推导','25e7a4真实MC encoder config几何','21ee94真实10bit步长/clip使能/坐标分支'],
  models=['编码器状态检查和request序号分配成功；不执行编码','日志和不含geometry的codec附加选项为模型','IPC/队列按原生字节复制；原WH、Notify目标、资源handle和输入状态为明确夹具；实际CP Notify另有联动证据','M/S原生class4cb分配/释放与resize driver返回为模型，容量按原生DMM配置74MiB断言'],
  limitations=['未执行硬件像素编码、存储卡写入、机内回放','不以参数通过代替实机验收'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--avcam',type=Path,required=True);p.add_argument('--old',type=Path,required=True)
 p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 require(not a.output.exists(),'拒绝覆盖证据');raw=a.avcam.read_bytes();old=a.old.read_bytes();report=json.loads(a.report.read_text())
 require(hashlib.sha256(raw).hexdigest()==report['sha256'],'AVCAM身份不符');result=verify(raw,old,report)
 result.update(AVCAM_sha256=report['sha256'],old_sha256=hashlib.sha256(old).hexdigest(),test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
 a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(result['rows']),controls=len(result['controls']))))
