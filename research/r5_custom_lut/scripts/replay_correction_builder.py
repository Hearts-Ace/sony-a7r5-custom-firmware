"""Replay pristine R5/C2 correction builders in synthetic Unicorn memory.

No patching, USB, file import, real MMIO, threads or scheduler. Native builder
instructions run unchanged; diagnostics/memcpy/memset/barriers are modeled.
"""
from pathlib import Path
import sys
import json
import struct
import random
import hashlib

HERE=Path(__file__).resolve().parents[1]
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'vendor/audit-python'))
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from audit_sources import SOURCES,BASE

CONFIG={
    'r5':dict(builder=0x231654,upload=0x414f44,copy=0x757068,memcpy=0x5f51bc,
        memset=0x5f58b0,log=0xb0de92,barriers=[0x5dde14,0x5ddf74],order=0xe8c1d8),
    'c2':dict(builder=0x23dc2c,upload=0x42cd28,copy=0x78aa20,memcpy=0x61e60c,
        memset=0x61ed00,log=0xb4457a,barriers=[0x607264,0x6073c4],order=0xec7c20),
}
CTX,PARAM,ENV=0x30000000,0x30001000,0x30002000
OUT,STATE,WORK,META,BANK,TABLE=0x30003000,0x30004000,0x30005000,0x30007000,0x30009000,0x30014000
DEV,CONTROL=0x30010000,0x30012000
SP,STOP,MMIO=0x3001f000,0x31000000,0xf3830000
CHUNKS=[(0xd000,300),(0xd200,240),(0xd300,240),(0xd400,192),(0xd500,200),(0xd600,160),(0xd700,160),(0xd800,128)]

def h(data):return hashlib.sha256(data).hexdigest()
def w(uc,at,*values):uc.mem_write(at,struct.pack('<'+'I'*len(values),*values))
def model(raw,order,level):
    output=bytearray(1620)
    for i in range(405):
        values=[int.from_bytes(raw[j*405+i:j*405+i+1],'little',signed=True) for j in range(3)]
        if 1<=level<=7:values=[v*level>>3 for v in values]
        packed=((values[0]&127)<<22)|((values[1]&127)<<12)|((values[2]&127)<<2)
        struct.pack_into('<I',output,order[i]*4,packed)
    return bytes(output)

