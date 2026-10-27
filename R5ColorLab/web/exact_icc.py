"""RGB ICC conversion without the default RGB16 lookup-table approximation.

Float64 processing, relative colorimetric intent, no black point compensation.
Only the final output is quantized to uint16. Original files are read-only.
"""
from pathlib import Path
import ctypes as c
import ctypes.util
import io
import numpy as np
import PIL
from PIL import ImageCms

INTENT_RELATIVE_COLORIMETRIC = 1
CMS_FLAGS_NOOPTIMIZE = 0x0100
TYPE_RGB_DBL = (1 << 22) | (4 << 16) | (3 << 3)


class ExactRGBTransform:
    def __init__(self, source_icc, destination_icc):
        for icc in (source_icc, destination_icc):
            p = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            if p.profile.xcolor_space.strip() != 'RGB':
                raise ValueError('Only RGB ICC profiles are supported')
        candidates=list((Path(PIL.__file__).parent/'.dylibs').glob('*lcms*'))
        candidates+=list((Path(PIL.__file__).parent.parent/'pillow.libs').glob('*lcms*'))
        library=next((str(p) for p in candidates if p.is_file()),None) or ctypes.util.find_library('lcms2')
        if not library:raise RuntimeError('缺少 LittleCMS2，请安装含 LittleCMS 的 Pillow 或系统 lcms2')
        self.lib = lib = c.CDLL(library)
        self.profiles = []
        self.transform = None
        for name, args, result in [
            ('cmsOpenProfileFromMem', [c.c_void_p, c.c_uint32], c.c_void_p),
            ('cmsCreateTransform', [c.c_void_p, c.c_uint32, c.c_void_p, c.c_uint32, c.c_uint32, c.c_uint32], c.c_void_p),
            ('cmsDoTransform', [c.c_void_p, c.c_void_p, c.c_void_p, c.c_uint32], None),
            ('cmsDeleteTransform', [c.c_void_p], None),
            ('cmsCloseProfile', [c.c_void_p], None),
        ]:
            fn = getattr(lib, name)
            fn.argtypes, fn.restype = args, result
        self.buffers = [c.create_string_buffer(v) for v in (source_icc, destination_icc)]
        try:
            for buffer, raw in zip(self.buffers, (source_icc, destination_icc)):
                profile = lib.cmsOpenProfileFromMem(buffer, len(raw))
                if not profile:
                    raise ValueError('Invalid ICC profile')
                self.profiles.append(profile)
            self.transform = lib.cmsCreateTransform(
                self.profiles[0], TYPE_RGB_DBL, self.profiles[1], TYPE_RGB_DBL,
                INTENT_RELATIVE_COLORIMETRIC, CMS_FLAGS_NOOPTIMIZE)
            if not self.transform:
                raise ValueError('Cannot create ICC conversion')
        except BaseException:
            self.close()
            raise

    def convert_float(self, rgb):
        source=np.ascontiguousarray(rgb,dtype=np.float64)
        if source.shape[-1]!=3 or not np.isfinite(source).all():
            raise ValueError('Expected finite normalized RGB')
        result=np.empty_like(source)
        self.lib.cmsDoTransform(self.transform,source.ctypes.data,result.ctypes.data,source.size//3)
        if not np.isfinite(result).all():raise ValueError('Non-finite ICC result')
        return np.clip(result,0,1)

    def convert(self, rgb16):
        values=np.asarray(rgb16)
        if values.dtype!=np.dtype('uint16') or values.shape[-1]!=3:
            raise ValueError('Expected native uint16 RGB')
        return np.rint(self.convert_float(values/65535)*65535).astype('uint16')

    def close(self):
        if self.transform:
            self.lib.cmsDeleteTransform(self.transform)
            self.transform = None
        for profile in self.profiles:
            self.lib.cmsCloseProfile(profile)
        self.profiles.clear()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def to_srgb(probes, icc):
    """Transform individual probes before their mean; no intermediate quantization."""
    from concurrent.futures import ThreadPoolExecutor
    import hashlib
    values=np.asarray(probes,dtype=np.float64)
    if not icc:return values,dict(policy='untagged-assumed-sRGB',converted=False)
    profile=ImageCms.ImageCmsProfile(io.BytesIO(bytes(icc)))
    description=ImageCms.getProfileDescription(profile).strip()
    if profile.profile.xcolor_space.strip()!='RGB':raise ValueError('需要 RGB ICC 配置文件')
    info=dict(source_profile=description,source_icc_sha256=hashlib.sha256(icc).hexdigest())
    if 'srgb' in description.lower().replace(' ',''):
        return values,dict(info,policy='embedded-sRGB',converted=False)
    destination=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    shape=values.shape;flat=values.reshape(-1,3)
    def convert(part):
        with ExactRGBTransform(icc,destination) as transform:return transform.convert_float(part)
    parts=np.array_split(flat,min(8,len(flat)))
    with ThreadPoolExecutor(max_workers=8,thread_name_prefix='r5-icc') as pool:
        result=np.concatenate(list(pool.map(convert,parts))).reshape(shape)
    return result,dict(info,policy='float64-NOOPTIMIZE-relative-noBPC-before-mean',converted=True,
        workers=8,working_bits=64,intermediate_quantization=False,
        destination_icc_sha256=hashlib.sha256(destination).hexdigest())
