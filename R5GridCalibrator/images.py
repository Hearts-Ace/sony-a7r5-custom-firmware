import io,hashlib
import numpy as np
from PIL import Image,ImageCms,ImageOps

def decode(data):
    if len(data)>96*1024**2:raise ValueError('每张图最多96 MiB')
    if data[:4] in (b'II*\0',b'MM\0*'):
        import tifffile
        with tifffile.TiffFile(io.BytesIO(data)) as f:
            if len(f.pages)!=1:raise ValueError('TIFF必须单页')
            p=f.pages[0]
            if int(p.photometric)!=2 or len(p.shape)!=3 or p.shape[-1]!=3 or p.dtype not in (np.dtype('uint8'),np.dtype('uint16')):raise ValueError('TIFF须为8/16位RGB')
            if p.shape[0]*p.shape[1]>80000000:raise ValueError('图片最多8000万像素')
            if 'Orientation' in p.tags and int(p.tags['Orientation'].value)!=1:raise ValueError('请先将方向归一化后再导入')
            icc=p.tags['InterColorProfile'].value if 'InterColorProfile' in p.tags else None
            a=p.asarray();bits=a.dtype.itemsize*8
    else:
        with Image.open(io.BytesIO(data)) as f:
            # Sony JPEG may contain MPF auxiliary images and Pillow identifies it as MPO.
            # Decode the primary full-resolution frame, never an embedded auxiliary frame.
            if f.format=='MPO':f.seek(0)
            if f.format not in ('JPEG','MPO','PNG') or f.mode!='RGB':raise ValueError('仅支持RGB JPG、PNG或TIFF')
            if f.width*f.height>80000000:raise ValueError('图片最多8000万像素')
            icc=f.info.get('icc_profile')
            normalized=ImageOps.exif_transpose(f)
            if icc:
                try:
                    profile=ImageCms.ImageCmsProfile(io.BytesIO(bytes(icc)))
                    normalized=ImageCms.profileToProfile(normalized,profile,ImageCms.createProfile('sRGB'),outputMode='RGB')
                except Exception as error:raise ValueError('JPG/PNG的ICC损坏或无法转换为sRGB：'+str(error)) from error
            a=np.array(normalized);bits=8
            return a,bits,'ICC-converted-sRGB; EXIF-normalized' if icc else 'untagged-assumed-sRGB; EXIF-normalized'
    if icc:
        p=ImageCms.ImageCmsProfile(io.BytesIO(bytes(icc)))
        if 'srgb' not in ImageCms.getProfileDescription(p).lower().replace(' ',''):raise ValueError('请先将两张图转换为sRGB')
    return a,bits,'embedded-sRGB' if icc else 'untagged-assumed-sRGB'

def sample(before,after,columns=64):
    a,ab,ap=decode(before);b,bb,bp=decode(after)
    if a.shape!=b.shape:raise ValueError('两图尺寸必须相同，不会自动缩放或自动调色对齐')
    h,w,_=a.shape
    if min(h,w)<128:raise ValueError('图片短边至少128像素')
    cols=min(columns,w//8);rows=max(8,min(64,round(cols*h/w)))
    xs=[];ys=[];buckets=[];coords=[];rejected=0
    for r in range(rows):
        for c in range(cols):
            y0,y1=int((r+.2)*h/rows),int((r+.8)*h/rows)
            x0,x1=int((c+.2)*w/cols),int((c+.8)*w/cols)
            aa=a[y0:y1,x0:x1].astype(float)/(2**ab-1);ba=b[y0:y1,x0:x1].astype(float)/(2**bb-1)
            mean=aa.mean((0,1));target=ba.mean((0,1))
            # High gradients are unreliable for unregistered image pairs. No color-delta based rejection.
            if max(float(aa.std((0,1)).max()),float(ba.std((0,1)).max()))>.10 or np.any(mean<.01) or np.any(mean>.99) or np.any(target<.005) or np.any(target>.995):
                rejected+=1;continue
            xs.append(mean);ys.append(target);coords.append([c,r])
            # Whole neighboring 4x4 tiles share split, reducing spatial leakage.
            buckets.append(((r//4)*13+(c//4)*7)%10)
    if len(xs)<40:raise ValueError(f'JPG已成功解码（{w}×{h}），但有效采样块只有{len(xs)}个/{cols*rows}，纹理或剪切剔除{rejected}个；请使用更多平坦颜色区域并固定机位')
    audit=dict(width=w,height=h,bits=[ab,bb],profiles=[ap,bp],blocks=len(xs),rejected=rejected,
               columns=cols,rows=rows,source_sha256=[hashlib.sha256(v).hexdigest() for v in (before,after)],
               sampling='central 60% tile mean; reject std>.10 or clipped means; 4x4-block spatial split',
               alignment='User-aligned same dimensions; no automatic exposure/WB/geometry correction')
    return dict(x=np.asarray(xs).tolist(),y=np.asarray(ys).tolist(),buckets=buckets,positions=coords),audit
