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


def manifest():
    import v4_dataset
    return dict(v4_dataset.metadata(),schema=v4_dataset.DATASET_ID,
        order='row-major pairs.npz sample order',colorspace='sRGB encoded RGB')


def download():
    import v4_dataset
    m=manifest()
    raw=__import__('gzip').decompress((v4_dataset.FOLDER/(m['raf_file']+'.gz')).read_bytes())
    if core.sha(raw)!=m['raf_sha256']:raise ValueError('v4 RAF 色卡散列不符')
    package=io.BytesIO()
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(m['raf_file'],raw)
        archive.writestr('layout.json',json.dumps(manifest(),indent=2))
        archive.writestr('使用说明.txt','默认 Sony unity-WB 一亿像素色卡经 IED 方案转换的 GFX RAF；11648×8736，32×32 色块，共99372块。\n导出同尺寸 RGB JPG 或8/16位TIFF，推荐16位；支持 sRGB 或带 RGB ICC 的目标，非sRGB逐探针以64位精度转换后平均。保留方向，不缩放、不裁切、不做几何修正。\n训练输入由新Sony传感器码值经ITP/unity-WB/SSCS模拟生成，全部色块9探针已与Edit PT实采逐值核对。训练/评估统一使用中心5点均值。实采不作隐藏颜色补偿。\n旧白平衡错误色卡及其训练结果已废弃。照片空间处理预览仍为近似。\n')
    return package.getvalue()


def check_profile(icc):
    if not icc:
        return 'untagged-assumed-sRGB'
    from PIL import ImageCms
    profile = ImageCms.ImageCmsProfile(io.BytesIO(bytes(icc)))
    if profile.profile.xcolor_space.strip()!='RGB':
        raise ValueError('目标图需要 RGB ICC 配置文件')
    return ImageCms.getProfileDescription(profile).strip()


def decode(data):
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
    layout=manifest() if is_v4 else dict(schema=LAYOUT,samples=COLUMNS*ROWS,width=WIDTH,height=HEIGHT)
    audit=dict(layout, target_kind='chart-image', source_sha256=core.sha(data),
               file_format=kind,bits_per_channel=bits,icc_policy=profile,target_width=int(pixels.shape[1]),target_height=int(pixels.shape[0]),
               icc_conversion=conversion,layout_requires_user_preservation=True)
    if is_v4:audit['patch_sampling']=__import__('patch_sampling').POLICY
    return samples,audit


def prepare(data, output, source_path=None):
    samples, chart_audit=decode(data)
    arrays,audit=core.measured_inputs(None if chart_audit['schema']!=LAYOUT else 'legacy')
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
