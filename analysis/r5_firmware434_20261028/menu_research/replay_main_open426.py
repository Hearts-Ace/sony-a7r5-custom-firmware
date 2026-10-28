"""Source-bound compiled AP1005 Enter integration; only custom request is stubbed.

Native registry insertion, model getters, screen validation and Sony lock/log
services are explicit host fixtures. New menu initialization, row/owner/menu
wrappers, native tree lookup, native disabled gate, native close queue and
compiled selected callback execute unchanged from the AP image.
"""
from pathlib import Path
import hashlib, io, json, struct, sys
ROOT = Path(__file__).resolve().parents[3]; OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'vendor/audit-python')]
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as R

SOURCE = OUT.parent / 'ap/appFw.so'
AUDIT = OUT.parent / 'import/module_audit.json'
raw = SOURCE.read_bytes(); elf = ELFFile(io.BytesIO(raw)); audit = json.loads(AUDIT.read_text())
source_sha = hashlib.sha256(raw).hexdigest()
assert json.loads((SOURCE.parent / 'ap_build.json').read_text())['AP_sha256'] == source_sha
assert audit['sources'][str((OUT / 'r5_filter_menu423.c').relative_to(ROOT))] == hashlib.sha256((OUT / 'r5_filter_menu423.c').read_bytes()).hexdigest(), 'rebuild AP after menu source change'
rx_segment = next(s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD' and s['p_vaddr'] == audit['rx'])
runtime = (OUT.parent / 'import/runtime_rx.bin').read_bytes()
assert rx_segment.data()[audit['headers_reserved']:len(runtime)] == runtime[audit['headers_reserved']:]
sy = audit['symbols']
RAM = 0x20000000; STOP = RAM + 0x1ff000; SP = RAM + 0x100000
THIS = RAM + 0x10000; ROUTER = RAM + 0x12000
MENU_MAP = RAM + 0x13000; MENU_NODE = RAM + 0x13100
ROW_MAP = RAM + 0x14000; ROW_NODE = RAM + 0x14100
MENU = RAM + 0x15000; ROW = RAM + 0x15004
CATEGORY = RAM + 0x15008; PROP = RAM + 0x15100
OPEN_QUEUE = RAM + 0x16000; QUEUE_DATA = RAM + 0x17000; QUEUE_NODE = RAM + 0x18000
EMPTY_AUX_MAP = RAM + 0x19000
GPRS = [getattr(R, 'UC_ARM64_REG_X' + str(i)) for i in range(29)] + [R.UC_ARM64_REG_FP, R.UC_ARM64_REG_LR]

def local_symbol(object_name, symbol_name):
    obj = OUT.parent / 'import/objects' / object_name
    objelf = ELFFile(io.BytesIO(obj.read_bytes()))
    symbol = next(s for s in objelf.get_section_by_name('.symtab').iter_symbols() if s.name == symbol_name)
    section = next(s for s in audit['sections'] if Path(s['object']).name == object_name and s['index'] == symbol['st_shndx'])
    return int(section['va'], 16) + symbol['st_value']
names_header = local_symbol('r5_filter_names423.o', 'names_header')
rows = []; init_rows = []; open_rows = []; callback_cases = 0
for bias in (0, 0x40000000):
    MENU=0x7eff000+0xa98+0x18000+0xf40+bias
    ROW_PID=0x7eff000+0xa98+0x18000+0xfb8+bias
    u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    for seg in elf.iter_segments():
        if seg['p_type'] != 'PT_LOAD': continue
        lo = (seg['p_vaddr'] + bias) & -4096
        hi = (seg['p_vaddr'] + bias + seg['p_memsz'] + 4095) & -4096
        if hi > lo: u.mem_map(lo, hi - lo)
        if seg['p_filesz']: u.mem_write(seg['p_vaddr'] + bias, seg.data())
    u.mem_map(RAM, 0x200000)
    def w32(a, v): u.mem_write(a, struct.pack('<I', v))
    def w64(a, v): u.mem_write(a, struct.pack('<Q', v))
    def r32(a): return struct.unpack('<I', u.mem_read(a, 4))[0]
    def r64(a): return struct.unpack('<Q', u.mem_read(a, 8))[0]
    # Apply the AP's original .rela.dyn RELATIVE entries including the ten
    # reviewed virtual remaps; external symbol relocation remains a fixture.
    reloc_count = 0
    for rec in elf.get_section_by_name('.rela.dyn').iter_relocations():
        if rec['r_info_type'] == 1027:
            w64(rec['r_offset'] + bias, (rec['r_addend'] + bias) & ((1 << 64) - 1)); reloc_count += 1
    w32(THIS + 0x178, 0x2ed); w64(THIS + 0x180, ROUTER)
    w64(ROUTER, 0x58d2fb8 + bias)
    events = []; trace = []; registered_menu = []; registered_rows = []
    def ret(value=0):
        lr = u.reg_read(R.UC_ARM64_REG_LR)
        for i in range(1, 19): u.reg_write(GPRS[i], 0xdead0000 + i)
        u.reg_write(R.UC_ARM64_REG_X0, value & ((1 << 64) - 1)); u.reg_write(R.UC_ARM64_REG_PC, lr)
    def code(cpu, pc, size, _):
        if pc == STOP: cpu.emu_stop(); return
        av = [cpu.reg_read(r) for r in GPRS[:5]]; at = pc - bias
        trace.append(at)
        if at in (sy['r5_native_menu_insert'], sy['r5_native_row_insert']):
            dest = registered_menu if at == sy['r5_native_menu_insert'] else registered_rows
            for ptr in range(av[1], av[2], 16): dest.append((r64(ptr), r64(ptr + 8)))
            ret(); return
        if at == sy['r5_osal_alloc']:raise AssertionError('private entry must not allocate')
        if at == 0x1d2e2f0:
            events.append(('private_reserved_controller_ctor_gate',0x308));w32(av[0]+0x178,0xd9);w64(av[0]+0x180,av[1]);ret(av[0]);return
        if at == sy['r5_filter_selected']:ret(0);return
        if at in (0x1d2e488,0x1e1e1a4):raise AssertionError('private MID delegated to stock D9')
        if at == sy['r5_filter_request']:
            events.append(('request_fixture', av[0])); ret(1); return
        if at == 0x1d15798:
            assert av[:2] == [ROUTER, THIS + 0x178]
            events.append(('native_close_screen', 0x2ed))
        if at == 0x369360c:
            assert av[0] == 0x2ed; events.append(('validate_screen_fixture', av[0])); ret(); return
        if at in (0x21e0128, 0x21e0140): ret(MENU if at == 0x21e0128 else ROW); return
        
        if at == 0x28a8734: ret(PROP); return
        if at == 0x28a86d0: ret(CATEGORY); return
        if at == 0x28a86e4: ret(PROP); return
        if at == 0x36935c4:
            events.append(('open_screen_validate_fixture', av[0], av[1])); ret(); return
        if at == 0x16da680: events.append(('native_log_fixture',)); ret(); return
        if at == 0x3694f64:
            cpu.mem_write(av[2], bytes(cpu.mem_read(av[3], av[4]))); ret(); return
        if at in (0x2e7d208, 0x2e7cee4, 0x2542a30, 0x2542a40, 0x252d80c): ret(); return
        if at == 0x35b858c: raise AssertionError('native controller invariant failed')
    watched = set([0x21e0128, 0x21e0140, 0x3694f64, 0x2e7d208, 0x2e7cee4, 0x2542a30,
                   0x2542a40, 0x252d80c, 0x35b858c, 0x369360c, 0x1d15798,
                   0x21e1b7c, 0x21e1c90, 0x21e03e0, 0x1d157ec, 0x1bd9348,
                   0x1bd906c, 0x1bd90c4, 0x1bc990c, 0x1bd5d50, 0x1bcf268,
                   0x1bd9f98, 0x1bd9f44, 0x1bd9440, 0x1bd851c, 0x1bd8eb8,
                   sy['r5_native_menu_insert'], sy['r5_native_row_insert'], sy['r5_filter_request'],sy['r5_osal_alloc'],sy['r5_filter_selected'],0x1d2e2f0,0x1d2e488,0x1e1e1a4])
    watched.update(sy[k] for k in ['r5_filter_menu_select', 'r5_filter_row_parent', 'r5_filter_row_normalize',
                                  'r5_filter_menu_normalize', 'r5_filter_available_mask'])
    watched.update([0x28a8720, 0x28a8734, 0x28a86d0, 0x28a86e4, 0x36935c4, 0x16da680,
                    0x21deab8, 0x1bd5720, 0x1bcf064, 0x21dd740, 0x1cdbb08, 0x1cdbb2c,
                    0x1d15b50, 0x1d15cfc, 0x1d15d20, 0x1bcf1b4, 0x1bcf204,
                    0x1bc84e0, 0x1bd9af8, 0x1bd912c])
    u.hook_add(UC_HOOK_CODE, code, begin=STOP, end=STOP)
    for at in watched: u.hook_add(UC_HOOK_CODE, code, begin=at + bias, end=at + bias)
    def run(entry, args):
        for i, reg in enumerate(GPRS): u.reg_write(reg, 0x123450000000 + i)
        u.reg_write(R.UC_ARM64_REG_SP, SP); u.reg_write(R.UC_ARM64_REG_LR, STOP)
        for i, value in enumerate(args): u.reg_write(GPRS[i], value)
        before = [u.reg_read(reg) for reg in GPRS]
        try: u.emu_start(entry + bias, STOP, count=200000)
        except Exception:
            print(json.dumps(dict(error_pc=hex(u.reg_read(R.UC_ARM64_REG_PC)), trace=list(map(hex, trace[-25:])), events=events))); raise
        assert u.reg_read(R.UC_ARM64_REG_PC) == STOP and u.reg_read(R.UC_ARM64_REG_SP) == SP
        assert [u.reg_read(reg) for reg in GPRS[19:30]] == before[19:30]
        return u.reg_read(R.UC_ARM64_REG_X0)
    run(sy['r5_filter_menu_register'], [MENU_MAP, 0, 0])
    run(sy['r5_filter_rows_register'], [ROW_MAP, 0, 0])
    assert registered_menu == [(0x635, sy['r5_filter_menu_descriptor'] + bias)]
    assert registered_rows == [(0x1600 + i, sy['r5_filter_menu_rows'] + bias + i * 128) for i in range(13)]
    desc = registered_menu[0][1]
    assert r32(desc + 0x20) == 0xd9 and r32(desc + 0x54) == 13
    assert r64(desc + 0x88) == sy['r5_filter_menu_select'] + bias
    for _, ptr in registered_rows:
        assert r32(ptr + 0x18) == 0x4cf and bytes(u.mem_read(ptr + 0x72, 2)) == b'\x55\0'
    init_rows.append(dict(bias=hex(bias), actual_initializer=True, private_rows=13, menu_screen='0xd9',
                          row_child_screen='0x4cf', selected_callback=hex(r64(desc + 0x88)), relative_relocations=reloc_count))
    w64(0x59611f8 + bias, MENU_MAP); w64(MENU_MAP + 0x10, MENU_NODE)
    w64(MENU_NODE + 0x10, 0); w64(MENU_NODE + 0x18, 0); w32(MENU_NODE + 0x20, 0x635); w64(MENU_NODE + 0x28, desc)
    w64(0x5915b80 + bias, ROW_MAP); w64(ROW_MAP + 0x10, ROW_NODE)
    w64(ROW_NODE + 0x10, 0); w64(ROW_NODE + 0x18, 0)
    # Open from the actual native1004 row-list controller. Its Enter handler
    # translates the selected category to a menu ID, then resolves descriptor
    # +20 through native virtual/tree lookups and queues one open request.
    w64(0x5947870 + bias, EMPTY_AUX_MAP); w64(EMPTY_AUX_MAP + 0x10, 0)
    w32(CATEGORY, 0x635); w32(MENU, 0x1f2);w32(ROW_PID,0x1607); w64(PROP, 0); w64(PROP + 8, 0)
    w32(THIS + 0x178, 0x2d7)
    w64(QUEUE_NODE, QUEUE_DATA)
    for off, value in [(0x10, QUEUE_DATA), (0x18, QUEUE_DATA), (0x20, QUEUE_DATA + 0x1f4), (0x28, QUEUE_NODE),
                       (0x30, QUEUE_DATA), (0x38, QUEUE_DATA), (0x40, QUEUE_DATA + 0x1f4), (0x48, QUEUE_NODE)]:
        w64(ROUTER + 0x198 + off, value)
    u.mem_write(ROUTER + 0x43c, b'\0')
    events.clear(); trace.clear()
    assert run(0x21deab8, [THIS, 0]) == 1
    assert r32(MENU) == 0x635
    assert r64(ROUTER + 0x198 + 0x30) == QUEUE_DATA + 20
    queued = bytes(u.mem_read(QUEUE_DATA, 20))
    assert struct.unpack('<4I2B2x', queued) == (0x2d7, 0xd9, 0x2d7, 0, 1, 0), struct.unpack('<4I2B2x', queued)
    assert trace.count(0x1d15cfc) == 1
    assert all(at in trace for at in [0x21deab8, 0x1bd5720, 0x1bcf064, 0x21dd740,
                                    0x1cdbb08, 0x1cdbb2c, 0x1d15b50, sy['r5_filter_menu_normalize']])
    assert not any(e[0] in ['request_fixture', 'native_close_screen'] for e in events)
    open_rows.append(dict(bias=hex(bias), native_1004_enter='0x21deab8', menu='0x635',
                          from_screen='0x2d7', target_screen='0xd9', queue_records=1, queue_record_bytes=20,
                          descriptor_and_native_route=True, events=list(events), callee_saved=True))
    assert r32(ROW_PID)==0x1607
    # Actual route table pointer, not a direct fixture substitution.
    slot=0x506bf20+0xd9*0x60+bias
    assert r64(slot)==sy['r5_filter_presenter425']+bias
    assert r64(slot+8)==sy['r5_filter_controller425']+bias
    before=len(events)
    assert run(r64(slot+8)-bias,[0,ROUTER,RAM+0x1a000,0,0,0])!=0
    assert events[before:]==[('private_reserved_controller_ctor_gate',0x308)]
    open_rows[-1].update(native_menu_pid='0x3b2',menu_pid_after_enter=hex(r32(MENU)),row_pid_unchanged=hex(r32(ROW_PID)),native_controller_factory_reached=True,exact_factory_slot=hex(slot-bias))
report=dict(passed=True,AP_sha256=source_sha,cases=len(open_rows),rows=open_rows,limits=['Actual compiled menu/rows registration, native1004 Enter, descriptor lookup, MID property write, open queue, exact native screen factory table lookup and private controller guard/reserved object gate run at two PIE bases.','Native accessors28a8720/MID3b2 and28a87e8/ROW3b7 execute without stubs. Category input, memory copying/logging/locks and controller ctor body and selected service are explicit fixtures.','The controller reaches its own reserved-object ctor gate; native ctor/render/LCD execution is covered separately, not claimed by this route proof.'])
(OUT/'main_open426_replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('passed',len(open_rows))
