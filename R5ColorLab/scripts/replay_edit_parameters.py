"""Replay selected unmodified Edit arm64 instructions in isolated Unicorn RAM.

No app launch, OS services, RAW writes, camera access or firmware changes.
Matrix builder: absent optional calibration service (returns NULL), explicit
identity calibration, output-gamut mode 3. Gamma builder: extra contrast NULL.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import struct
import sys
import argparse
sys.dont_write_bytecode = True
from edit_native_model import np, expand_gamma, decode_matrix16, expand_matrix16, cc1_chroma
from audit_edit_renderer import Mach, THIN_PIN, OUT
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import (UC_ARM64_REG_X0, UC_ARM64_REG_X1,
    UC_ARM64_REG_X2, UC_ARM64_REG_X3, UC_ARM64_REG_X4, UC_ARM64_REG_X5,
    UC_ARM64_REG_LR, UC_ARM64_REG_SP, UC_ARM64_REG_PC, UC_ARM64_REG_CPACR_EL1)

RUNTIME, GAMMA, AXIS, VALUES = 0x30000000, 0x30100000, 0x30130000, 0x30131000
RAW, CONTEXT, GUARD = 0x30200000, 0x30210000, 0x30220000
SP, STOP = 0x303f0000, 0x31000000
REGS = [UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3,UC_ARM64_REG_X4,UC_ARM64_REG_X5]
def sha(data): return hashlib.sha256(data).hexdigest()


class Replay:
    def __init__(self):
        self.data = (OUT/'Edit.arm64').read_bytes()
        if sha(self.data) != THIN_PIN: raise ValueError('Wrong Edit source')
        self.image = Mach(self.data)
        self.uc = u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for seg in self.image.segments:
            if not seg['size']: continue
            u.mem_map(seg['va'], (seg['vsize']+4095)&~4095)
            u.mem_write(seg['va'], self.data[seg['offset']:seg['offset']+seg['size']])
        u.mem_map(RUNTIME,0x400000); u.mem_map(STOP,4096)
        u.reg_write(UC_ARM64_REG_CPACR_EL1,3 << 20)
        # Model a fixed synthetic stack canary, never load a host pointer.
        u.mem_write(0x1002c02e8,struct.pack('<Q',GUARD))
        u.mem_write(GUARD,struct.pack('<Q',0x123456789abcdef0))
        self.calibration_calls = 0
        def absent_calibration(cpu, at, size, data):
            self.calibration_calls += 1
            cpu.reg_write(UC_ARM64_REG_X0,0)
            cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_LR))
        u.hook_add(UC_HOOK_CODE,absent_calibration,begin=0x1000e691c,end=0x1000e691c)

    def call(self, va, *args):
        for reg,value in zip(REGS,args): self.uc.reg_write(reg,value)
        self.uc.reg_write(UC_ARM64_REG_SP,SP); self.uc.reg_write(UC_ARM64_REG_LR,STOP)
        self.uc.emu_start(va,STOP,count=4000000)
        if self.uc.reg_read(UC_ARM64_REG_PC) != STOP or self.uc.reg_read(UC_ARM64_REG_SP) != SP:
            raise RuntimeError('Function did not return within the instruction bound')

    def gamma(self, x, y):
        u=self.uc
        u.mem_write(GAMMA-16,b'\xa5'*16);u.mem_write(GAMMA+0x20000,b'\x5a'*16)
        u.mem_write(GAMMA,b'\xcc'*0x20000)
        xbytes=struct.pack('<'+'i'*len(x),*x); ybytes=struct.pack('<'+'i'*len(y),*y)
        u.mem_write(AXIS,xbytes);u.mem_write(VALUES,ybytes)
        self.call(0x1000c82d4,0,GAMMA,AXIS,VALUES,len(x),0)
        result=bytes(u.mem_read(GAMMA,0x20000))
        if bytes(u.mem_read(AXIS,len(xbytes)))!=xbytes or bytes(u.mem_read(VALUES,len(ybytes)))!=ybytes:
            raise AssertionError('Gamma source parameters overwritten')
        if bytes(u.mem_read(GAMMA-16,16))!=b'\xa5'*16 or bytes(u.mem_read(GAMMA+0x20000,16))!=b'\x5a'*16:
            raise AssertionError('Gamma output bounds exceeded')
        expected=expand_gamma(x,y).tobytes()
        if result!=expected:
            a=np.frombuffer(result,dtype='<u2'); b=np.frombuffer(expected,dtype='<u2')
            bad=np.flatnonzero(a!=b)
            raise AssertionError(f'Gamma differences {len(bad)}; first {[(int(i),int(a[i]),int(b[i])) for i in bad[:8]]}')
        return dict(samples=65536,all_bytes_equal=True,sha256=sha(result),guards_intact=True)

    def matrix(self, payload):
        u=self.uc
        u.mem_write(RUNTIME,bytes(0x100000));u.mem_write(RAW,bytes(0x2000))
        u.mem_write(CONTEXT,bytes(0x1000));u.mem_write(CONTEXT+0x44,struct.pack('<I',3))
        u.mem_write(RAW+0xae,payload)
        u.mem_write(RUNTIME+0x91bc0+1024*72,b'\x5a'*16)
        self.call(0x1000d4ec4,RUNTIME,RAW,CONTEXT,0)
        config=bytes(u.mem_read(RUNTIME+0x91998,0x228))
        expected=decode_matrix16(payload)
        if config!=expected:
            bad=[(hex(i),a,b) for i,(a,b) in enumerate(zip(config,expected)) if a!=b]
            raise AssertionError(f'Matrix config differences {bad[:12]}')
        rawtable=bytes(u.mem_read(RUNTIME+0x91bc0,1024*72))
        table=np.frombuffer(rawtable,dtype='<f4').reshape(1024,18)
        model=expand_matrix16(config)
        maximum=float(np.max(np.abs(table-model)))
        if maximum>2e-6: raise AssertionError(f'Matrix interpolation residual {maximum}')
        if bytes(u.mem_read(RAW+0xae,276))!=payload:raise AssertionError('RAW matrix overwritten')
        if bytes(u.mem_read(RUNTIME+0x91bc0+1024*72,16))!=b'\x5a'*16:raise AssertionError('Matrix bounds exceeded')
        angles=struct.unpack_from('<16H',config,6)
        quadr=table[:,9:]
        return dict(config_bytes=552,config_all_bytes_equal=True,config_sha256=sha(config),
            matrices=1024,table_sha256=sha(rawtable),max_abs_model_residual=maximum,
            enabled=struct.unpack_from('<H',config,0x220)[0],
            quadratic_enabled=struct.unpack_from('<H',config,0x222)[0],
            sector_boundaries=list(angles),normalizers=list(struct.unpack_from('<16H',config,0x1e8)),
            quadratic_max_abs=float(np.max(np.abs(quadr))),guards_intact=True)

    def cc1(self, base, a1, a2):
        # Validate two distinct native selections before the chroma kernel.
        # Other modes/weighted selections remain explicit gaps.
        u=self.uc; rows=[]
        for mode,delta in [(0,a1),(7,a2)]:
            u.mem_write(CONTEXT,bytes(0x1000))
            u.mem_write(CONTEXT+0x10,struct.pack('<I',mode))
            for offset,at,data in [(0x20,RAW,base),(0x30,RAW+32,a1),(0x38,RAW+64,a2)]:
                u.mem_write(CONTEXT+offset,struct.pack('<Q',at));u.mem_write(at,struct.pack('<8h',*data))
            self.call(0x1000bf8e8,CONTEXT)
            effective=((np.array(base,dtype=np.int64)+delta+32768)%65536-32768).astype('<i2')
            if bytes(u.mem_read(CONTEXT+0x88,16))!=effective.tobytes():raise AssertionError('CC1 selection differs')
            grid=[(a,b) for a in [-16000,-8192,-1,0,1,8192,16000] for b in [-16000,-8192,-1,0,1,8192,16000]]
            for bypass in [False,True]:
                predicted=cc1_chroma(effective,grid,bypass)
                actual=[]
                for a,b in grid:
                    self.call(0x1000bfe60,CONTEXT,a & 0xffffffff,b & 0xffffffff,int(bypass))
                    actual.append(struct.unpack('<hh',struct.pack('<I',u.reg_read(UC_ARM64_REG_X0) & 0xffffffff)))
                maximum=int(np.max(np.abs(np.array(actual,dtype=np.int64)-predicted)))
                if maximum>1:raise AssertionError(f'CC1 kernel differs by {maximum} codes')
                rows.append(dict(mode=mode,selection='B+A1' if mode==0 else 'B+A2',
                    effective8=effective.tolist(),selection_all_bytes_equal=True,
                    clipping_bypassed=bypass,points=len(grid),max_abs_code_residual=maximum))
        return rows


def read_styles(path):
    reader=Path(__file__).with_name('sony_arw_metadata.py')
    spec=importlib.util.spec_from_file_location('readonly_raw',reader)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    original=path.read_bytes(); parsed=module.parse(original)
    result={}
    tags=[0x7800,0x7805,0x7806,0x7808,0x780c,0x780d,0x780e,0x780f,0x7842,0x7844,0x7845]
    for g in parsed['styles']:
        name=module.look_name(g)
        if name not in ('Standard','FL','FL2','FL3'):continue
        result[name]={e['tag']:e['data'] for e in g if e['tag'] in tags}
    if set(result)!={'Standard','FL','FL2','FL3'}:raise ValueError('Missing reference looks')
    return result,dict(path=str(path),sha256=sha(original),model=parsed['model'],
        reader=str(reader),reader_sha256=sha(reader.read_bytes()))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw',type=Path,default=Path('input.ARW'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Refuse to replace retained evidence')
    styles,source=read_styles(args.raw)
    engine=Replay();results={}
    for name,g in styles.items():
        x=struct.unpack('<128i',g[0x7805]);y=struct.unpack('<128i',g[0x7806])
        results[name]=dict(gamma=engine.gamma(x,y),matrix=engine.matrix(g[0x780f]),
            cc1=engine.cc1(*[struct.unpack('<8h',g[t]) for t in [0x7842,0x7844,0x7845]]),
            raw_parameters={hex(tag):data.hex() for tag,data in g.items()})
    # Distinct supported inputs test interpolation/saturation, rather than only
    # the flat tail of saved looks. Known identity must be indexed exactly.
    synthetic={}
    x=[0,1024,8192,65536,131072,524288,4194176]
    for name,y in [('identity',x),('curved',[0,3072,11000,41000,61000,130000,261888])]:
        synthetic[name]=engine.gamma(x,y)
    identity=expand_gamma(x,x)[32768:].astype(np.int64)
    ideal=np.arange(32768,dtype=np.int64)*8%65536
    residual=(identity-ideal+32768)%65536-32768
    # FMUL/FDIV rounding before truncation can lose one output code between
    # knots. Knot locations must be exact; never substitute an ideal identity
    # for the native interpolation when comparing replay bytes.
    if np.max(np.abs(residual))>1 or any(identity[k//128]!=ideal[k//128] for k in x):
        raise AssertionError('Independent identity scale/index anchor failed')
    synthetic['identity']['max_abs_modulo_ideal_residual']=int(np.max(np.abs(residual)))
    # A second matrix with negative-even/odd/zero coefficients exercises the
    # native unusual signed decoding independently from reference photos.
    payload=bytearray(styles['FL2'][0x780f])
    values=[-128,-124,-120,-8,-4,0,4,8,120,124,128,512]*8
    struct.pack_into('<96h',payload,24,*values)
    synthetic['matrix_signed_edges']=engine.matrix(bytes(payload))
    result=dict(schema='sony-edit-parameter-replay/1',device_io=False,app_launched=False,
        source_edit_sha256=THIN_PIN,source_raw=source,assumption='Edit look rendering is the camera-equivalent fitting target, as instructed by user.',
        results=results,synthetic=synthetic,modeled_optional_calibration_calls=engine.calibration_calls,
        scripts={p.name:sha(p.read_bytes()) for p in [Path(__file__),Path(__file__).with_name('edit_native_model.py')]},
        limits=['Unmodified selected instructions replayed in synthetic memory, not Edit UI output or camera execution.',
            'Matrix optional calibration service returns NULL; identity calibration and no additional gamut matrix.',
            'Gamma additional contrast table is NULL; legacy gamma and parameter selection not covered.',
            'CC1 only two unweighted selection modes and isolated chroma kernel; no full RGB/YCC table.',
            'No demosaic, spatial filtering, full color pipeline or LUT fit accuracy claim.',
            'Matrix float64 algebra compared to native float32/FMA with explicit tolerance.'])
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:dict(gamma=v['gamma']['all_bytes_equal'],matrix_residual=v['matrix']['max_abs_model_residual'],quadratic=v['matrix']['quadratic_enabled']) for k,v in results.items()},indent=2))


if __name__=='__main__': main()
