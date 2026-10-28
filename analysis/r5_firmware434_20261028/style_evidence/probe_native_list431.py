"""Read-only original R5 type1c list computation: original A64 instructions.

No GUI/backend or camera execution. This directly executes only native row
parameter generation 1892068 and its local mode helper. Native resource/font
rasterization and actual scroll-container implementation are outside scope.
"""
from pathlib import Path
import hashlib, io, json, struct, sys
ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT/'vendor/audit-python'), str(ROOT/'analysis/r5_custom_menu430_startup_20261027/menu_research')]
from read_menu import Image
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as R

im = Image(ROOT/'assets/firmware/a8d5cd444bf0-appFw.so')
rows=[]
for bias in (0, 0x40000000):
    u=Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    elf=ELFFile(io.BytesIO(im.data))
    for s in elf.iter_segments():
        if s['p_type']!='PT_LOAD': continue
        lo=(s['p_vaddr']+bias)&-4096;hi=(s['p_vaddr']+s['p_memsz']+bias+4095)&-4096
        u.mem_map(lo,hi-lo)
        u.mem_write(s['p_vaddr']+bias,s.data())
    for at,(info,addend) in im.relocs.items():
        if info==1027:u.mem_write(at+bias,struct.pack('<Q',addend+bias))
    mem=0x30000000;u.mem_map(mem,0x200000);stop=mem+0x1ff000
    def w32(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
    def d(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    calls=[]
    fixture={0x18434d0,0x1842e50,0x16dbeb0,0x1842a44,0x1842a34,
             0x1842a2c,0x1842ab0,0x18430e8,0x18438dc,0x1843294,
             0x1842d28,0x1842d5c,0x18428e4,0x1844250,0x1842cc4,0x1843f94}
    def hook(cpu,pc,size,arg):
        if pc==stop:cpu.emu_stop()
        if pc==0x35b858c+bias:raise AssertionError('native assertion')
        if pc-bias in fixture:
            calls.append(dict(pc=hex(pc-bias),w1=cpu.reg_read(R.UC_ARM64_REG_X1),
                s0=struct.unpack('<f',struct.pack('<I',cpu.reg_read(R.UC_ARM64_REG_S0)))[0]))
            cpu.reg_write(R.UC_ARM64_REG_X0,0)
            cpu.reg_write(R.UC_ARM64_REG_PC,cpu.reg_read(R.UC_ARM64_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    def call(pc,owner):
        u.reg_write(R.UC_ARM64_REG_X0,owner)
        u.reg_write(R.UC_ARM64_REG_SP,mem+0x1f0000)
        u.reg_write(R.UC_ARM64_REG_LR,stop)
        u.emu_start(pc+bias,stop,count=200000)
    call(0x16f389c,0) # Original GUI table initializer, no external calls.
    for mode in range(4):
      for focus in (0,1,3,6,9,12):
        owner=mem;param=owner+0x1d8
        u.mem_write(owner,bytes(0x100000))
        w32(param+0x20,112);w32(param+0x24,330)
        for i in range(13):
            w32(param+0x30+i*4,-1);w32(param+0x430+i*4,-1)
            w32(param+0x830+i*4,0x02ff4300+i)
        w32(param+0xd30,13);w32(param+0xd34,mode);w32(param+0xd38,focus)
        w32(param+0xd44,4);u.mem_write(param+0xd40,b'\1')
        call(0x1892068,owner)
        padded=2 if mode in (0,2) else 3 if mode==1 else 1
        slots=[]
        for logical in range(-padded,13):
            slot=owner+0x1de8+(logical+padded)*0x9e8
            rid=d(slot);active=bytes(u.mem_read(slot+0x37c,1))[0]
            disabled=bytes(u.mem_read(slot+0x37d,1))[0]
            assert rid==(0xffffffff if logical<0 else 0x02ff4300+logical),(mode,focus,logical,hex(rid))
            assert active==int(logical==focus),(mode,focus,logical,active)
            assert disabled==0
            rect=[d(slot+0x310+i*4)for i in range(4)]
            if logical>=0 and mode==0:assert rect==[20,0,70,60],rect
            slots.append(dict(logical=logical,resource=hex(rid),active=active,rect=rect))
        calls.clear();call(0x1892414,owner)
        stride=next(x['s0']for x in calls if x['pc']=='0x18438dc')
        scroll_focus=[x['w1']for x in calls if x['pc'] in ('0x1844250','0x1842cc4')]
        assert scroll_focus==[focus,focus],scroll_focus
        if mode==0:assert stride==66.0,stride
        rows.append(dict(bias=hex(bias),mode=mode,focus=focus,visible=2*padded+1,
            leading_blank_slots=padded,rows=slots,native_scroll_calls=list(calls),
            scroll_stride=stride,visible_logical_rows=list(range(focus-padded,focus+padded+1))))
pool_capacity_instructions=[(0x182ae94,0x600000),(0x182aed4,0x400000),
    (0x182af10,0x400000),(0x182af54,0x40000),(0x182af98,0x20000),(0x182afd4,0x20000)]
pools=[]
for i,(at,capacity) in enumerate(pool_capacity_instructions):
    instruction=struct.unpack('<I',im.read(at,4))[0]
    assert instruction&0xff80001f==0x52800004
    assert ((instruction>>5)&0xffff)<<(((instruction>>21)&3)*16)==capacity
    pools.append(dict(index=i,capacity=capacity,capacity_instruction=hex(at),
        capacity_instruction_bytes=im.read(at,4).hex(),pool_pointer_slot=hex(0x74c0470+i*8)))
report=dict(passed=True,original_sha256=hashlib.sha256(im.data).hexdigest(),
    cases=rows,executed_entry='0x1892068',executed_mode_helper='0x1892048/0x1891fe0',
    pool_static_evidence=dict(initializer='0x182ae14',pointer_table='0x74c0470',
       view_constructor='0x182ad30',arena_pointer_field='0x3e98',
       arena_capacity_field='0x3ea0',arena_used_field='0x3ea4',
       native_create='0x182b41c',type1c_allocator='0x18204a0',type1c_bytes='0x9ffd8',
       parameter_only_allocator='0x1822adc',parameter_only_bytes='0xd68',pools=pools,
       evidence_type='Static instruction decode; original initializer/create/allocator execution covered separately.'),
    limitations=['Original A64 row-generation and scroll-configuration instructions execute; low-level scroll setters are recorded fixtures. GUI rendering/font, actual scroll-container placement and physical LCD do not.',
      'Row resource IDs are inputs. Custom UTF8 resource bridge is validated separately by the parent task.',
      'No camera or filesystem device I/O.'])
(HERE/'native_list431.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
windows=[(0x16f389c,0x320),(0x1bc36f8,0x280),(0x1891fe0,0x88),(0x1892068,0x328),(0x1892414,0x2e0),(0x18204a0,0xc0),(0x1822adc,0x138),(0x182ad30,0xe4),(0x182ae14,0x234)]
(HERE/'native_list_disassembly.txt').write_text('\n\n'.join(im.dis(a,n)for a,n in windows)+'\n')
print(json.dumps(dict(passed=True,cases=len(rows),sha256=report['original_sha256'])))
