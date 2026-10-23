"""Fixed measured ST chart interchange; no interpolation of unseen colors."""
import io
import json
import zipfile
import numpy as np
import core

COLUMNS, ROWS, TILE = 74, 50, 32
WIDTH, HEIGHT = COLUMNS*TILE, ROWS*TILE
LAYOUT = 'r5-st-measured-3700-row-major-v1'
MAX_BYTES = 64*1024*1024


def manifest():
    import anchor_dataset
    return dict(schema=LAYOUT, width=WIDTH, height=HEIGHT, columns=COLUMNS,
                rows=ROWS, tile=TILE, samples=COLUMNS*ROWS, order='row-major pairs.npz sample order',
                colorspace='sRGB encoded RGB; no extra transfer curve',
                pairs_sha256=core.sha(anchor_dataset.PAIRS.read_bytes()),
                sampling='mean of central 16x16 pixels per tile')


def download():
    import tifffile
    from PIL import ImageCms
    from edit_color_pipeline import RuntimeColor
    arrays, _ = core.measured_inputs()
    rgb = RuntimeColor.from_capture(core.CAPTURE,4).color_only(arrays['input'])[:,4]/16383
    if rgb.shape != (COLUMNS*ROWS,3):
        raise ValueError('色卡样本数量与布局不符')
    image = np.rint(np.clip(rgb,0,1)*65535).astype(np.uint16).reshape(ROWS,COLUMNS,3)
    image = np.repeat(np.repeat(image,TILE,axis=0),TILE,axis=1)
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    target = io.BytesIO()
    tifffile.imwrite(target,image,photometric='rgb',metadata=None,iccprofile=icc)
    package = io.BytesIO()
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('R5-ST-original.tiff',target.getvalue())
        archive.writestr('layout.json',json.dumps(manifest(),indent=2))
        archive.writestr('使用说明.txt',
            '原图为现有实采输入经 ST 颜色子链模型输出的 16 位 sRGB 色卡，并非原始 ARW。\n'
            '在软件中进行全局颜色处理，导出 sRGB RGB TIFF（8/16位）或高质量 JPG（8位）。\n'
            '保持 2368×1600 像素、色块顺序和方向，不裁切、缩放、旋转，不添加边框。\n'
            '不要使用局部蒙版、自动局部调整、锐化或降噪；它们不能由全局颜色参数复现。\n'
            '嵌入 sRGB 配置；无配置文件按 sRGB 解释。非 sRGB 请在软件中转换后导出。\n'
            '上传处理后图像作为目标，原实采输入与训练/验证/测试划分保持不变。\n')
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
        raise ValueError('目标图大小必须在 64 MiB 内')
    if data[:4] in (b'II*\x00',b'MM\x00*'):
        import tifffile
        with tifffile.TiffFile(io.BytesIO(data)) as file:
            if len(file.pages)!=1:
                raise ValueError('仅支持单页 RGB TIFF')
            page=file.pages[0]
            if tuple(page.shape)!=(HEIGHT,WIDTH,3) or int(page.photometric)!=2 or (page.dtype.kind!='u' or page.dtype.itemsize not in (1,2)):
                raise ValueError('TIFF 必须为 2368×1600、三通道 RGB、8 或 16 位整数')
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
            if image.format!='JPEG' or image.size!=(WIDTH,HEIGHT) or image.mode!='RGB':
                raise ValueError('JPG 必须为 2368×1600、三通道 RGB')
            if image.getexif().get(274,1)!=1:
                raise ValueError('请按原方向导出，不要旋转色卡')
            profile=check_profile(image.info.get('icc_profile'))
            pixels=np.array(image)
            kind='jpg'
    else:
        raise ValueError('请选择 TIFF 或 JPG 目标图')
    bits=pixels.dtype.itemsize*8
    # Average only the interior; avoid JPEG ringing and color-block boundaries.
    blocks=pixels.reshape(ROWS,TILE,COLUMNS,TILE,3)[:,8:24,:,8:24,:]
    samples=blocks.mean(axis=(1,3)).reshape(-1,3)/(2**bits-1)
    audit=dict(manifest(), target_kind='chart-image', source_sha256=core.sha(data),
               file_format=kind,bits_per_channel=bits,icc_policy=profile,
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
