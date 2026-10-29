"""Fixed measured ST chart interchange; no interpolation of unseen colors."""
import io
import json
import zipfile
import numpy as np
import core

COLUMNS, ROWS, TILE = 74, 50, 32
WIDTH, HEIGHT = COLUMNS*TILE, ROWS*TILE
LAYOUT = 'r5-st-measured-3700-row-major-v1'
MAX_BYTES = 1024*1024*1024


def manifest(dataset_id=None):
    from chart_datasets import get
    dataset=get(dataset_id)
    return dict(dataset.metadata(),schema=dataset.DATASET_ID,
        order='row-major pairs.npz sample order',colorspace='sRGB encoded RGB')


def raw_file(dataset_id=None,format='raf'):
    from chart_datasets import get
    if format not in ('raf','arw','dng'):
        raise ValueError('不支持的色卡格式')
    dataset=get(dataset_id)
    m=dataset.metadata()
    if format+'_file' not in m:
        raise ValueError('此历史色卡未提供该格式下载')
    name=m[format+'_file']
    path=dataset.FOLDER/name
    data=path.read_bytes() if path.is_file() else __import__('gzip').decompress((dataset.FOLDER/(name+'.gz')).read_bytes())
    if core.sha(data)!=m[format+'_sha256']:
        raise ValueError('色卡文件散列不符')
    return name,data

def download(dataset_id=None):
    m=manifest(dataset_id)
    name,raw=raw_file(dataset_id)
    package=io.BytesIO()
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name,raw)
        archive.writestr('layout.json',json.dumps(m,indent=2))
        note=('v4.5：Sony 5300K 白平衡已在 Bayer 中补偿，DNG 保留相同码值和 WB，RAF 经 IED 转换不加增益。保留文件的拍摄白平衡；跨机型 Kelvin 显示可以不同，不要在富士软件强改为5300K。全部99372块中心模拟输入已与新版Edit实采逐值核对；最终PT输出仅1块绿色通道差11个原生码值，未加实采补偿。' if m.get('version')=='4.5' else '历史 v4：unity-WB；模拟输入已与 Edit PT 实采核对。')
        archive.writestr('使用说明.txt',note+'\n11648×8736，32×32 色块，共99372块。导出同尺寸 RGB JPG 或8/16位TIFF，推荐16位；支持 sRGB 或 RGB ICC，转换后使用中心横向5点均值。保留方向，不缩放、不裁切、不做几何修正。\n上传时必须选择同一色卡版本，不要混用旧目标。照片空间前端仍为近似。\n')
    return package.getvalue()


def check_profile(icc):
    if not icc:
        return 'untagged-assumed-sRGB'
    from PIL import ImageCms
    profile = ImageCms.ImageCmsProfile(io.BytesIO(bytes(icc)))
    if profile.profile.xcolor_space.strip()!='RGB':
        raise ValueError('目标图需要 RGB ICC 配置文件')
    return ImageCms.getProfileDescription(profile).strip()