class Replay:
    def __init__(self,name):
        self.c=CONFIG[name]
        path,expected=SOURCES[name+'_cp']
        self.image=(ROOT/path).read_bytes()
        if h(self.image)!=expected:raise ValueError('Source mismatch')
        self.order=struct.unpack_from('<405H',self.image,self.c['order']-BASE)
        self.uc=u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        u.mem_map(BASE,(len(self.image)+4095)&~4095);u.mem_write(BASE,self.image)
        u.mem_map(CTX,0x20000);u.mem_map(STOP,4096);u.mem_map(MMIO,0x10000)
        self.calls={};self.transfers=[]
        def hook(cpu,at,size,_):
            self.calls[hex(at)]=self.calls.get(hex(at),0)+1
            if at==self.c['memcpy']:
                dst,src,n=[cpu.reg_read(reg) for reg in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2]]
                if not 0<=n<=1620:raise ValueError('Unbounded modeled memcpy')
                cpu.mem_write(dst,bytes(cpu.mem_read(src,n)))
                self.transfers.append(dict(dst=hex(dst),src=hex(src),bytes=n))
            elif at==self.c['memset']:
                dst,n=[cpu.reg_read(reg) for reg in [UC_ARM_REG_R0,UC_ARM_REG_R1]]
                if not 0<=n<=1620:raise ValueError('Unbounded modeled memset')
                cpu.mem_write(dst,bytes(n))
            cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        for at in [self.c['memcpy'],self.c['memset'],self.c['log']]+self.c['barriers']:
            u.hook_add(UC_HOOK_CODE,hook,begin=at,end=at)
    def call(self,va,*args):
        u=self.uc
        for reg,v in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):u.reg_write(reg,v)
        u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,STOP|1)
        u.emu_start(va|1,STOP,count=900000)
        if u.reg_read(UC_ARM_REG_PC)!=STOP or u.reg_read(UC_ARM_REG_SP)!=SP:
            raise ValueError('Did not return within bounded instruction limit')
    def run(self,raw,level,bank_index=0,submit=False):
        u=self.uc;self.calls={};self.transfers=[]
        u.mem_write(CTX,bytes(0x20000));u.mem_write(MMIO,bytes(0x10000))
        w(u,CTX,PARAM,ENV);u.mem_write(PARAM+0x2f,bytes([level]))
        w(u,OUT+8,STATE,WORK,META);w(u,WORK+0x6b0,BANK)
        u.mem_write(META+0xb,bytes([bank_index]));w(u,STATE+0x184,TABLE)
        u.mem_write(STATE+0x188,b'\x01\x02');u.mem_write(TABLE,raw)
        u.mem_write(BANK-16,b'\xa5'*16);u.mem_write(BANK+3*1620,b'\x5a'*16)
        self.call(self.c['builder'],CTX,OUT)
        actual=bytes(u.mem_read(BANK+bank_index*1620,1620))
        expected=model(raw,self.order,level)
        if actual!=expected:raise ValueError(f'Builder differs at level {level}, bank {bank_index}')
        if bytes(u.mem_read(TABLE,1215))!=raw:raise ValueError('Input table overwritten')
        if bytes(u.mem_read(BANK-16,16))!=b'\xa5'*16 or bytes(u.mem_read(BANK+3*1620,16))!=b'\x5a'*16:
            raise ValueError('Bank guard overwritten')
        if submit:
            # Supply an explicit valid synthetic device/control/state. This
            # verifies the code consuming an existing bank, NOT scheduler reachability.
            w(u,DEV+0x184,MMIO);u.mem_write(STATE+0x18,b'\x01')
            w(u,STATE+0x14,BANK+bank_index*1620)
            self.call(self.c['upload'],DEV,DEV,CONTROL,STATE)
            seen=b''.join(bytes(u.mem_read(MMIO+at,n)) for at,n in CHUNKS)
            if seen!=expected:raise ValueError('Synthetic hardware bank differs')
        return dict(level=level,bank_index=bank_index,bank_sha256=h(actual),matches_model=True,
            synthetic_upload=submit,external_calls=dict(self.calls),modeled_transfers=list(self.transfers))

def main():
    rng=random.Random(20261019)
    cases=[('zero',bytes(1215)),('minus64',bytes([192])*1215),('plus63',bytes([63])*1215)]
    for pos in [0,80,81,404,405,809,810,1214]:
        table=bytearray(1215);table[pos]=63;cases.append((f'pulse{pos}',bytes(table)))
    cases += [(f'random{i}',bytes(rng.randrange(-64,64)&255 for _ in range(1215))) for i in range(4)]
    results={}
    for name in CONFIG:
        engine=Replay(name);rows=[]
        for index,(label,raw) in enumerate(cases):
            for level in [1,4,7,8]:
                row=engine.run(raw,level,bank_index=(index%3),submit=True)
                row['case']=label;rows.append(row)
        results[name]=dict(source_sha256=h(engine.image),cases=rows)
    hashes=lambda name:[r['bank_sha256'] for r in results[name]['cases']]
    if hashes('r5')!=hashes('c2'):raise ValueError('Cross-model banks differ')
    result=dict(schema='r5-native-correction-replay/1',device_io=False,firmware_patched=False,
        instructions='Pristine source builders and uploader/copy; external services modeled',
        results=results,cross_model_all_equal=True,
        limits=['Controlled replay; no real scheduler, sensor pixels, USB or hardware execution.',
            'Only root+0x36=0, type=1, transform=2, synthetic valid buffers and device.',
            'Does not implement 48000-byte native video MLUT or generic cube loader.',
            '7-bit correction grid reproduction does not establish C2/R5 ISP colorimetric equality.'])
    (HERE/'evidence/correction_replay.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(cases_per_model=len(results['r5']['cases']),cross_model_all_equal=True,
        synthetic_uploads_per_model=len(results['r5']['cases']),device_io=False),indent=2))

if __name__=='__main__':main()
