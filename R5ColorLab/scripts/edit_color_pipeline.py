"""Edit-derived photo color stages using measured runtime tables.

This begins at the matrix task input (after RAW decoding/WB/demosaic), and
ends before final display/JPEG handling. It is deliberately not a RAW decoder.
All stages preserve native integer ranges and float32 operation order.
"""
from pathlib import Path
import hashlib
import json
import struct
from functools import lru_cache
from edit_native_model import np, _integer_array, rgb_to_ycc, ycc_to_rgb

EVIDENCE = Path(__file__).resolve().parents[1]/'evidence/edit_renderer_20261019'
THIN_SHA = 'c250f466835c5380d244de33a6824e9930fe3f250ce9b1d948d5e379cc4c8133'


def fma(a, b, c):
    """One float32 rounding, for the finite float32 domain of these kernels."""
    return (np.asarray(a, dtype=np.float64)*np.asarray(b, dtype=np.float64)
            + np.asarray(c, dtype=np.float64)).astype(np.float32)


@lru_cache(maxsize=32)
def static_table(address, count, dtype):
    path=Path(__file__).resolve().parents[1]/'data/static_tables.json'
    item=json.loads(path.read_text())[f'{address:x}:{count}:{dtype}']
    raw=bytes.fromhex(item['hex'])
    if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('Static table changed')
    result=np.frombuffer(raw,dtype=dtype,count=count).copy();result.setflags(write=False)
    return result