def decode(data,dataset_id=None):
    from chart_datasets import get
    dataset=get(dataset_id)
    if not 0 < len(data) <= MAX_BYTES:
        raise ValueError('目标图大小必须在 1 GiB 内')
    if data[:4] in (b'II*\x00',b'MM\x00*'):
        import tifffile
        with tifffile.TiffFile(io.BytesIO(data)) as file:
            # SILKYPIX appends an unflagged 160x120 thumbnail IFD. Accept one
            # chart image plus small RGB thumbnails; reject ambiguous images.
            sizes=((HEIGHT,WIDTH,3),(6336,9504,3),(8736,11648,3),(8735,11648,3))
            candidates=[p for p in file.pages if tuple(p.shape) in sizes]
            if len(candidates)!=1 or any(p not in candidates and
                (len(p.shape)!=3 or p.shape[-1]!=3 or max(p.shape[:2])>512 or int(p.photometric)!=2) for p in file.pages):
                raise ValueError('TIFF 只能含一张完整 RGB 色卡及可选小尺寸 RGB 缩略图')
            page=candidates[0]
            if tuple(page.shape) not in ((HEIGHT,WIDTH,3),(6336,9504,3),(8736,11648,3),(8735,11648,3)) or int(page.photometric)!=2 or (page.dtype.kind!='u' or page.dtype.itemsize not in (1,2)):
                raise ValueError('TIFF 必须为11648×8736（v4）或旧版2368×1600/9504×6336，三通道RGB、8/16位')
            if int(page.tags['Orientation'].value if 'Orientation' in page.tags else 1)!=1:
                raise ValueError('请按原方向导出，不要旋转色卡')
            icc=page.tags['InterColorProfile'].value if 'InterColorProfile' in page.tags else None
            profile=check_profile(icc)
            try:
                pixels=page.asarray(maxworkers=8)
            except (ValueError,NotImplementedError) as error:
                raise ValueError('无法读取此 TIFF 压缩方式，请导出无压缩 TIFF') from error
            kind='tiff'
    elif data[:3]==b'\xff\xd8\xff':
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ('JPEG','MPO') or image.size not in ((WIDTH,HEIGHT),(9504,6336),(11648,8736),(11648,8735)) or image.mode!='RGB':
                raise ValueError('JPG 必须为11648×8736（v4）或旧版2368×1600/9504×6336，三通道RGB')
            if image.getexif().get(274,1)!=1:
                raise ValueError('请按原方向导出，不要旋转色卡')
            icc=image.info.get('icc_profile')
            profile=check_profile(icc)
            pixels=np.array(image)
            kind='jpg'
    else:
        raise ValueError('请选择 TIFF 或 JPG 目标图')
    bits=pixels.dtype.itemsize*8
    # Average only the interior; avoid JPEG ringing and color-block boundaries.
    is_v4=pixels.shape[1]==11648
    if not is_v4 and dataset.DATASET_ID != __import__('v4_dataset').DATASET_ID:
        raise ValueError('v4.5 必须使用完整一亿像素新版色卡导出图')
    if is_v4:
        import v4_dataset
        # LibRaw can drop the first row of the odd-top recommended crop.
        offset=8736-pixels.shape[0]
        probes=np.empty((v4_dataset.ROWS,v4_dataset.COLUMNS,5,3),dtype=pixels.dtype)
        for row in range(v4_dataset.ROWS):
            strip=pixels[row*32+16-offset]
            probes[row]=strip.reshape(v4_dataset.COLUMNS,32,3)[:,14:19,:]
        probes=probes.reshape(-1,5,3)/(2**bits-1)
        from exact_icc import to_srgb
        probes,conversion=to_srgb(probes,icc)
        samples=probes.mean(1)
    elif pixels.shape[:2]==(6336,9504):
        import anchor_dataset
        with np.load(anchor_dataset.PAIRS,allow_pickle=False) as p:coords=p['coords']
        # Raw sample centers minus ActiveArea crop origin; clamp at outer chart boundaries.
        from exact_icc import to_srgb
        samples=[]
        for x,y in coords:
            probes=pixels[max(0,int(y)-26):min(6336,int(y)-13),max(0,int(x)-38):min(9504,int(x)-25)]/(2**bits-1)
            converted,conversion=to_srgb(probes,icc)
            samples.append(converted.mean((0,1)))
        samples=np.asarray(samples)
    else:
        blocks=pixels.reshape(ROWS,TILE,COLUMNS,TILE,3)[:,8:24,:,8:24,:]
        from exact_icc import to_srgb
        blocks,conversion=to_srgb(blocks/(2**bits-1),icc)
        samples=blocks.mean(axis=(1,3)).reshape(-1,3)
    layout=manifest(dataset.DATASET_ID) if is_v4 else dict(schema=LAYOUT,samples=COLUMNS*ROWS,width=WIDTH,height=HEIGHT)
    audit=dict(layout, target_kind='chart-image', source_sha256=core.sha(data),
               file_format=kind,bits_per_channel=bits,icc_policy=profile,target_width=int(pixels.shape[1]),target_height=int(pixels.shape[0]),
               icc_conversion=conversion,layout_requires_user_preservation=True)
    if is_v4:audit['patch_sampling']=__import__('patch_sampling').POLICY
    return samples,audit


def prepare(data, output, source_path=None,dataset_id=None):
    samples, chart_audit=decode(data,dataset_id)
    arrays,audit=core.measured_inputs(chart_audit['schema'] if chart_audit['schema']!=LAYOUT else 'legacy')
    if len(samples)!=len(arrays['input']):
        raise ValueError('目标图与训练输入样本数量不符')
    if source_path is None:
        (output/'target-image.bin').write_bytes(data)
    else:
        from file_storage import copy_independent
        copy_independent(source_path,output/'target-image.bin')
        import hashlib
        with (output/'target-image.bin').open('rb') as stream:
            copied_sha=hashlib.file_digest(stream,'sha256').hexdigest()
        if copied_sha!=chart_audit['source_sha256']:
            raise ValueError('目标原图在复制过程中发生变化')
    (output/'chart_target.json').write_text(json.dumps(chart_audit,indent=2)+'\n')
    arrays['0_target']=samples*16383
    arrays.pop('1_target',None)
    np.savez_compressed(output/'pairs.npz',**arrays)
    import baseline
    audit.update(chart_audit,context=baseline.resolve(audit.get('dataset_id'))[1],photo_training=False,
                 target_source_sha256=core.sha(data), reference_mode=chart_audit['schema'])
    (output/'input_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
