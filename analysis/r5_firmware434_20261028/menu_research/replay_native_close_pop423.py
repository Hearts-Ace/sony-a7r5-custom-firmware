"""Execute native close_screen_ii and its deque pop/restore instructions.

Synthetic controllers/presenters replace rendering, construction and deletion.
The firmware performs the deque iterator update and chooses the prior screen ID.
No device, display, native event loop, or new custom service is executed.
"""
from pathlib import Path
import hashlib, io, json, struct, sys
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'vendor/audit-python')]
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as R
SOURCE = ROOT / 'build_r5_m4strict_4.04_20261015/patched/appFw.so'
raw = SOURCE.read_bytes()
elf = ELFFile(io.BytesIO(raw))
RAM = 0x20000000
STOP = RAM + 0x1ff000
SP = RAM + 0x100000
MANAGER = RAM + 0x10000
CURRENT_ID = RAM + 0x11000
CONTROLLER_PTR = RAM + 0x11008
PRESENTERS = RAM + 0x11010
FALLBACK = RAM + 0x11030
DEQUE = RAM + 0x12000
DATA = RAM + 0x13000
NODES = RAM + 0x14000
OLD_CONTROLLER = RAM + 0x15000
NEW_CONTROLLER = RAM + 0x15100
OLD_PRESENTERS = [RAM + 0x15200 + i * 0x100 for i in range(3)]
NEW_PRESENTER = RAM + 0x15500
VT = RAM + 0x16000
DELETE = RAM + 0x17000
CLOSE = RAM + 0x17004
OPEN = RAM + 0x17008
GETID = RAM + 0x1700c
GPRS = [getattr(R, 'UC_ARM64_REG_X' + str(i)) for i in range(29)] + [R.UC_ARM64_REG_FP, R.UC_ARM64_REG_LR]
results = []
for bias in (0, 0x40000000):
    u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    for seg in elf.iter_segments():
        if seg['p_type'] != 'PT_LOAD':
            continue
        lo = (seg['p_vaddr'] + bias) & -4096
        hi = (seg['p_vaddr'] + bias + seg['p_memsz'] + 4095) & -4096
        if hi > lo:
            u.mem_map(lo, hi - lo)
        if seg['p_filesz']:
            u.mem_write(seg['p_vaddr'] + bias, seg.data())
    u.mem_map(RAM, 0x200000)
    def w32(a, v): u.mem_write(a, struct.pack('<I', v))
    def w64(a, v): u.mem_write(a, struct.pack('<Q', v))
    def r32(a): return struct.unpack('<I', u.mem_read(a, 4))[0]
    def r64(a): return struct.unpack('<Q', u.mem_read(a, 8))[0]
    w64(0x5915668 + bias, 0x506bf20 + bias)
    for obj in [OLD_CONTROLLER, NEW_CONTROLLER, *OLD_PRESENTERS, NEW_PRESENTER]:
        w64(obj, VT)
    w64(VT, DELETE)
    w64(VT + 0x18, GETID)
    w64(VT + 0x20, OPEN)
    w64(VT + 0x28, CLOSE)
    events = []
    trace = []
    expected_previous = 0
    def ret(v=0):
        lr = u.reg_read(R.UC_ARM64_REG_LR)
        for i in range(1, 19):
            u.reg_write(GPRS[i], 0xdead0000 + i)
        u.reg_write(R.UC_ARM64_REG_X0, v)
        u.reg_write(R.UC_ARM64_REG_PC, lr)
    def code(cpu, pc, size, arg):
        if pc == STOP:
            cpu.emu_stop()
            return
        av = [cpu.reg_read(r) for r in GPRS[:5]]
        if pc == DELETE:
            events.append(('delete_fixture', av[0])); ret(); return
        if pc == CLOSE:
            assert av[0] == OLD_CONTROLLER
            assert r32(av[1]) == expected_previous
            events.append(('close_to_previous_fixture', r32(av[1]))); ret(); return
        if pc == OPEN:
            assert av[0] == NEW_CONTROLLER and r32(av[1]) == 0x2ee
            events.append(('open_restored_controller_fixture',)); ret(); return
        if pc == GETID:
            assert av[0] in OLD_PRESENTERS
            events.append(('current_presenter_id_fixture', 0x2ee)); ret(0x2ee); return
        at = pc - bias
        trace.append(at)
        if at == 0x1e98444:
            assert av[:2] == [MANAGER, expected_previous]
            events.append(('orientation_fixture', av[1])); ret(0); return
        if at == 0x1ec4488:
            assert av[0] == MANAGER
            events.append(('orientation_apply_fixture',)); ret(); return
        if at == 0x1e979e4:
            assert av[:2] == [MANAGER, expected_previous]
            events.append(('restore_controller_factory_fixture', av[1])); ret(NEW_CONTROLLER); return
        if at == 0x1e97948:
            assert av[:2] == [MANAGER, expected_previous]
            events.append(('restore_presenter_factory_fixture', av[1])); ret(NEW_PRESENTER); return
        if at == 0x35b858c:
            raise AssertionError('native close_screen_ii invariant failed')
        if at == 0x16d9870:
            raise AssertionError('fixture unexpectedly crossed deque buffer boundary')
    for at in [STOP, DELETE, CLOSE, OPEN, GETID]:
        u.hook_add(UC_HOOK_CODE, code, begin=at, end=at)
    for at in [0x1e98444, 0x1ec4488, 0x1e979e4, 0x1e97948, 0x35b858c, 0x16d9870,
               0x1ec557c, 0x1ec5540, 0x1ec56fc, 0x1ec5704, 0x1ec57fc]:
        u.hook_add(UC_HOOK_CODE, code, begin=at + bias, end=at + bias)
    for previous in (0x2ed, 0x2ec, 0x32d):
        expected_previous = previous
        events.clear(); trace.clear()
        w32(CURRENT_ID, 0x2ee); w32(FALLBACK, 0x4cf)
        w64(CONTROLLER_PTR, OLD_CONTROLLER)
        for i, obj in enumerate(OLD_PRESENTERS): w64(PRESENTERS + i * 8, obj)
        # A two-entry deque in one real 500-byte block. Native code pops the last
        # 12-byte screen group, leaving the earlier entry and buffer allocated.
        u.mem_write(DATA, struct.pack('<6I', 0x2ec, 0x4cf, 0x4cf, previous, 0x4cf, 0x4cf))
        w64(NODES, DATA)
        for off, value in [(0x10, DATA), (0x18, DATA), (0x20, DATA + 0x1f4), (0x28, NODES),
                           (0x30, DATA + 24), (0x38, DATA), (0x40, DATA + 0x1f4), (0x48, NODES)]:
            w64(DEQUE + off, value)
        for i, r in enumerate(GPRS): u.reg_write(r, 0x123450000000 + i)
        u.reg_write(R.UC_ARM64_REG_SP, SP)
        u.reg_write(R.UC_ARM64_REG_LR, STOP)
        for i, value in enumerate([MANAGER, CURRENT_ID, CONTROLLER_PTR, PRESENTERS, DEQUE, FALLBACK, 0, 0]):
            u.reg_write(GPRS[i], value)
        before = [u.reg_read(r) for r in GPRS]
        try:
            u.emu_start(0x1ec557c + bias, STOP, count=50000)
        except Exception:
            print(json.dumps(dict(error_pc=hex(u.reg_read(R.UC_ARM64_REG_PC)),
                                  recent_trace=list(map(hex,trace[-30:])), events=events)))
            raise
        assert u.reg_read(R.UC_ARM64_REG_PC) == STOP
        assert u.reg_read(R.UC_ARM64_REG_SP) == SP
        assert [u.reg_read(r) for r in GPRS[19:30]] == before[19:30]
        assert r64(DEQUE + 0x30) == DATA + 12
        assert r64(CONTROLLER_PTR) == NEW_CONTROLLER
        assert [r64(PRESENTERS + i * 8) for i in range(3)] == [NEW_PRESENTER, 0, 0]
        assert [event[0] for event in events] == [
            'close_to_previous_fixture', 'delete_fixture', 'current_presenter_id_fixture'] + ['delete_fixture'] * 3 + [
            'orientation_fixture', 'orientation_apply_fixture',
            'restore_controller_factory_fixture', 'open_restored_controller_fixture', 'restore_presenter_factory_fixture']
        assert all(at in trace for at in [0x1ec557c, 0x1ec5540, 0x1ec56fc, 0x1ec5704, 0x1ec57fc])
        results.append(dict(bias=hex(bias), previous_screen=hex(previous),
                            restored_screen_from_deque=True, native_deque_pop_bytes=12,
                            events=events, callee_saved=True))
report = dict(passed=True, source=str(SOURCE.relative_to(ROOT)),
              sha256=hashlib.sha256(raw).hexdigest(), cases=len(results), rows=results,
              limits=['Original close_screen_ii, iterator copy/decrement, deque pop and previous screen selection execute.',
                      'Previous groups and controller/presenter objects are synthetic. Factories, destruction, open/close notification and orientation use explicit fixtures.',
                      'This proves restore uses the preceding stack group; it does not establish the screen actually preceding custom menu on a physical device. No native OS event loop or rendering.'])
(OUT / 'native_close_pop423_replay.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k != 'rows'}, ensure_ascii=False))
