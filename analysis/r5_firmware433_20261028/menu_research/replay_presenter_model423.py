"""Candidate 1005 presenter -> actual private registry/wrappers -> row model.

Native map allocation is replaced by an explicit balanced-tree fixture populated
only by the candidate registration calls. Actual map lookups, enumeration,
private availability/normalizer/parent wrappers and 21e2690 model writes run.
No device, display, filesystem service or event loop is executed.
"""
from pathlib import Path
import hashlib, io, json, struct, sys
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
CAND = OUT.parent
sys.path[:0] = [str(ROOT/'vendor/audit-python')]
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as R
SOURCE = CAND/'ap/appFw.so'
raw = SOURCE.read_bytes()
elf = ELFFile(io.BytesIO(raw))
audit = json.loads((CAND/'import/module_audit.json').read_text())
RAM, STOP, SP = 0x20000000, 0x203ff000, 0x203f0000
MMAP, RMAP, NODES = RAM+0x1000, RAM+0x1100, RAM+0x2000
PRES, VIEW, PARAM = RAM+0x10000, RAM+0x14000, RAM+0x20000
UTILITY = RAM+0x1200
GPRS = [getattr(R, 'UC_ARM64_REG_X'+str(i)) for i in range(29)] + [R.UC_ARM64_REG_FP, R.UC_ARM64_REG_LR]
results = []
for bias in (0, 0x40000000):
    u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    for seg in elf.iter_segments():
        if seg['p_type'] != 'PT_LOAD': continue
        lo = (seg['p_vaddr']+bias)&-4096
        hi = (seg['p_vaddr']+bias+seg['p_memsz']+4095)&-4096
        if hi > lo: u.mem_map(lo, hi-lo)
        if seg['p_filesz']: u.mem_write(seg['p_vaddr']+bias, seg.data())
    u.mem_map(RAM, 0x400000)
    def w32(a, value): u.mem_write(a, struct.pack('<I', value & 0xffffffff))
    def w64(a, value): u.mem_write(a, struct.pack('<Q', value))
    def r32(a): return struct.unpack('<I', u.mem_read(a, 4))[0]
    def r64(a): return struct.unpack('<Q', u.mem_read(a, 8))[0]
    for section in elf.iter_sections():
        if section['sh_type'] != 'SHT_RELA': continue
        for rel in section.iter_relocations():
            if rel['r_info_type'] == 1027:
                w64(rel['r_offset']+bias, rel['r_addend']+bias)
    sy = {name:address+bias for name,address in audit['symbols'].items()}
    state = dict(mask=4095, selected=0, maps={MMAP:{}, RMAP:{}}, fallbacks=[], events=[], trace=[])
    def ret(value=0):
        lr = u.reg_read(R.UC_ARM64_REG_LR)
        for i in range(1, 19): u.reg_write(GPRS[i], 0xdead0000+i)
        u.reg_write(R.UC_ARM64_REG_X0, value & ((1<<64)-1))
        u.reg_write(R.UC_ARM64_REG_PC, lr)
    def cstring(address, limit=1024):
        return bytes(u.mem_read(address,limit)).split(b'\0')[0].decode('utf8','replace')
    native_names = ('r5_native_menu_insert', 'r5_native_row_insert',
                    'r5_native_menu_normalize', 'r5_native_row_normalize',
                    'r5_native_row_available', 'r5_native_row_available_direct',
                    'r5_native_row_parent', 'r5_filter_available_mask', 'r5_filter_selected')
    fixtures = {sy[name]:name for name in native_names}
    watched = (0x21e2690,0x21e2640,0x1bd6658,0x1bcf3fc,0x1bc49c8,0x1bd912c,
               0x1bd5810,0x1bd5538,0x1bc4a2c,0x1bd1b88,0x1bd9f98,
               0x1bd62ac,0x1bc50ec,0x1bd5d50,0x1bcf268)
    def hook(cpu, pc, size, arg):
        if pc == STOP: cpu.emu_stop(); return
        av = [cpu.reg_read(r) for r in GPRS[:5]]
        kind = fixtures.get(pc)
        if kind:
            if kind.endswith('_insert'):
                records = state['maps'][av[0]]
                assert (av[2]-av[1])%16 == 0
                for q in range(av[1], av[2], 16):
                    key,pointer = struct.unpack('<QQ',u.mem_read(q,16))
                    records[key] = pointer
                state['events'].append((kind,(av[2]-av[1])//16));ret();return
            if kind == 'r5_filter_available_mask': ret(state['mask']);return
            if kind == 'r5_filter_selected': ret(state['selected']);return
            state['fallbacks'].append((kind,av[1]))
            if kind == 'r5_native_row_parent': ret(0xca4);return
            if 'available' in kind: ret(1);return
            ret(av[1]);return
        at = pc-bias
        if at in watched: state['trace'].append(at)
        if at == 0x16d95f0:
            cpu.mem_write(av[0],bytes([av[1]&255])*av[2]);ret(av[0]);return
        if at == 0x16d9770:
            value = bytes(cpu.mem_read(av[1],1024)).split(b'\0')[0]+b'\0'
            cpu.mem_write(av[0],value);ret(av[0]);return
        if at == 0x35b858c: raise AssertionError('native presenter invariant failed')
    for at in (STOP,*fixtures): u.hook_add(UC_HOOK_CODE,hook,begin=at,end=at)
    for at in (*watched,0x16d95f0,0x16d9770,0x35b858c):
        u.hook_add(UC_HOOK_CODE,hook,begin=at+bias,end=at+bias)
    def call(address,*args):
        for i,register in enumerate(GPRS): u.reg_write(register,0x123450000000+i)
        for i,value in enumerate(args): u.reg_write(GPRS[i],value)
        u.reg_write(R.UC_ARM64_REG_SP,SP);u.reg_write(R.UC_ARM64_REG_LR,STOP)
        before=[u.reg_read(r) for r in GPRS]
        try: u.emu_start(address,STOP,count=1000000)
        except Exception:
            print(json.dumps(dict(error_pc=hex(u.reg_read(R.UC_ARM64_REG_PC)),recent_trace=list(map(hex,state['trace'][-30:])),fallbacks=state['fallbacks'][-10:])))
            raise
        assert u.reg_read(R.UC_ARM64_REG_PC)==STOP and u.reg_read(R.UC_ARM64_REG_SP)==SP
        assert [u.reg_read(r) for r in GPRS[19:30]]==before[19:30]
        return u.reg_read(R.UC_ARM64_REG_X0)
    call(sy['r5_filter_menu_register'],MMAP,RAM,RAM)
    call(sy['r5_filter_rows_register'],RMAP,RAM,RAM)
    assert set(state['maps'][MMAP])=={0x635}
    assert set(state['maps'][RMAP])==set(range(0x1600,0x160d))
    assert state['maps'][MMAP][0x635]==sy['r5_filter_menu_descriptor']
    # One unchanged stock row permits a native-fallback label/icon control.
    state['maps'][RMAP][0x84a] = 0x3f71d00+bias
    cursor=[NODES]
    def build(records,parent):
        if not records:return 0
        middle=len(records)//2;key,pointer=records[middle]
        node=cursor[0];cursor[0]+=0x40
        w32(node,1);w64(node+8,parent)
        w64(node+0x10,build(records[:middle],node))
        w64(node+0x18,build(records[middle+1:],node))
        w32(node+0x20,key);w64(node+0x28,pointer)
        return node
    for map_address,records in state['maps'].items():
        header=map_address+8;root=build(sorted(records.items()),header)
        w64(map_address,0);w64(header+8,root)
        w64(header+0x10,root);w64(header+0x18,root);w64(map_address+0x28,len(records))
    w64(0x59611f8+bias,MMAP);w64(0x5915b80+bias,RMAP)
    w64(UTILITY,0x582ca68+bias)
    w64(PRES+0x30,VIEW);w64(VIEW+0x38,RAM+0x18000)
    w32(VIEW+0x40,0x35);w64(VIEW+0x48,PARAM)
    for mask,selected in ((4095,0),(4095,12),(0x805,1),(0x805,12),(0,0)):
        state['mask']=mask;state['selected']=selected
        state['trace'].clear();state['fallbacks'].clear()
        u.mem_write(PARAM,bytes(0x10000))
        call(0x21e2690+bias,PRES,0x635)
        expected=[0]+[n for n in range(1,13) if mask&(1<<(n-1))]
        count=r32(PARAM+0xdedc)
        primary=[r32(PARAM+0x15c+i*4) for i in range(count)]
        icons=[r32(PARAM+0x288+i*4) for i in range(count)]
        disabled=list(u.mem_read(PARAM+0xdee4,count))
        assert count==len(expected),(count,expected)
        assert primary==[0x02ff4300+n for n in expected]
        assert icons==[0xffffffff]*count
        assert disabled==[0]*count
        assert r32(PARAM+0xdf38)==9+expected.index(selected),(hex(mask),selected,r32(PARAM+0xdf38),expected)
        assert not state['fallbacks'],state['fallbacks']
        for required in (0x21e2690,0x21e2640,0x1bcf3fc,0x1bc49c8,0x1bd912c,0x1bd5810,0x1bd5538,0x1bd9f98,0x1bd62ac):
            assert required in state['trace'],hex(required)
        if bias==0 and mask==4095 and selected==0:
            (OUT/'presenter_full_model423.bin').write_bytes(u.mem_read(PARAM,0xdf8c))
        results.append(dict(bias=hex(bias),mask=hex(mask),selected=selected,
                            count=count,source_rows=[hex(0x1600+n) for n in expected],
                            primary=[hex(x) for x in primary],icons_none=True,
                            native_disabled=disabled,selected_index=r32(PARAM+0xdf38),
                            actual_registry_lookups=True,actual_private_wrappers=True,
                            callee_saved=True))
    state['fallbacks'].clear()
    scratch=RAM+0x80000
    assert call(0x1bd5538+bias,0x84a,scratch)==0x0200a00f
    assert call(0x1bd5810+bias,0x84a)==0xffffffff
    assert ('r5_native_row_parent',0x84a) in state['fallbacks']
    assert ('r5_native_row_normalize',0x84a) in state['fallbacks']
    results.append(dict(bias=hex(bias),stock_control_row='0x84a',
                        actual_stock_row_bytes=True,stock_primary='0x0200a00f',
                        stock_icon='0xffffffff',native_fallback_called=True))
report=dict(passed=True,schema='r5-filter423-presenter-native-model-replay/1',
            camera_io=False,AP_sha256=hashlib.sha256(raw).hexdigest(),cases=len(results),rows=results,
            emitted_full_model='presenter_full_model423.bin',
            limits=['Candidate registration wrappers and private descriptor/13row initialization execute. Native insertion allocation is a fixture retaining inserted pairs in synthetic balanced native-layout trees.',
                    'Real 21e2690/21e2640, enumeration, normalized map lookups, row labels/icons, native selected-row mapping and native disabled checks execute with patched utility vtables at two PIE bases.',
                    'Only mask/selected AP services, native insert allocation, native stock wrapper fallbacks and PLT memset/strcpy are fixtures. Stock fallback control verifies delegation and real unchanged stock row label, not the whole stock alias registry.',
                    'Does not execute actual view widgets, renderer, screen manager event loop, CP or camera. The model binary uses a synthetic param address and must not be treated as a device snapshot.'])
(OUT/'presenter_model423_replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='rows'},ensure_ascii=False))
