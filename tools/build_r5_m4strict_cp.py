#!/usr/bin/env python3
"""R5 4.03 CP feature adaptation of Erlla M4 v7 from immutable official R5.

Only selector/gamma/CC1/matrix/consumer/name/metadata/load-layout changes.
No old alternate-reader patch, settings writes, updater hooks, or devices.

No camera I/O and no DAT generation. Existing builds are never modified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build_r5_m4strict_4.03_20261015'
SOURCE = ROOT / 'unpacked/r5/cp_data/cpapp-b.bin'
SOURCE_SHA = '3269bf62426339791fcfbe8529698cd4accbe6c3d2ea61cd7c368a90ab7ee7c8'
BASE = 0x108000
CODE_START, CODE_END = 0xae7220, 0xae74c0
TEXT_PADDING = (0xae7218, 0xae8000)
RO_PADDING = (0xf76728, 0xf77000)
MD = Cs(CS_ARCH_ARM, CS_MODE_THUMB)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bw(at, target):
    displacement = target-at-4
    require(displacement % 2 == 0 and -(1<<24) <= displacement < (1<<24), 'Thumb B.W outside signed25-bit range')
    value = displacement & ((1<<25)-1)
    s, i1, i2 = (value>>24)&1, (value>>23)&1, (value>>22)&1
    h1 = 0xf000 | (s<<10) | ((value>>12)&0x3ff)
    h2 = 0x9000 | (((1^i1^s)&1)<<13) | (((1^i2^s)&1)<<11) | ((value>>1)&0x7ff)
    raw = struct.pack('<HH',h1,h2)
    i = next(MD.disasm(raw,at))
    require(i.mnemonic == 'b.w' and i.op_str == f'#{target:#x}', 'Branch encoder disagreement')
    return raw


def mov16(reg, value, top=False):
    require(0<=reg<=12 and 0<=value<65536,'MOVW/MOVT operands')
    h1=(0xf2c0 if top else 0xf240)|((value>>12)&15)|(((value>>11)&1)<<10)
    h2=(((value>>8)&7)<<12)|(reg<<8)|(value&255)
    return struct.pack('<HH',h1,h2)


def movabs(reg, value):
    return mov16(reg,value&0xffff)+mov16(reg,value>>16,True)


def movimm(reg, value):
    require(0<=value<256,'Small immediate expected')
    return struct.pack('<H',0x2000|(reg<<8)|value) if reg<8 else struct.pack('<HH',0xf04f,(reg<<8)|value)


class Asm:
    def __init__(self, at):
        self.at=at
        self.data=bytearray()
        self.labels={}
        self.fixups=[]

    @property
    def pc(self): return self.at+len(self.data)

    def emit(self, raw): self.data.extend(raw)
    def label(self,name): self.labels[name]=self.pc
    def cmp(self,reg,value): self.emit(struct.pack('<H',0x2800|(reg<<8)|value))
    def cond(self,condition,name):
        self.fixups.append((len(self.data),condition,name));self.emit(b'\0\0')
    def jump(self, target): self.emit(bw(self.pc,target))
    def finish(self):
        for off,cond,name in self.fixups:
            diff=self.labels[name]-(self.at+off)-4
            require(diff%2==0 and -256<=diff<256,'Local conditional branch overflow')
            struct.pack_into('<H',self.data,off,0xd000|(cond<<8)|((diff//2)&255))
        return bytes(self.data)


# gate, fallback, continuation, index register, result register
CONSUMERS=[
    (0x13ca62,0x13caa2,0x13caa4,1,0),
    (0x13cc24,0x13cc64,0x13cc66,1,0),
    (0x13cdb4,0x13cdf4,0x13cdf6,1,0),
    (0x13cf44,0x13cf84,0x13cf86,1,0),
    (0x13d0d4,0x13d114,0x13d116,1,0),
    (0x13d23c,0x13d282,0x13d284,1,0),
    (0x13d35a,0x13d3ac,0x13d3b0,0,10),
    (0x13d4dc,0x13d53e,0x13d542,0,None),
]


def segment_evidence(stock):
    text=struct.unpack_from('<III',stock,0x20124)
    ro=struct.unpack_from('<III',stock,0x20130)
    data=struct.unpack_from('<III',stock,0x2013c)
    require(text==(0,0xac7218,0x128000),'Unexpected original text segment')
    require(ro==(0xac8000,0x48e728,0xbf0000),'Unexpected original rodata segment')
    require(data==(0xf57000,0x116070,0x107f000),'Unexpected original data segment')
    for start,end in (TEXT_PADDING,RO_PADDING):
        require(stock[start:end]==bytes(end-start),'Segment tail padding occupied')
    require(0x20000+text[1]==TEXT_PADDING[0] and 0x20000+ro[0]==TEXT_PADDING[1],'Text padding source boundary')
    require(0x20000+ro[0]+ro[1]==RO_PADDING[0] and 0x20000+data[0]==RO_PADDING[1],'Rodata padding source boundary')
    require(text[2]+0xac8000==ro[2] and ro[2]+0x48f000==data[2],'Expanded maps overlap next segment')
    require((text[1]+4095)&~4095==0xac8000 and (ro[1]+4095)&~4095==0x48f000,
            'Padding expansion unexpectedly adds mapping pages')
    require(RO_PADDING[1]<=len(stock),'Expanded copy/map outside CP file')
    arm=Cs(CS_ARCH_ARM,CS_MODE_ARM)
    return {'original':{'text':list(text),'rodata':list(ro),'data':list(data)},
            'new_text_size':0xac8000,'new_rodata_size':0x48f000,
            'padding_ranges':[list(TEXT_PADDING),list(RO_PADDING)],
            'all_padding_originally_zero':True,'next_segment_starts_unchanged':True,
            'rounded_4096_byte_page_extents_unchanged':True,
            'file_size_unchanged':True,'rodata_execution_permission_unchanged':True,
            'mapping_code':[{'offset':hex(i.address),'instruction':f'{i.mnemonic} {i.op_str}'} for i in arm.disasm(stock[0x4bc:0x50c],0x4bc)]}


SELECTOR_PATCHES = [{'offset': '0x12b8ca',
  'before_hex': '40f6147051467246c0f26b1090f85701049041f6d830c0f2f200daf0d5dadde907ec002006234ff00c0bff2404229fe0',
  'after_hex': '4ff0360b40f61470c0f26b100699c97851b1dcf8001091f8341000f25b12012908bf00f5ae7201e000f25d121078b5e0',
  'reason': 'FL2 still: native FL setup, profile36, no invalid log'},
 {'offset': '0x12b8fa',
  'before_hex': '40f6147051467246c0f26b1090f85801049041f6d830c0f2f200daf0bddadde907ec002006234ff00c0bff24052287e0',
  'after_hex': '4ff0370be6e700bf00bf00bf00bf00bf00bf00bf00bf00bf00bf00bf00bf00bf00bf00bf00bf00bf00bf00bf00bf00bf',
  'reason': 'FL3 still: shared FL setup, profile37, no invalid log'},
 {'offset': '0x12be0e',
  'before_hex': '40f61470494622467546c0f26b1090f85701049041f62d30c0f2f200daf032d8ddf820c00020ae464ff0ff0b042216e0',
  'after_hex': '3820069040f61470c0f26b109ef8031051b1dcf8001091f8341000f25b12012908bf00f5ae7201e000f25d12107802e0',
  'reason': 'FL2 movie: actual profile38 in stack18/r0; inherited fp preserved'},
 {'offset': '0x12be3e',
  'before_hex': '40f61470494622467546c0f26b1090f85801049041f62d30c0f2f200daf01ad8ddf820c00020ae464ff0ff0b05220a90',
  'after_hex': '39200690e6e70490ff2200200a900698d9e000bf00bf00bf00bf00bf00bf00bf00bf00bf00bf00bf00bf00bf00bf00bf',
  'reason': 'FL3 movie: profile39, shared native FL setup, native r3=4 common tail'}]

def build(include_gamma=True):
    stock=SOURCE.read_bytes()
    require(sha(stock)==SOURCE_SHA,'Unknown R5 4.00 CP source')
    patches=[]
    def add(at,raw,reason):
        require(0<=at and at+len(raw)<=len(stock),'Patch outside immutable file')
        require(all(at+len(raw)<=p['offset'] or p['offset']+len(p['after'])<=at for p in patches),'Overlapping CP patches')
        patches.append({'offset':at,'before':stock[at:at+len(raw)],'after':raw,'reason':reason})
    # Four R5-native selector replacements implement the author's color19/20
    # profiles through the existing FL common tail. No previous binary is input.
    for p in SELECTOR_PATCHES:
        at = int(p['offset'],16)
        require(stock[at:at+len(bytes.fromhex(p['before_hex']))] == bytes.fromhex(p['before_hex']), 'Selector preimage mismatch')
        add(at,bytes.fromhex(p['after_hex']),p['reason'])
    for at,old,new in ((0x61668c,'01d3','5bd0'),(0x61668e,'352e','392e'),(0x616690,'59d1','59d8')):
        require(stock[at:at+2] == bytes.fromhex(old), 'CC1 gate preimage mismatch')
        add(at,bytes.fromhex(new),'M4 main CC1 reader gate: retain original 0..51 and53, add54..57; reject52 and58+')
    report={'segments':segment_evidence(stock),'gates':[],
            'reference':{'repository':'Erlla/sony-a7m4-custom-firmware','commit':'086df3b1e33dfa0206553ac2bb003535c58ddb80',
            'recipe':'a7m4/profiles/fl23/cp-v7-recipe.json','m4_source_sha256':'7b9b137d696e5972d20db7f9119076172ed8e0730805d7f0b4c31b87689e2c2b',
            'm4_target_sha256':'4551c73386c27a0a9b247fd3e05c3bd5e3425bdb9fe9f8374c201c96533b3479'}}
    # Only expand into verified inter-segment padding. No mapping flags change.
    add(0x20128,struct.pack('<I',0xac8000),'Extend text mapping to next original segment boundary')
    add(0x20134,struct.pack('<I',0x48f000),'Extend rodata mapping to next original segment boundary')
    cursor=CODE_START
    strings=CODE_START
    add(strings,b'FL2\0FL3\0','New CP primary/secondary and per-slot names')
    cursor+=8

    def dispatch(gate,fallback,continuation,reg,old_max,new_values,result_reg=None,names=False,reason=''):
        nonlocal cursor
        require(stock[gate:gate+2]==struct.pack('<H',0x2800|(reg<<8)|old_max),'Unexpected range gate')
        old_branch=next(MD.disasm(stock[gate+2:gate+6],gate+2))
        require(old_branch.size==2 and old_branch.mnemonic=='bhi' and old_branch.op_str==f'#{fallback:#x}','Unexpected range fallback')
        start=cursor;a=Asm(start)
        for k,value in enumerate(new_values):
            a.cmp(reg,value);a.cond(0,f'new{k}')
        a.cmp(reg,old_max);a.cond(8,'old_fallback')
        a.jump(gate+4)
        a.label('old_fallback');a.jump(fallback)
        for k in range(2):
            a.label(f'new{k}')
            if names:
                if result_reg==6:a.emit(bytes.fromhex('3046')) # mov r0,r6 in slot-name path
                a.emit(movabs(1,BASE+strings+4*k))
            else:
                a.emit(movimm(result_reg,0x36+k if reason.startswith('consumer') else 22+k))
            a.jump(continuation)
        raw=a.finish();require(cursor+len(raw)<=CODE_END,'CP code padding exhausted')
        add(start,raw,reason+' trampoline (old comparison replayed for every old input)')
        add(gate,bw(gate,start),reason+' redirect range gate')
        report['gates'].append({'gate':gate,'fallback':fallback,'old_continue':gate+4,
                                'new_continue':continuation,'index_register':reg,'old_max':old_max,
                                'new_values':list(new_values),'result_register':result_reg,
                                'names':names,'trampoline':start,'trampoline_size':len(raw),'reason':reason})
        cursor=(cursor+len(raw)+3)&~3

    for n,(gate,fallback,tail,reg,dst) in enumerate(CONSUMERS):
        dispatch(gate,fallback,tail,reg,8,(9,10),6 if dst is None else dst,dst is None,f'consumer{n+1}')
    dispatch(0x13c460,0x13c484,0x13c4ec,1,17,(18,19),None,True,'primary name')
    dispatch(0x13d43a,0x13d462,0x13d4a8,1,26,(18,19),None,True,'secondary name')
    dispatch(0x13c4fc,0x13c510,0x13c512,1,19,(20,21),2,False,'B029 enum')

    # Matrix: retain original rejection of 0x34/0x35 and all values >0x39.
    at=cursor;a=Asm(at)
    a.cmp(3,0x33);a.cond(9,'accept') # bls
    a.cmp(3,0x36);a.cond(3,'reject') # blo
    a.cmp(3,0x39);a.cond(8,'reject') # bhi
    a.label('accept');a.emit(mov16(2,0x3414));a.jump(0x616444)
    a.label('reject');a.jump(0x616450)
    raw=a.finish();require(at+len(raw)<=CODE_END,'Matrix trampoline exceeds padding')
    require(stock[0x61643e:0x616444]==bytes.fromhex('07d843f21442'),'Unexpected matrix gate/preimage')
    add(at,raw,'Matrix accepts only original0..0x33 plus new0x36..0x39')
    add(0x61643e,bw(0x61643e,at)+bytes.fromhex('00bf'),'Matrix gate redirect plus copied MOVW in trampoline')
    cursor=at+len(raw)
    report['matrix_gate']={'trampoline':at,'trampoline_size':len(raw),'redirect':0x61643e,
                            'accept':0x616444,'reject':0x616450,'original_invalid_profiles_preserved':[0x34,0x35]}
    # M4 v7 reads the four new CC1 records directly from CP, without relying
    # on the settings service to provide those coefficient rows. Compact their
    # unused 16-byte paddings: 48-byte active rows have identical arithmetic.
    cursor=(cursor+3)&~3
    tramp=cursor
    coeff=tramp+32
    a=Asm(tramp)
    a.cmp(6,0x35);a.cond(1,'new')
    a.jump(0x6166c0)
    a.label('new')
    a.emit(bytes.fromhex('30463638410008440001')) # r0=(r6-54)*48
    a.emit(movabs(1,BASE+coeff));a.emit(bytes.fromhex('0844'))
    a.jump(0x6166e8)
    raw=a.finish()
    require(len(raw)==32,'Unexpected CC1 trampoline size')
    require(stock[0x6166bc:0x6166c0]==bytes.fromhex('352e04d1'),'CC1 dispatch preimage')
    add(0x6166bc,bw(0x6166bc,tramp),'M4 main CC1 direct embedded coefficient dispatch')
    add(tramp,raw,'CC1 embedded coefficient address; native profile53 special path preserved')
    from sony_bk4 import find_banks
    donor_path=sorted((ROOT/'unpacked/fx2/firmware/0110_backup').rglob('*ALLLANG.bin'))[0]
    props=[]
    for bank in find_banks(donor_path.read_bytes()):
        try: props.append(bank.property(0x02a40001).data)
        except KeyError: pass
    require(len(props)==1,'Expected unique FX2 CC1')
    cc1=props[0]
    require(sha(cc1)=='c87f4dad18225b0b6a5a273bd27211fd93ad0ca0ab8ac2f1b65f680daec4d996','Wrong FX2 CC1')
    coeff_records=[]
    for i,bank in enumerate((22,24,23,25)):
        source=0x1250+bank*64
        row=struct.unpack_from('<24h',cc1,source)
        vals=list(row[:8])+[row[k+8]-row[k] for k in range(8)]+[row[k+16]-row[k] for k in range(8)]
        require(all(-32768<=x<=32767 for x in vals),'CC1 signed16 delta overflow')
        data=struct.pack('<24h',*vals)
        add(coeff+i*48,data,f'M4 embedded coefficients: profile{54+i} bank{bank}; B,A1-B,A2-B')
        coeff_records.append({'profile':54+i,'bank':bank,'offset':hex(coeff+i*48),'source_offset':hex(source),'sha256':sha(data)})
    cursor=coeff+192
    require(cursor<=CODE_END,'CP embedded coefficients exceed verified text padding')
    report['cc1_direct_coefficients']={'trampoline':hex(tramp),'records':coeff_records,'stride':48,'m4_active_bytes_equal':True,'alternate_reader_original':True}
    report['code_padding_used']={'start':CODE_START,'end':cursor,'limit':CODE_END}
    if include_gamma:
        from build_r5_m4strict_gamma import build_patches
        gamma_patches,gamma_report=build_patches(stock)
        for p in gamma_patches:
            require(stock[p['offset']:p['offset']+len(p['before'])]==p['before'],'Gamma preimage mismatch')
            require(len(p['before'])==len(p['after']),'Gamma patch changes size')
            add(p['offset'],p['after'],p['reason'])
        report['gamma']=gamma_report
    result=bytearray(stock)
    for p in patches:result[p['offset']:p['offset']+len(p['after'])]=p['after']
    require(len(result)==len(stock),'CP length changed')
    require(result[0x6169c8:0x616b40]==stock[0x6169c8:0x616b40], 'Alternate reader must stay official')
    require(result[0x4bc:0x50c]==stock[0x4bc:0x50c], 'Mapping attributes must stay official')
    allowed={i for p in patches for i in range(p['offset'],p['offset']+len(p['after']))}
    differences=[i for i,(x,y) in enumerate(zip(stock,result)) if x!=y]
    require(all(i in allowed for i in differences),'Unexpected CP difference')
    report.update(source_sha256=sha(stock),output_sha256=sha(result),size=len(stock),
                  changed_bytes=len(differences),patch_records=len(patches),gamma_included=include_gamma,
                  all_changed_bytes_allowlisted=True,camera_io=False,
                  limitations=['Offline instruction and layout validation only; no camera/ISP boot or pixel proof.'])
    return stock,bytes(result),patches,report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,default=OUT)
    parser.add_argument('--without-gamma',action='store_true',help='Write only partial analysis evidence, never candidate CP')
    args=parser.parse_args()
    before,after,patches,report=build(not args.without_gamma)
    out=args.build.resolve()
    require(out != (ROOT/'build_r5_4.03_customkey_firmware_20261015').resolve(),'Preserve incident artifacts')
    (out/'evidence/cp').mkdir(parents=True,exist_ok=True)
    report['feature_map'] = [
        {'feature':'still/movie color19/20 selectors','m4_offsets':['0x11dab4','0x11dac8','0x11deb6','0x11debe'], 'r5_offsets':['0x12b8ca','0x12b8fa','0x12be0e','0x12be3e'], 'method':'Set profiles54/55/56/57 and reuse native FL setup/common override semantics'},
        {'feature':'main CC1 direct embedded coefficients','m4_offsets':['0x59ce94','0x59cec2','0xa08f10','0xa08f50','0xa9c650'], 'r5_offsets':['0x61668c','0x61668e','0x616690','0x6166bc',report['cc1_direct_coefficients']['trampoline']], 'method':'Identical 48 active bytes per row; compact unused 16-byte padding; retain original profile53 special path'},
        {'feature':'gamma curves/table/route','m4_offsets':['0xa9b240','0xa9b820','0xa9b8d0'],'r5_offsets':['0xae74c0','0xf76728','0xf76968','0xf76efc'], 'method':'Same first572 curve bytes and ID47..50 route/slot mapping; R5 consumed u32 tail2 replaces unused M4 padding'},
        {'feature':'matrix gate','m4_offsets':['0x59cc30'],'r5_offsets':['0x61643e'], 'method':'Add profiles54..57 while retaining R5 original invalid52/53 behavior'},
        {'feature':'eight look consumers','m4_offsets':['0x12ce5e','0x12d020','0x12d1b0','0x12d340','0x12d4d0','0x12d638','0x12d756','0x12d8d8'],'r5_offsets':[hex(x[0]) for x in CONSUMERS], 'method':'Add look10/11 dispatch; preserve all other registers/flags/native destinations'},
        {'feature':'primary/secondary names and metadata','m4_offsets':['0x12c85c','0x12d83a','0x12c8f8'],'r5_offsets':['0x13c460','0x13d43a','0x13c4fc'], 'method':'FL2/FL3 names and B029 metadata22/23'},
        {'feature':'load attributes and placement','m4_offsets':['0x4ec','0x20128','0x20140'],'r5_offsets':['0x20128','0x20134'], 'method':'Only expand segment copy sizes inside existing last pages; original map permission instructions unchanged'},
    ]
    report['excluded_old_changes'] = ['R5 alternate CC1 reader modifications: 0x6169c8..0x616b40 remains stock', 'No previous modified CP binary used as baseline', 'No updater, settings or WBI action in CP builder']
    report['patches']=[dict(offset=hex(p['offset']),before_hex=p['before'].hex(),after_hex=p['after'].hex(),reason=p['reason']) for p in patches]
    name='partial_manifest.json' if args.without_gamma else 'manifest.json'
    (out/'evidence/cp'/name).write_text(json.dumps(report,indent=2)+'\n')
    if not args.without_gamma:
        (out/'patched').mkdir(exist_ok=True)
        (out/'patched/cpapp-b.bin').write_bytes(after)
        subprocess.run([sys.executable,str(ROOT/'tools/verify_r5_m4strict_cp.py'),'--build',str(out)],check=True)
        subprocess.run([sys.executable,str(ROOT/'tools/verify_r5_m4strict_cp_reference.py'),'--build',str(out)],check=True)
    print(json.dumps({k:v for k,v in report.items() if k in ('source_sha256','output_sha256','size','changed_bytes','patch_records','gamma_included','code_padding_used')},indent=2))


if __name__=='__main__':main()
