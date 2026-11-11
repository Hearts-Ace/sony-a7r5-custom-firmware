#!/usr/bin/env python3
"""真实CP producer/Notify→AVCAM import/view→RAW EMB/辅助resize与HEIF clip联动。

硬件像素由明确的灰度纹理/最近邻CPU模型消费原生请求。资源API是导入夹具，
不将其句柄或共享次数冒充实际MM引用计数。
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

HERE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(HERE),str(HERE/'tests')]
from verify_allocation_failure import Capture
from verify_cp import TASKS,WORK as CP_WORK,STACK,SNAPSHOT,GFW,REQUEST,STOP
from verify_heif_clip import Clip,setup,encode,downstream,CTX,GEO,INPUT,OUTPUT,PARAM,RESULT,META,MSG
from verify_avcam import require
from unicorn import arm_const as C
from unicorn import arm64_const as A

GEOMETRIES=((9600,6336,9504,6336,0,0),(1664,1080,1616,1080,0,0),(384,216,320,212,0,0))
RESOURCE_IDS=(21,22,23)
R_IN,R_OUT,R_TARGET,R_RESOURCE,R_OWNER,R_UNIT=tuple(0x20017000+i*0x1000 for i in range(6))
HISTORICAL_RECEIPTS={
    'CP':('five-cp-install.json','5f5a1f290b276d20be0a3c0cf7db8c93a46ef2abb5c8f11830482d3efec757a2'),
    'AVCAM':('five-avcam-install.json','0db9afb167a8475de4aff48e5ab85a08c0739190c7ab0f37c1cf918c89c3ca5d'),
}


def digest(data):return hashlib.sha256(data).hexdigest()


def fixed_windows(data,receipt,reverse=False):
    """逐窗核前像，只处理确定的定长补丁。"""
    result=bytearray(data)
    rows=reversed(receipt['patches']) if reverse else receipt['patches']
    for row in rows:
        at=row['offset'];before=bytes.fromhex(row['before']);after=bytes.fromhex(row['after'])
        require(isinstance(at,int) and at>=0 and len(before)==len(after)>0,'历史夹具补丁布局不符')
        require('bytes' not in row or row['bytes']==len(before),'历史夹具窗口长度不符')
        require(at+len(before)<=len(result),'历史夹具补丁越界')
        expected,replacement=(after,before) if reverse else (before,after)
        require(result[at:at+len(expected)]==expected,'历史夹具补丁前像不符')
        result[at:at+len(replacement)]=replacement
    return bytes(result)


def historical_forward(data,receipt,output_key):
    require(digest(data)==receipt['input_sha256'],'历史夹具输入摘要不符')
    result=fixed_windows(data,receipt)
    require(digest(result)==receipt[output_key],'历史夹具输出摘要不符')
    return result


def stock_avcam_from_candidate(data,receipt,stock_size,stock_sha):
    require(receipt['passed'] and receipt['reverse_exact'],'当前AVCAM回执未通过反向核验')
    require(digest(data)==receipt['sha256'] and len(data)==receipt['bytes'],'当前AVCAM组件身份不符')
    require(receipt['input_sha256']==stock_sha and receipt['original_bytes']==stock_size,'当前AVCAM原厂基线不符')
    require(receipt['appended_bytes']==len(data)-stock_size>0,'当前AVCAM尾部长度不符')
    # append不在定长patches中，依构建器合同先截原厂长度再逆应用全部窗口。
    result=fixed_windows(data[:stock_size],receipt,reverse=True)
    require(digest(result)==stock_sha,'反向恢复原厂AVCAM摘要不符')
    return result


def historical_fixtures(build,current_avcam,current_receipt):
    receipts={};identities={}
    for kind,(name,expected) in HISTORICAL_RECEIPTS.items():
        path=HERE/'evidence/ratio5x3-20261106'/name;data=path.read_bytes()
        require(digest(data)==expected,'持久历史回执身份不符：'+name)
        row=json.loads(data);require(row['passed'] and row['reverse_exact'],'历史回执未通过')
        receipts[kind]=row;identities[kind]=dict(path=path.relative_to(HERE).as_posix(),sha256=expected)
    baseline=(build/'base/patched/cpapp-b.bin').read_bytes()
    require(digest(baseline)==receipts['CP']['input_sha256'],'历史fixture只适用于锁定五功能组合')
    cp=historical_forward(baseline,receipts['CP'],'output_sha256')
    stock=stock_avcam_from_candidate(current_avcam,current_receipt,receipts['AVCAM']['bytes'],receipts['AVCAM']['input_sha256'])
    avcam=historical_forward(stock,receipts['AVCAM'],'sha256')
    # 确定的损坏注入：摘要、窗口前像和最终摘要都必须明确拒绝。
    negatives=[]
    def rejected(call,label):
        try:call()
        except AssertionError:negatives.append(label)
        else:raise AssertionError('历史夹具损坏未被拒绝：'+label)
    damaged=bytearray(baseline);damaged[0]^=1
    rejected(lambda:historical_forward(bytes(damaged),receipts['CP'],'output_sha256'),'baseline_input_sha256')
    damaged_receipt=json.loads(json.dumps(current_receipt))
    after=bytearray.fromhex(damaged_receipt['patches'][0]['after']);after[0]^=1
    damaged_receipt['patches'][0]['after']=after.hex()
    rejected(lambda:stock_avcam_from_candidate(current_avcam,damaged_receipt,receipts['AVCAM']['bytes'],receipts['AVCAM']['input_sha256']),'reverse_window_preimage')
    damaged_receipt=json.loads(json.dumps(receipts['AVCAM']));damaged_receipt['sha256']='0'*64
    rejected(lambda:historical_forward(stock,damaged_receipt,'sha256'),'historical_output_sha256')
    proof=dict(mechanism='deterministic persistent receipts; in-memory only',receipts=identities,
        CP_baseline=dict(path='base/patched/cpapp-b.bin',sha256=digest(baseline)),
        CP_reconstructed_sha256=digest(cp),stock_AVCAM_reconstructed_sha256=digest(stock),AVCAM_reconstructed_sha256=digest(avcam),
        current_AVCAM_reverse_windows=len(current_receipt['patches']),historical_CP_windows=len(receipts['CP']['patches']),
        historical_AVCAM_windows=len(receipts['AVCAM']['patches']),corruption_rejections=negatives,old_tmp_required=False)
    return (cp,receipts['CP'],avcam),proof


class Raster:
    """真实像素字节行；256个纹理相位复用行存储，不缩小原生坐标空间。"""
    def __init__(self,width,rows):
        self.width=width;self.rows=rows;self.height=len(rows)
        require(all(len(row)==width for row in rows),'像素行宽不符')
    @classmethod
    def texture(cls,width,height,seed):
        base=bytes((x*13+x//17+seed)&255 for x in range(width))
        phases=[base.translate(bytes((v+i)&255 for v in range(256)))for i in range(256)]
        return cls(width,[phases[(y*17+y//37)&255]for y in range(height)])
    def view(self,x,y,width,height):
        require(width>0 and height>0 and 0<=x<=self.width-width and 0<=y<=self.height-height,'像素ROI越界')
        return Raster(width,[row[x:x+width]for row in self.rows[y:y+height]])
    def resize(self,width,height):
        require(width>0 and height>0,'目标像素为零')
        if (width,height)==(self.width,self.height):return self
        indices=[x*self.width//width for x in range(width)];cache={};rows=[]
        for y in range(height):
            row=self.rows[y*self.height//height]
            if row not in cache:cache[row]=bytes(row[x]for x in indices)
            rows.append(cache[row])
        return Raster(width,rows)
    def digest(self):
        h=hashlib.sha256(struct.pack('<2I',self.width,self.height))
        for row in self.rows:h.update(row)
        return h.hexdigest()


FRAMES={i:Raster.texture(g[0],g[1],i*11)for i,g in zip(RESOURCE_IDS,GEOMETRIES)}
FULL=[FRAMES[i].view(0,0,g[2],g[3])for i,g in zip(RESOURCE_IDS,GEOMETRIES)]


def pixels(frame,source,target):
    cw,ch,vx,vy,vw,vh,tx,ty,tw,th=source
    require((cw,ch)==(frame.width,frame.height),'请求canvas与资源像素不符')
    require(tx+tw<=vw and ty+th<=vh,'输入嵌套ROI越界')
    picture=frame.view(vx+tx,vy+ty,tw,th)
    cw,ch,vx,vy,vw,vh,tx,ty,tw,th=target
    require(tx+tw<=vw and ty+th<=vh,'输出嵌套ROI越界')
    picture=picture.resize(tw,th);blank=bytes(vw);rows=[blank]*vh
    cache={}
    for y,row in enumerate(picture.rows):
        if row not in cache:cache[row]=bytes(tx)+row+bytes(vw-tx-tw)
        rows[ty+y]=cache[row]
    return Raster(vw,rows)


class Producer(Capture):
    def hook(self,u,pc,size,data):
        if pc==0xaea0e4:
            u.reg_write(C.UC_ARM_REG_R0,0);u.reg_write(C.UC_ARM_REG_PC,u.reg_read(C.UC_ARM_REG_LR));return
        return super().hook(u,pc,size,data)
    def native(self,pc,arg):
        self.u.reg_write(C.UC_ARM_REG_R0,arg);self.u.reg_write(C.UC_ARM_REG_SP,STACK+0x1ff00)
        self.u.reg_write(C.UC_ARM_REG_LR,STOP|1);self.u.emu_start(pc|1,STOP,count=300000)
        require(self.u.reg_read(C.UC_ARM_REG_PC)==STOP,'CP producer未返回')
    def packet(self,selection,formats):
        self.select(selection);self.request_number+=1;number=self.request_number
        self.write(REQUEST,number);self.resident(0xadf128,SNAPSHOT,GFW,0xdbc)
        task=TASKS;self.write(task+0x5ae8,number);self.resident(0xadd846,task+0x20,SNAPSHOT)
        require(self.call('aspect_task_id',task)==selection,'CP照片快照不符')
        self.write(task+0x5980,formats[0]);self.write(task+0x5988,formats[1])
        for at in (0x5984,0x598c):self.write(task+at,0)
        self.write(task+0x24,2);self.write(task+0x98,0);self.write(task+0x9c,0)
        self.write(task+0x210,0);self.write(task+0x214,0)
        self.u.mem_write(task+0x5b3c,bytes(0x25c))
        template=task+0x5b3c+0x12c
        self.write(template+4,0x100);self.write(template+0x44,0x1000)
        self.u.mem_write(template+0x10,struct.pack('<2I',9504,6336))
        for geo,offset,handle,resource in zip(GEOMETRIES,(0x5f78,0x5fdc,0x5fe8),(0x59f0,0x59f8,0x5a00),RESOURCE_IDS):
            self.u.mem_write(task+offset,struct.pack('<6H',*geo));self.write(task+handle,resource)
        self.write(task+0x5e70,0x2345);self.write(CP_WORK+0x6000,task)
        self.native(0xae7522,CP_WORK+0x6000)
        self.u.mem_write(task+0x224,struct.pack('<10H',9504,6336,1616,1080,320,212,160,120,9504,6336))
        packet=CP_WORK+0x1000;self.u.mem_write(packet,bytes(0x468));frame=STACK+0x1f000
        self.u.mem_write(frame,bytes(0x40));self.size=(9504,6336)
        for reg,value in ((C.UC_ARM_REG_R4,task),(C.UC_ARM_REG_R5,packet),(C.UC_ARM_REG_R9,task+0x5b3c),(C.UC_ARM_REG_SP,frame)):
            self.u.reg_write(reg,value)
        self.u.emu_start(0xae779d,0xae791c,count=300000)
        require(self.u.reg_read(C.UC_ARM_REG_PC)==0xae791c,'CP Notify未返回')
        result=bytearray(self.u.mem_read(packet,0x468))
        # 外围包头生产不在此窗口，明确给定3:2/有效原尺寸说明标记。
        struct.pack_into('<2I',result,0,2,2)
        return bytes(result)


class Consumers(Clip):
    def __init__(self,raw,same_unit):
        self.same_unit=same_unit;self.views={};self.addresses={};self.next_handle=1000
        self.resource_calls=[];self.pixel_requests=[];self.preparing=False
        super().__init__(raw)
    def descriptor(self,pointer,handle):
        entry=self.views[handle]
        self.u.mem_write(pointer+0xc,struct.pack('<I',handle))
        self.u.mem_write(pointer+0x18,struct.pack('<QI',entry['address'],entry['bytes']))
    def hook(self,u,at,size,data):
        if at==0x209bd4:return self.ret()
        if at==0x20838c:return self.ret()
        if at==0x208950:
            p=u.reg_read(A.UC_ARM64_REG_X0);resource=u.reg_read(A.UC_ARM64_REG_X2)
            kind=u.reg_read(A.UC_ARM64_REG_X4);length=u.reg_read(A.UC_ARM64_REG_X5)
            require(resource in FRAMES,'CP resource夹具丢失')
            self.next_handle+=1;handle=self.next_handle;address=0x50000000+resource*0x1000000
            self.views[handle]=dict(resource=resource,address=address,bytes=length,unit=kind)
            self.addresses[address]=FRAMES[resource];self.descriptor(p,handle)
            self.resource_calls.append(dict(native='208950',unit=hex(kind),CP_resource=resource,model_handle=handle,bytes=length))
            return self.ret()
        if at==0x2093d0:
            unit=u.reg_read(A.UC_ARM64_REG_X0);source=u.reg_read(A.UC_ARM64_REG_X1);p=u.reg_read(A.UC_ARM64_REG_X3)
            require(source in self.views and self.views[source]['unit']==unit,'原生duplicate的unit/source不配')
            handle=source
            if not self.same_unit:
                self.next_handle+=1;handle=self.next_handle;self.views[handle]=dict(self.views[source])
            self.descriptor(p,handle)
            self.resource_calls.append(dict(native='2093d0',unit=hex(unit),source_model_handle=source,result_model_handle=handle,same_backing=True))
            return self.ret()
        if at==0x209fe4 and self.preparing:
            source=u.reg_read(A.UC_ARM64_REG_X1);kind=u.reg_read(A.UC_ARM64_REG_X2)
            si=u.reg_read(A.UC_ARM64_REG_X3);di=u.reg_read(A.UC_ARM64_REG_X4);out=u.reg_read(A.UC_ARM64_REG_X5)
            require(source in self.views,'RAW prepare未消费实际导入view')
            self.descriptor(si,source)
            self.next_handle+=1;handle=self.next_handle
            self.views[handle]=dict(resource=None,address=0x90000000+handle*0x1000,bytes={0x4c7:61865984,0x4cc:123731968,0x4cd:4194304,0x4ce:65536}[kind],unit=kind)
            self.descriptor(di,handle);u.mem_write(out,struct.pack('<I',handle))
            self.resource_calls.append(dict(native='209fe4',source_model_handle=source,target_class=hex(kind),model_allocation=True))
            return self.ret()
        if at in (0x1fb3c8,0x1fb6f8,0x1fb5e4) and self.preparing:
            p=u.reg_read(A.UC_ARM64_REG_X2);address=struct.unpack('<Q',u.mem_read(p+0x10,8))[0]
            source=struct.unpack('<10H',u.mem_read(p+0x50,20));target=struct.unpack('<10H',u.mem_read(p+0xd8,20))
            require(address in self.addresses,'原生driver未消费导入资源的地址')
            image=pixels(self.addresses[address],source,target)
            self.pixel_requests.append(dict(driver=hex(at),source=list(source),target=list(target),pixel_WH=[image.width,image.height],pixel_sha256=image.digest()))
            return self.ret(1)
        return super().hook(u,at,size,data)
    def construct_import(self,packet,formats,selection):
        slot=16 if formats[0]==2 else 1
        setup(self,formats,selection,slot=slot)
        self.u.mem_write(MSG,packet);self.u.mem_write(CTX+0x80,struct.pack('<I',2));self.u.mem_write(CTX+0x81c,struct.pack('<I',1))
        self.u.reg_write(A.UC_ARM64_REG_X19,CTX);self.u.reg_write(A.UC_ARM64_REG_X20,MSG);self.u.reg_write(A.UC_ARM64_REG_X23,MSG+4)
        self.invoke(0x1f3b10,stop=0x1f3c7c)
        for entry in (0x203b40,0x203808,0x203988):self.invoke(entry,(CTX,))
        require(tuple(struct.unpack('<4H',self.u.mem_read(CTX+0x7e4,8)))==tuple(struct.unpack_from('<2H',packet,0x1b6)+struct.unpack_from('<2H',packet,0x1c2)),'CP目标WH未沿原生构造传入')
        return slot
    def raw(self,slot):
        rows=[];self.preparing=True
        for mode in (3,1,2):
            before=len(self.pixel_requests)
            result=self.invoke(0x206378,(slot,mode,CTX,R_OWNER,GEO,R_IN,R_TARGET,R_RESOURCE),extra=(R_UNIT,0))
            require(result==0,'RAW原生prepare失败')
            unit=self.word(R_UNIT)
            result=self.invoke(0x206720,(mode,CTX,GEO,R_IN,R_TARGET,R_RESOURCE,unit,0))
            require(result==0 and len(self.pixel_requests)==before+1,'RAW原生resize请求未完成')
            rows.append(dict(mode=mode,unit_type=unit,**self.pixel_requests[-1]))
        self.preparing=False
        return rows
    def heif(self,slot):
        rows=[]
        for mode,offset,h_at in ((0,0x410 if slot==1 else 0x428,0x41c if slot==1 else 0x434),(1,0x3e0,0x33c),(2,0x3ec,0x340)):
            geometry=struct.unpack('<6H',self.u.mem_read(CTX+offset,12));handle=self.word(CTX+h_at)
            view=self.views[handle];self.u.mem_write(INPUT,struct.pack('<IIQI',0,handle,view['address'],view['bytes']))
            self.u.reg_write(A.UC_ARM64_REG_X21,slot);self.payload=None;self.lower=None;self.config=None
            output=encode(self,mode,geometry);hardware=downstream(self)
            # 原厂路径validWH为0，由原生targetWH表示整幅；私有路径二者一致。
            x,y=hardware['origin'];w,h=output[8:10]
            image=FRAMES[view['resource']].view(x,y,w,h)
            rows.append(dict(mode=mode,image_geometry=list(output),hardware=hardware,pixel_WH=[w,h],pixel_sha256=image.digest()))
        return rows


def expectation():
    main=FULL[0].digest();scn=FULL[1].digest()
    src=[384,216,0,0,320,212,0,0,320,212]
    dst=[160,120,0,0,160,120,0,7,160,106]
    thumb=pixels(FRAMES[23],src,dst).digest()
    return [main,scn,thumb]


def verify(cp_raw,cp_report,av_raw,old_cp,old_report,old_av):
    expected=expectation();rows=[];controls=[]
    for label,cbytes,creport,abytes in (('new',cp_raw,cp_report,av_raw),('old415',old_cp,old_report,old_av)):
        producer=Producer(cbytes,creport)
        for selection in ((0,4,5,6,7) if label=='new' else (4,5,6,7)):
            for formats in ((2,4),(4,2)):
                packet=producer.packet(selection,formats)
                for same_unit in ((True,False) if label=='new' else (True,)):
                    m=Consumers(abytes,same_unit);heif_slot=m.construct_import(packet,formats,selection);raw_slot=17-heif_slot
                    raw_before=m.raw(raw_slot)
                    declaration=list(struct.unpack('<10H',m.u.mem_read(CTX+0x36c,20)))
                    correct=[row['pixel_sha256']==value for row,value in zip(raw_before,expected)]
                    # ae78bc..7908将task22c和228重排，当前明确夹具的SCN原WH在第三对。
                    # 这里只核真实传输的原WH说明，不冒充最终RAW文件tag写者。
                    preview_declared=raw_before[1]['pixel_WH']==declaration[4:6]
                    if label=='old415':
                        require(not correct[0] and not preview_declared,'旧4.15未被RAW嵌图拉伸/声明回归拒绝')
                        controls.append(dict(selection=selection,formats=list(formats),RAW_EMB_stretched=True,small_preview_declaration_mismatch=True,raw_requests=raw_before,declaration=declaration))
                        continue
                    require(all(correct),'新RAW实际请求消费像素后改变原幅/辅助图视野')
                    require(preview_declared,'新RAW小预览实际尺寸与原生说明不一致')
                    shared=bytes(m.u.mem_read(CTX+0x3bc,0x80));heif=m.heif(heif_slot)
                    require(bytes(m.u.mem_read(CTX+0x3bc,0x80))==shared,'HEIF改写shared source/view')
                    raw_after=m.raw(raw_slot)
                    require(raw_after==raw_before,'HEIF消费后RAW请求或像素改变')
                    rows.append(dict(selection=selection,formats=list(formats),same_unit_model=same_unit,CP_shared_YC=[list(struct.unpack_from('<6H',packet,0x2b4+i*32))for i in range(3)],
                        declaration=declaration,raw_before=raw_before,HEIF=heif,raw_after=raw_after,resource_calls=m.resource_calls,
                        sequence=['RAW EMB/SCN/THM','HEIF main/SCN/THM native hardware clip parameters','RAW EMB/SCN/THM']))
    return dict(passed=True,camera_io=False,device_tested=False,rows=rows,old415_controls=controls,
        native=['CP ae7522→ade746/784/7c2三YC producer、ae779c..ae791c真实Notify/共享copy',
            'AVCAM1f3b10..1f3c7c真实资源ID/原WH说明/三YC导入及StillInfo构造',
            '203b40/203710主view、203808 SCN与203988 THM import/duplicate分流',
            '206378 RAW模式3/1/2 prepare→206720 resize真实driver请求',
            'HEIF200734→1f977c→1a944c→25d9bc→25e7a4→21ee94实际clip坐标/WH'],
        models=['CP源原WH/资源ID、模板header偏移及外围包头为明确夹具；参数库给原L尺寸，裁后WH来自真实Notify',
            '208950/2093d0导入与duplicate提供同backing的fixture views；覆盖同unit同handle及不同handle，不称实际MM引用计数',
            'RAW209fe4资源准备返回fixture descriptors，class来自实际native prepare；不证明实拍空闲/分配或释放',
            'CPU逐像素灰度纹理、裁切/黑边/最近邻resize消费真实driver/MC clip请求；未执行YC10bit打包、颜色转换或硬件编码',
            '原生请求后的硬件driver/completion及编码状态/IPC边界沿Clip显式模型'],
        limitations=['RAW传感器原始数据/实际RAW文件最终声明、真实codec、写卡/回放和完整资源完成链未执行',
            '声明检查是实际CP原WH→AVCAM说明字段与真实RAW小预览输出请求对应，不冒充最终文件重拍验收',
            '本测试不以夹具句柄或model调用次数证明真实引用计数，真实DMM生命周期证据另列'])


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('build','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();require(not a.output.exists(),'拒绝覆盖证据')
    def load(build):
        cp=(build/'cp/cpapp-b.bin').read_bytes();cr=json.loads((build/'cp/patch.json').read_text())
        av=(build/'avcam/av-cam.bin').read_bytes();ar=json.loads((build/'avcam/patch.json').read_text())
        require(hashlib.sha256(cp).hexdigest()==cr['output_sha256'] and hashlib.sha256(av).hexdigest()==ar['sha256'],'组件身份不符')
        return (cp,cr,av),ar
    current,current_avcam_receipt=load(a.build)
    old,fixture_proof=historical_fixtures(a.build,current[2],current_avcam_receipt)
    result=verify(*current,*old)
    result.update(CP_sha256=hashlib.sha256(current[0]).hexdigest(),AVCAM_sha256=hashlib.sha256(current[2]).hexdigest(),
        old_CP_sha256=hashlib.sha256(old[0]).hexdigest(),old_AVCAM_sha256=hashlib.sha256(old[2]).hexdigest(),
        historical_fixture=fixture_proof,test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(result['rows']),old415_rejections=len(result['old415_controls']))))
