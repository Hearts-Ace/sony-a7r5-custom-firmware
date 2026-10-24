"""One v4 BIN containing a zero baseline, nine training probes and two holdouts."""
import copy,hashlib,io,json,zipfile,uuid
import numpy as np
import bin_v4

def sha(data):return hashlib.sha256(data).hexdigest()
def grid(e):return np.asarray(e['grid_5x9x9']['coefficients']).reshape(3,405).T

def build(raw,number,amplitude=12):
    cfg=bin_v4.unpack(raw)
    entries=[e for e in cfg['entries'] if e['number']==int(number)]
    if not entries:raise ValueError('BIN中没有所选配置')
    e=entries[0];amp=int(amplitude)
    if not 1<=amp<=32:raise ValueError('探针幅度须为1–32')
    patterns=[('ZERO','零网格基准','baseline',np.zeros((405,3),int))]
    for axis in range(3):
        for sign in (1,-1):
            g=np.zeros((405,3),int);g[:,axis]=sign*amp
            patterns.append((f'C{axis+1}{"+" if sign>0 else "-"}',f'通道{axis+1} {"正" if sign>0 else "负"}偏移','train',g))
    indices=np.indices((5,9,9))
    for axis,dim in enumerate((5,9,9)):
        coord=indices[axis].reshape(-1)/(dim-1)*2-1
        g=np.zeros((405,3),int);g[:,axis]=np.rint(coord*amp)
        patterns.append((f'RAMP{axis+1}',f'坐标方向{axis+1}渐变','train',g))
    patterns.append(('ORIGINAL','原配置网格（留出测试）','test',grid(e)))
    # Cross-channel/coordinate interactions withheld from optimization and model selection.
    y,u,v=indices.reshape(3,-1)/np.array([4,8,8])[:,None]
    wave=np.rint(amp*np.column_stack([np.sin(np.pi*(y+u)),np.cos(np.pi*(u+v)),np.sin(np.pi*(v-y))])).astype(int)
    patterns.append(('WAVE','交叉波形（留出测试）','test',wave))
    out=[];manifest=[]
    for number,(short,full,role,g) in enumerate(patterns,1):
        record=copy.deepcopy(e);record.update(number=number,short_name=short,full_name=full)
        record['grid_5x9x9']['coefficients']=g.T.reshape(3,5,9,9).tolist();out.append(record)
        manifest.append(dict(number=number,short_name=short,full_name=full,role=role,nonzero=int(np.count_nonzero(g)),grid_sha256=sha(g.astype(np.int8).tobytes())))
    packed=bin_v4.pack(bin_v4.config(out));pid=uuid.uuid4().hex
    meta=dict(id=pid,schema='r5-grid-probe-set/1',source_number=e['number'],source_name=e['full_name'],source_bin_sha256=sha(raw),
              probe_bin_sha256=sha(packed),amplitude=amp,entries=manifest,
              parameter_sha256=sha(json.dumps({k:e[k] for k in ('cc1_delta','block13','gamma_native_129')},sort_keys=True).encode()))
    return packed,meta

def archive(packed,meta):
    z=io.BytesIO()
    with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as f:
        f.writestr('R5NATIVE.BIN',packed);f.writestr('probe_manifest.json',json.dumps(meta,ensure_ascii=False,indent=2))
        f.writestr('SHA256SUMS',sha(packed)+'  R5NATIVE.BIN\n')
        f.writestr('拍摄顺序.csv','编号,简写,名称,用途\n'+'\n'.join(f'{e["number"]},{e["short_name"]},{e["full_name"]},{e["role"]}' for e in meta['entries']))
        f.writestr('拍摄说明.txt',INSTRUCTIONS)
    return z.getvalue()

INSTRUCTIONS='''R5 网格探针：一份BIN，12个配置

此BIN用所选源配置的CC1、block13和129点Gamma复制出12项，仅名称、编号和网格不同。它会完整替换相机原有自定义配置集，请自行保存原BIN，拍完用原文件重新导入。

已有支持BIN v4的4.23/4.24固件无需重复刷固件。把R5NATIVE.BIN放SD根目录，按已有流程关机/开机导入。原厂创意外观固定同一项；自定义滤镜依次选1–12拍摄。不要选择关闭：零网格基准是1 ZERO。

固定机位、光线、手动曝光、ISO、WB及全部右侧调节，使用静态丰富颜色/灰阶色卡。关闭会变化的自动/局部处理。优先同尺寸、同色域sRGB机内JPG，不裁切、缩放或旋转。工具不会自动曝光/白平衡补偿，也不会自动几何对齐。

先拍1 ZERO，再拍2 C1+，检查SD卡JPG确有变化。继续拍2–12，最后再拍一次1 ZERO用于光线漂移检查。11/12作为留出测试，不参与拟合和模型选择。

回到Web选择本次探针组，上传1 ZERO的基准JPG，逐行上传2–12对应JPG；可另建采集批次拍第二场景。所有数据仅保存在本地workspace。原配置若本来全零，11不计入拟合，12仍作为留出。

报告为经验网格响应拟合，不证明唯一恢复ISP内部算法。覆盖不足时追加探针/场景。不要把该模型当成跨ISO/WB/原厂外观通用标定。
'''