class RuntimeColor:
    def __init__(self, runtime, raw, settings, area_controls=None):
        if len(runtime) != 0xa3bc0 or not 0x1200 <= len(raw) <= 0x2000 or len(settings) < 0x2b2:
            raise ValueError('Incomplete captured context')
        self.runtime, self.raw, self.settings = bytes(runtime), bytes(raw), bytes(settings)
        if area_controls is not None and len(area_controls) != 65:
            raise ValueError('AreaComp requires 16 floats and one selector byte')
        self.area_controls = area_controls
        self.config = self.runtime[0x91998:0x91bc0]
        self.matrix_table = np.frombuffer(self.runtime, dtype='<f4', count=1024*18, offset=0x91bc0).reshape(1024,18).copy()

    @classmethod
    def from_capture(cls, folder, index=0):
        folder = Path(folder)
        report = json.loads((folder/'report.json').read_text())
        buffers = {}; area_controls = None
        for record in report['messages']:
            p = record['message'].get('payload', {})
            if p.get('kind') != 'buffer':
                continue
            label = p['label']
            is_area = (p.get('context') == index and record['data']['bytes'] == 65
                and label.startswith('area-comp-'))
            if not is_area and label not in [f'color-build-{part}-{index}' for part in ['runtime','raw','settings']]:
                continue
            data = (folder/record['data']['file']).read_bytes()
            if hashlib.sha256(data).hexdigest() != record['data']['sha256'] or len(data) != record['data']['bytes']:
                raise ValueError('Captured context hash mismatch')
            if is_area:
                if area_controls is not None and area_controls != data:
                    raise ValueError('AreaComp controls changed within captured context')
                area_controls = data
            else: buffers[label] = data
        return cls(*(buffers[f'color-build-{part}-{index}'] for part in ['runtime','raw','settings']),
            area_controls=area_controls)

    def _h(self, offset): return struct.unpack_from('<h', self.runtime, offset)[0]
    def _f(self, offset): return struct.unpack_from('<f', self.runtime, offset)[0]
    def _rawh(self, offset): return struct.unpack_from('<h', self.raw, offset)[0]

    def coefficients(self):
        mode = struct.unpack_from('<i', self.settings, 0x1e8)[0]
        if mode == 1 and self.raw[0x1c]:
            return np.array(struct.unpack_from('<8h', self.raw, 0xddc))
        base = np.array(struct.unpack_from('<8h', self.raw, 0xdec), dtype=np.int64)
        if mode in [0,2,3,4,5,6]:
            result = base+np.array(struct.unpack_from('<8h', self.raw, 0xe0c))
        elif mode == 7:
            result = base+np.array(struct.unpack_from('<8h', self.raw, 0xe1c))
        elif mode == 1:
            deltas = np.array(struct.unpack_from('<32h', self.raw, 0xdfc)).reshape(4,8)
            weights = np.array(struct.unpack_from('<4h', self.raw, 0xe44))
            result = base+(np.einsum('ij,i->j', deltas, weights, optimize=False) >> 10)
        else:
            raise ValueError('CC1 selector mode is not implemented; no implicit A1 fallback')
        return (result+32768) % 65536-32768

    def sscs(self,pixels):
        """Integer SSCS highlight handling before the 16-sector color matrix."""
        a = _integer_array(pixels,3,0,65535,'SSCS').copy()
        if len(self.raw) < 0x120b:
            raise ValueError('SSCS requires the extended RAW context capture')
        maximum,tr,tg,tb = struct.unpack_from('<4h',self.raw,0xf82)
        channels = struct.unpack_from('<4i',self.raw,0x84)
        weights=np.zeros(3,dtype=np.int64)
        for channel,value in zip(channels,self.raw[0x1207:0x120b]):
            weights[0 if channel==0 else 1 if channel==1 else 2]+=value
        active=(a[:,0]>tr)&(a[:,1]>tg)&(a[:,2]>tb)
        r,g,b = a[active].T
        def divide(x,d):
            return np.zeros_like(x) if d==0 else np.sign(x*d)*(np.abs(x)//abs(d))
        gf=np.minimum(divide((g-tg)*128,maximum-tg),128)
        use_blue=b<r
        numerator=np.where(use_blue,b-tb,r-tr)*128
        denominator=np.where(use_blue,maximum-tb,maximum-tr)
        sf=np.zeros_like(numerator)
        nonzero=denominator!=0
        sf[nonzero]=np.sign(numerator[nonzero]*denominator[nonzero])*(
            np.abs(numerator[nonzero])//np.abs(denominator[nonzero]))
        sf=np.where(np.where(use_blue,b,r)>maximum,128,sf)
        amount=128-((sf*gf)>>7)
        dr,db=amount*(r-g),amount*(b-g)
        def signed32(v): return ((v+2147483648)&0xffffffff)-2147483648
        green=signed32((weights[0]*r+weights[1]*g+weights[2]*b)*128
            -dr*weights[0]-db*weights[2])>>14
        a[active,0]=(signed32(green*128+dr)>>7)&65535
        a[active,1]=green&65535
        a[active,2]=(signed32(green*128+db)>>7)&65535
        return a.astype('<u2')

    @staticmethod
    def smooth_horizontal(pixels):
        p = np.asarray(pixels, dtype=np.float32)
        if p.ndim != 3 or p.shape[2] != 3 or p.shape[1] < 5 or not np.all(np.isfinite(p)):
            raise ValueError('Expected HxWx3 finite pixels, width >= 5')
        # Native edge replication. Operation order is checked with native replay.
        padded = np.pad(p, ((0,0),(2,2),(0,0)), mode='edge')
        left, mid, right = padded[:,:-4], padded[:,2:-2], padded[:,4:]
        adjacent = (padded[:,1:-3]+padded[:,3:-1]).astype(np.float32)
        result = fma(mid, np.float32(14), left)
        result = (result+right).astype(np.float32)
        return fma(adjacent, np.float32(8), result)*np.float32(1/32)

    def sectors(self, pixels):
        p = np.asarray(pixels, dtype=np.float32)
        smooth = self.smooth_horizontal(p)
        luma_source = smooth if struct.unpack_from('<H',self.config,0)[0] == 1 else p
        chroma_source = smooth if struct.unpack_from('<H',self.config,2)[0] == 1 else p
        luma = luma_source[...,0]*np.float32(109)
        luma = fma(luma_source[...,1], np.float32(366), luma)
        luma = fma(luma_source[...,2], np.float32(37), luma)*np.float32(1/512)
        dr = chroma_source[...,0]-luma
        db = chroma_source[...,2]-luma
        if struct.unpack_from('<H',self.config,4)[0]:
            dr *= np.float32(.875); db *= np.float32(.5)
        ar, ab = np.abs(dr), np.abs(db)
        blue_major = ar <= ab
        base_blue = np.where(dr < 0, np.where(db < 0,512,-1024), np.where(db < 0,-512,0))
        base_red = np.where(dr < 0, np.where(db < 0,-768,768), np.where(db < 0,256,-256))
        base = np.where(blue_major,base_blue,base_red).astype(np.float32)
        minor, major = np.minimum(ar,ab), np.maximum(ar,ab)
        ratio = (minor*np.float32(512))/np.where(major == 0,np.float32(1),major)
        table_index = np.minimum(np.trunc(ratio+np.float32(.5)).astype(np.int64),511)
        angle = static_table(0x100237e00,512,'<f4')[table_index]
        return np.minimum(np.trunc(np.abs(angle+base)).astype(np.int64),1023)

    def matrix16(self, image, return_float=False):
        p = np.asarray(image)
        if p.ndim != 3 or p.shape[-1] != 3 or np.any(p < 0) or np.any(p > 65535):
            raise ValueError('Expected matrix task input HxWx3 in 0..65535')
        if not struct.unpack_from('<H',self.config,0x220)[0]:
            return p.copy()
        p = p.astype(np.float32)
        table = self.matrix_table[self.sectors(p)]
        squared = p*p
        columns = []
        for channel in range(3):
            q = table[...,3*channel:3*channel+3]
            linear = fma(q[...,1],p[...,1],q[...,0]*p[...,0])
            linear = fma(q[...,2],p[...,2],linear)
            if struct.unpack_from('<H',self.config,0x222)[0]:
                q = table[...,9+3*channel:12+3*channel]
                nonlinear = fma(q[...,1],squared[...,1],q[...,0]*squared[...,0])
                nonlinear = fma(q[...,2],squared[...,2],nonlinear)*np.float32(1/16384)
                threshold = np.float32(struct.unpack_from('<f',self.config,0x214+channel*4)[0])
                # Native branch excludes every negative quadratic value.
                summed = (nonlinear+linear).astype(np.float32)
                high = (nonlinear >= 0) & (nonlinear >= threshold)
                low = (nonlinear >= 0) & ~high & (nonlinear <= -threshold)
                linear = np.where(high,summed-threshold,np.where(low,summed+threshold,linear))
            columns.append(np.clip(linear,0,16383))
        result = np.stack(columns,axis=-1).astype(np.float32)
        return result if return_float else np.trunc(result).astype('<u2')

    def main_gamma(self, pixels):
        a = _integer_array(pixels,3,0,32767,'MainGamma input')
        table = np.frombuffer(self.runtime,dtype='<u2',count=65536,offset=0x18f6)
        return table[a+32768]

    def rgb_ycc(self, pixels):
        return rgb_to_ycc(pixels,self.coefficients(),struct.unpack_from('<3h',self.runtime,0x218f6),
                          bool(struct.unpack_from('<i',self.settings,0x248)[0]))

    def chroma_controls(self):
        look = struct.unpack_from('<I',self.raw,0x2c)[0]-0x100
        slope0, slope1, slope2 = [self._rawh(0xf00+i*2) for i in range(3)]
        threshold0, threshold1, threshold2 = [self._rawh(0xf06+i*2) for i in range(3)]
        if 0 <= look < 6 and (0x3d >> look) & 1:
            slope0 = 512
        if 0 <= look < 22 and (0x2e67ff >> look) & 1:
            slope1 = static_table(0x100247620,22,'<f8')[look]
            slope2 = static_table(0x1002476d0,22,'<f8')[look]
            threshold1 = 15360
            threshold2 = static_table(0x100247780,22,'<f8')[look]
        exposure = struct.unpack_from('<i',self.runtime,0xc)[0]/300
        slope, threshold = self._rawh(0xf00), self._rawh(0xf06)
        if -2 <= exposure < -1:
            slope = int(slope2+(slope1-slope2)*(exposure+2))
            threshold = int(threshold2+(threshold1-threshold2)*(exposure+2))
        elif -1 <= exposure < 0:
            slope = int(slope1+(slope0-slope1)*(exposure+1))
            threshold = int(threshold1+(self._rawh(0xf06)-threshold1)*(exposure+1))
        gain = self._h(0x18ee)/64
        if gain <= 0 or threshold < 0:
            raise ValueError('Unsupported chroma controls')
        inv_secondary = struct.unpack_from('<h',self.runtime,0x89962+2*min(threshold,16383))[0]
        inv_main = struct.unpack_from('<h',self.runtime,0x69962+2*(inv_secondary+32768))[0]
        code = min(int(gain*inv_main),32767)
        gamma = struct.unpack_from('<h',self.runtime,0x118f6+2*code)[0]
        cutoff = struct.unpack_from('<h',self.runtime,0x218fc+2*(gamma+32768))[0]
        low_cutoff = int(cutoff*self._rawh(0xf0e)/threshold) if threshold else 0
        adjustment = -exposure if -1 <= exposure <= 0 else exposure+2 if -2 <= exposure <= -1 else 0
        return dict(high_cutoff=cutoff+int(adjustment*-1200),low_cutoff=low_cutoff,
                    high_slope=int(slope/gain)+int(adjustment*150),
                    low_slope=int(self._rawh(0xf0c)/gain))

    def chroma_suppress(self, pixels):
        a = _integer_array(pixels,3,0,65535,'YCC').copy()
        controls = self.chroma_controls()
        y = ((a[:,0]+32768)%65536)-32768
        low = y < controls['low_cutoff']
        high = (~low) & (y >= controls['high_cutoff']) & (y != controls['high_cutoff'])
        amount = np.where(low,(controls['low_cutoff']-y)*controls['low_slope'],
                          np.where(high,(y-controls['high_cutoff'])*controls['high_slope'],0))
        factor = np.clip(255-(amount >> 12),0,255)
        chroma = (a[:,1:]-32768)*factor[:,None]
        chroma = np.sign(chroma)*(np.abs(chroma)//256)
        return np.column_stack([np.maximum(y,0),(chroma+32768)&65535]).astype('<u2')

    def area_comp(self,pixels):
        if self.area_controls is None:
            raise ValueError('AreaComp controls were not captured; cannot assume identity')
        a = _integer_array(pixels,3,0,65535,'AreaComp').copy()
        c = np.frombuffer(self.area_controls,dtype='<f4',count=16)
        if not np.all(np.isfinite(c)) or self.area_controls[64] not in [0,1]:
            raise ValueError('Unsupported AreaComp controls')
        cr = (a[:,1]-32768).astype(np.float32)
        cb = (a[:,2]-32768).astype(np.float32)
        x,y = c[0]+cr,c[1]+cb
        u = np.minimum(np.maximum(fma(y,c[6],x*c[4]),0),np.maximum(fma(c[7],y,c[5]*x),0))
        x,y = c[2]+cr,c[3]+cb
        v = np.minimum(np.maximum(fma(y,c[10],x*c[8]),0),np.maximum(fma(c[11],y,c[9]*x),0))
        if self.area_controls[64]:
            u = np.minimum(u,v);v=np.zeros_like(u)
        # Native promotes each float32 product to double before adding to
        # chroma+32768, then truncates and stores the low 16 bits.
        for channel,source,k in [(1,cr,12),(2,cb,13)]:
            value = source.astype(np.float64)+32768+(u*c[k]).astype(np.float64)
            value += (v*c[k+2]).astype(np.float64)
            a[:,channel] = np.trunc(value).astype(np.int64)&65535
        return a.astype('<u2')

    def y_gamma(self, pixels):
        a = _integer_array(pixels,3,0,65535,'YCC').copy()
        if np.any(a[:,0] > 32767):
            raise ValueError('YGamma requires nonnegative signed16 luma after suppression')
        table = np.frombuffer(self.runtime,dtype='<u2',count=32768,offset=0x318fc)
        y = table[a[:,0]].astype(np.float32)
        level = struct.unpack_from('<h',self.settings,0x2ac)[0]
        level_quarter = int(level/4)
        black = np.float32(-level_quarter)*np.float32(63.998047)
        white = struct.unpack_from('<h',self.settings,0x2b0)[0]
        divisor = 512-white+level_quarter
        if divisor == 0: raise ValueError('Invalid levels denominator')
        normalized = np.maximum((y-black)*np.float32(512),np.float32(0))
        pivot, gain = np.float32(self._h(0x91962)), np.float32(self._f(0x91964))
        y = fma(normalized,np.float32(1)/np.float32(divisor),-pivot)
        y = fma(y,gain,pivot)
        a[:,0] = np.trunc(np.clip(y,0,16383)).astype(np.int64)
        return a.astype('<u2')

    def color_only(self, image):
        """Matrix→gamma→CC1→measured AreaComp→suppression→YGamma→RGB.

        Intended as an explicit color-only fitting subchain, not as an exported
        JPEG, and not an implicit replacement for intervening sharpness/NR.
        AreaComp is included when its controls are captured; legacy contexts
        without those controls explicitly remain a shorter color subchain.
        """
        shape = np.asarray(image).shape
        rgb = self.matrix16(image).reshape(-1,3)
        ycc = self.rgb_ycc(self.main_gamma(rgb))
        if self.area_controls is not None: ycc=self.area_comp(ycc)
        ycc = self.chroma_suppress(ycc)
        return ycc_to_rgb(self.y_gamma(ycc)).reshape(shape)
