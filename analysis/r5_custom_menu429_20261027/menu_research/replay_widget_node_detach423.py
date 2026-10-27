"""Run libObj's real Node destructor and intrusive parent removal at two PIE bases.

The synthetic parent has only a child-list getter fixture. All unlink and
parent-zeroing instructions execute from original libObj.so. This bounded test
does not execute the graphics or WidgetManager destructors.
"""
from pathlib import Path
import hashlib, io, json, struct, sys
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT/'vendor/audit-python')]
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as R
SOURCE = ROOT/'unpacked/r5/usr_complete/lib/libObj.so'
raw = SOURCE.read_bytes()
elf = ELFFile(io.BytesIO(raw))
RAM = 0x20000000
SP, STOP = RAM+0x100000, RAM+0x1ff000
PARENT, LIST, VT, GET = RAM+0x1000, RAM+0x1100, RAM+0x1200, RAM+0x1300
NODES = [RAM+0x2000+i*0x80 for i in range(7)]
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
    u.mem_map(RAM, 0x200000)
    def w64(a, value): u.mem_write(a, struct.pack('<Q', value))
    def r64(a): return struct.unpack('<Q', u.mem_read(a, 8))[0]
    for rel in elf.get_section_by_name('.rela.dyn').iter_relocations():
        if rel['r_info_type'] == 1027:
            w64(rel['r_offset']+bias, rel['r_addend']+bias)
    w64(PARENT, VT); w64(VT+0x18, GET)
    trace = []; getters = []
    def code(cpu, pc, size, arg):
        if pc == STOP: cpu.emu_stop(); return
        if pc == GET:
            assert cpu.reg_read(R.UC_ARM64_REG_X0) == PARENT
            getters.append(PARENT)
            lr = cpu.reg_read(R.UC_ARM64_REG_LR)
            for i in range(1, 19): cpu.reg_write(GPRS[i], 0xdead0000+i)
            cpu.reg_write(R.UC_ARM64_REG_X0, LIST)
            cpu.reg_write(R.UC_ARM64_REG_PC, lr)
            return
        trace.append(pc-bias)
        if pc == bias+0x56160: raise AssertionError('native Node invariant failed')
    u.hook_add(UC_HOOK_CODE, code, begin=STOP, end=STOP)
    u.hook_add(UC_HOOK_CODE, code, begin=GET, end=GET)
    for at in (0x133bd4, 0x133b44, 0x133858, 0x1339cc, 0x12b91c,
               0x12b23c, 0x133958, 0x12b41c, 0x12b484, 0x56160):
        u.hook_add(UC_HOOK_CODE, code, begin=bias+at, end=bias+at)
    for count in (1, 3, 7):
        for selected in range(count):
            nodes = NODES[:count]
            w64(LIST, nodes[0]+8); w64(LIST+8, nodes[-1]+8)
            for i, node in enumerate(nodes):
                w64(node, VT)
                w64(node+8, nodes[i+1]+8 if i+1<count else 0)
                w64(node+0x10, nodes[i-1]+8 if i else 0)
                w64(node+0x18, PARENT)
            for i, register in enumerate(GPRS): u.reg_write(register, 0x123450000000+i)
            u.reg_write(R.UC_ARM64_REG_SP, SP); u.reg_write(R.UC_ARM64_REG_LR, STOP)
            u.reg_write(R.UC_ARM64_REG_X0, nodes[selected])
            before = [u.reg_read(r) for r in GPRS]
            trace.clear(); getters.clear()
            u.emu_start(bias+0x133bd4, STOP, count=20000)
            assert u.reg_read(R.UC_ARM64_REG_PC) == STOP
            assert u.reg_read(R.UC_ARM64_REG_SP) == SP
            assert [u.reg_read(r) for r in GPRS[19:30]] == before[19:30]
            assert r64(nodes[selected]+0x18) == 0
            assert r64(nodes[selected]+8) == r64(nodes[selected]+0x10) == 0
            remaining = [n for i,n in enumerate(nodes) if i != selected]
            assert r64(LIST) == (remaining[0]+8 if remaining else 0)
            assert r64(LIST+8) == (remaining[-1]+8 if remaining else 0)
            for i, node in enumerate(remaining):
                assert r64(node+8) == (remaining[i+1]+8 if i+1<len(remaining) else 0)
                assert r64(node+0x10) == (remaining[i-1]+8 if i else 0)
                assert r64(node+0x18) == PARENT
            assert all(x in trace for x in (0x133bd4,0x133b44,0x133858,0x1339cc,0x12b91c,0x12b23c,0x133958))
            assert getters == [PARENT]
            results.append(dict(bias=hex(bias), children=count, removed=selected,
                                remaining=len(remaining), native_unlink=True,
                                parent_zero=True, removed_links_zero=True,
                                callee_saved=True))
report = dict(passed=True, schema='r5-filter423-widget-node-detach-replay/1',
              source=str(SOURCE.relative_to(ROOT)), sha256=hashlib.sha256(raw).hexdigest(),
              cases=len(results), rows=results,
              limits=['Real original libObj Node destructor, parent accessor, setParent(0), child-list removal, intrusive neighbor unlink and parent-zeroing execute at two PIE bases.',
                      'Only parent virtual child-list getter is a fixture. Synthetic lists contain 1, 3 or 7 children with a single selected node destroyed.',
                      'Does not execute full view_string, graphics, WidgetManager or owner destruction; their call binding is established by separate static evidence. No camera/display test.'])
(OUT/'widget_node_detach423_replay.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k != 'rows'}, ensure_ascii=False))
