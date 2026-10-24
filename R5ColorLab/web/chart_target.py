"""Fixed measured ST chart interchange; no interpolation of unseen colors."""
import io
import json
import zipfile
import numpy as np
import core

COLUMNS, ROWS, TILE = 74, 50, 32
WIDTH, HEIGHT = COLUMNS*TILE, ROWS*TILE
LAYOUT = 'r5-st-measured-3700-row-major-v1'
MAX_BYTES = 512*1024*1024


def manifest():
    import anchor_dataset
    return dict(schema=LAYOUT, width=WIDTH, height=HEIGHT, columns=COLUMNS,
                rows=ROWS, tile=TILE, samples=COLUMNS*ROWS, order='row-major pairs.npz sample order',
                colorspace='sRGB encoded RGB; no extra transfer curve',
                pairs_sha256=core.sha(anchor_dataset.PAIRS.read_bytes()),
                sampling='mean of central 16x16 pixels per tile')


def download():
    from pathlib import Path
    raw=__import__('gzip').decompress((Path(__file__).resolve().parent/'data/chart/R5-training-chart.arw.gz').read_bytes())
    if core.sha(raw)!='6549bf051c07745a17fa238cfcf5803cb1f6d10babd64bb119269284e6709c4f':raise ValueError('ARW色卡散列不符')
    package=io.BytesIO()
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('R5-training-chart.ARW',raw)
        archive.writestr('layout.json',json.dumps(manifest(),indent=2))
        archive.writestr('使用说明.txt','索尼R5合成ARW，3700点传感器色块与现有训练输入对应。旧原始传感器及缩略图负载已清零，部分软件需打开RAW后才生成正确预览。\n在显影软件全局调色，导出9504×6336的sRGB RGB JPG或8/16位TIFF；不裁切、缩放、旋转、透视/镜头几何修正。保留原始方向。\n目标导入按原传感器色块中心采样。旧2368×1600模型色卡目标仍支持。软件RAW前端可能与训练输入不同，结果需检查。\n')
    return package.getvalue()


def check_profile(icc):
    if not icc:
        return 'untagged-assumed-sRGB'
    from PIL import ImageCms
    profile = ImageCms.ImageCmsProfile(io.BytesIO(bytes(icc)))
    if 'srgb' not in ImageCms.getProfileDescription(profile).lower().replace(' ', ''):
        raise ValueError('目标图必须转换为 sRGB 后导出，不支持直接指定其他 ICC')
    return 'embedded-sRGB'


def decode(data):
    if not 0 < len(data) <= MAX_BYTES:
        raise ValueError('目标图大小必须在 512 MiB 内')
    if data[:4] in (b'II*\x00',b'MM\x00*'):
        import tifffile
        with tifffile.TiffFile(io.BytesIO(data)) as file:
            if len(file.pages)!=1:
                raise ValueError('仅支持单页 RGB TIFF')
            page=file.pages[0]
            if tuple(page.shape) not in ((HEIGHT,WIDTH,3),(6336,9504,3)) or int(page.photometric)!=2 or (page.dtype.kind!='u' or page.dtype.itemsize not in (1,2)):
                raise ValueError('TIFF 必须为 2368×1600或9504×6336、三通道 RGB、8 或 16 位整数')
            if int(page.tags['Orientation'].value if 'Orientation' in page.tags else 1)!=1:
                raise ValueError('请按原方向导出，不要旋转色卡')
            profile=check_profile(page.tags['InterColorProfile'].value if 'InterColorProfile' in page.tags else None)
            try:
                pixels=page.asarray()
            except (ValueError,NotImplementedError) as error:
                raise ValueError('无法读取此 TIFF 压缩方式，请导出无压缩 TIFF') from error
            kind='tiff'
    elif data[:3]==b'\xff\xd8\xff':
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ('JPEG','MPO') or image.size not in ((WIDTH,HEIGHT),(9504,6336)) or image.mode!='RGB':
                raise ValueError('JPG 必须为 2368×1600或9504×6336、三通道 RGB')
            if image.getexif().get(274,1)!=1:
                raise ValueError('请按原方向导出，不要旋转色卡')
            profile=check_profile(image.info.get('icc_profile'))
            pixels=np.array(image)
            kind='jpg'
    else:
        raise ValueError('请选择 TIFF 或 JPG 目标图')
    bits=pixels.dtype.itemsize*8
    # Average only the interior; avoid JPEG ringing and color-block boundaries.
    if pixels.shape[:2]==(6336,9504):
        import anchor_dataset
        with np.load(anchor_dataset.PAIRS,allow_pickle=False) as p:coords=p['coords']
        # Raw sample centers minus ActiveArea crop origin; clamp at outer chart boundaries.
        samples=np.array([pixels[max(0,int(y)-20-6):min(6336,int(y)-20+7),max(0,int(x)-32-6):min(9504,int(x)-32+7)].mean((0,1)) for x,y in coords])/(2**bits-1)
    else:
        blocks=pixels.reshape(ROWS,TILE,COLUMNS,TILE,3)[:,8:24,:,8:24,:]
        samples=blocks.mean(axis=(1,3)).reshape(-1,3)/(2**bits-1)
    audit=dict(manifest(), target_kind='chart-image', source_sha256=core.sha(data),
               file_format=kind,bits_per_channel=bits,icc_policy=profile,target_width=int(pixels.shape[1]),target_height=int(pixels.shape[0]),
               layout_requires_user_preservation=True)
    return samples,audit


def prepare(data, output):
    samples, chart_audit=decode(data)
    arrays,audit=core.measured_inputs()
    if len(samples)!=len(arrays['input']):
        raise ValueError('目标图与训练输入样本数量不符')
    (output/'target-image.bin').write_bytes(data)
    (output/'chart_target.json').write_text(json.dumps(chart_audit,indent=2)+'\n')
    arrays['0_target']=samples*16383
    arrays.pop('1_target',None)
    np.savez_compressed(output/'pairs.npz',**arrays)
    audit.update(chart_audit,context=4,photo_training=False,
                 target_source_sha256=core.sha(data), reference_mode=LAYOUT)
    (output/'input_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
