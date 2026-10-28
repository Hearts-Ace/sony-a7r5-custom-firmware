"""Replay native screen-stack push/pop for Fn C2 -> private D9 -> Fn C2.

This is local synthetic CPU evidence. The manager's lower-level native
open_screen_ii/close_screen_ii execute; factories, display notifications and
orientation are explicit fixtures. The actual main-menu Enter binding is a
separate report. No camera, event loop, or native display is executed.
"""
from pathlib import Path
import hashlib, io, json, struct, sys
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'vendor/audit-python')]
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as R
from replay_activation433 import ActivationVM, EXPECTED

SOURCE = OUT.parent / 'ap/appFw.so'
raw = SOURCE.read_bytes()
assert hashlib.sha256(raw).hexdigest() == json.loads((SOURCE.parent / 'ap_build.json').read_text())['AP_sha256']
assert hashlib.sha256(raw).hexdigest() == EXPECTED
elf = ELFFile(io.BytesIO(raw))
RAM = 0x20000000
STOP = RAM + 0x1ff000
SP = RAM + 0x100000
MANAGER = RAM + 0x10000
CURRENT_ID = RAM + 0x11000
NEW_ID = RAM + 0x11004
CONTROLLER_PTR = RAM + 0x11008
PRESENTERS = RAM + 0x11010
FALLBACK = RAM + 0x11030
DEQUE = RAM + 0x12000
DATA = RAM + 0x13000
NODES = RAM + 0x14000
MAIN_CONTROLLER = RAM + 0x15000
CUSTOM_CONTROLLER = RAM + 0x15100
RESTORED_CONTROLLER = RAM + 0x15200
MAIN_PRESENTER = RAM + 0x15300
CUSTOM_PRESENTER = RAM + 0x15400
RESTORED_PRESENTER = RAM + 0x15500
VT = RAM + 0x16000
DELETE = RAM + 0x17000
CLOSE = RAM + 0x17004
OPEN = RAM + 0x17008
GETID = RAM + 0x1700c
GPRS = [getattr(R, 'UC_ARM64_REG_X' + str(i)) for i in range(29)] + [R.UC_ARM64_REG_FP, R.UC_ARM64_REG_LR]
rows = []
for bias in (0, 0x40000000):
    vm = ActivationVM(SOURCE, bias)
    u = vm.u
    def w32(a, v): u.mem_write(a, struct.pack('<I', v))
    def w64(a, v): u.mem_write(a, struct.pack('<Q', v))
    def r32(a): return struct.unpack('<I', u.mem_read(a, 4))[0]
    def r64(a): return struct.unpack('<Q', u.mem_read(a, 8))[0]
    w64(0x5915668 + bias, 0x506bf20 + bias)
    for obj in [MAIN_CONTROLLER, CUSTOM_CONTROLLER, RESTORED_CONTROLLER,
                MAIN_PRESENTER, CUSTOM_PRESENTER, RESTORED_PRESENTER]: w64(obj, VT)
    for off, addr in [(0, DELETE), (0x18, GETID), (0x20, OPEN), (0x28, CLOSE)]: w64(VT + off, addr)
    events, trace = [], []
    phase = 'open'
    def ret(value=0):
        lr = u.reg_read(R.UC_ARM64_REG_LR)
        for i in range(1, 19): u.reg_write(GPRS[i], 0xdead0000 + i)
        u.reg_write(R.UC_ARM64_REG_X0, value)
        u.reg_write(R.UC_ARM64_REG_PC, lr)
    def code(cpu, pc, size, _):
        if pc == STOP: cpu.emu_stop(); return
        av = [cpu.reg_read(r) for r in GPRS[:5]]
        if pc == DELETE:
            assert av[0] in ([MAIN_CONTROLLER, MAIN_PRESENTER] if phase == 'open' else [CUSTOM_CONTROLLER, CUSTOM_PRESENTER])
            events.append(('delete_fixture', av[0])); ret(); return
        if pc == CLOSE:
            assert av[0] == (MAIN_CONTROLLER if phase == 'open' else CUSTOM_CONTROLLER)
            assert r32(av[1]) == (0xd9 if phase == 'open' else 0xc2)
            events.append(('close_notification_fixture', r32(av[1]))); ret(); return
        if pc == OPEN:
            assert av[0] == (CUSTOM_CONTROLLER if phase == 'open' else RESTORED_CONTROLLER)
            assert r32(av[1]) == (0xc2 if phase == 'open' else 0xd9)
            events.append(('open_notification_fixture', phase)); ret(); return
        if pc == GETID:
            assert av[0] == (MAIN_PRESENTER if phase == 'open' else CUSTOM_PRESENTER)
            sid = 0xc2 if phase == 'open' else 0xd9
            events.append(('presenter_screen_id_fixture', sid)); ret(sid); return
        at = pc - bias
        trace.append(at)
        target = 0xd9 if phase == 'open' else 0xc2
        if at == 0x1e98444:
            assert av[:2] == [MANAGER, 0xd9 if phase == 'open' else 0xc2]
            events.append(('orientation_fixture', av[1])); ret(0); return
        if at == 0x1ec4488:
            assert av[0] == MANAGER
            events.append(('orientation_apply_fixture',)); ret(); return
        if at == 0x1e979e4:
            assert av[:2] == [MANAGER, target]
            events.append(('controller_factory_fixture', target))
            ret(CUSTOM_CONTROLLER if phase == 'open' else RESTORED_CONTROLLER); return
        if at == 0x1e97948:
            assert av[:2] == [MANAGER, target]
            events.append(('presenter_factory_fixture', target))
            ret(CUSTOM_PRESENTER if phase == 'open' else RESTORED_PRESENTER); return
        if at in [0x35b858c, 0x16d9870, 0x1ec5060]:
            raise AssertionError('unexpected assertion, free, or deque buffer expansion')
    for at in [STOP, DELETE, CLOSE, OPEN, GETID]: u.hook_add(UC_HOOK_CODE, code, begin=at, end=at)
    for at in [0x1e98444, 0x1ec4488, 0x1e979e4, 0x1e97948,
               0x35b858c, 0x16d9870, 0x1ec5060, 0x1ec5304, 0x1ec51f4,
               0x1ec557c, 0x1ec5540, 0x1ec56fc, 0x1ec5704, 0x1ec57fc]:
        u.hook_add(UC_HOOK_CODE, code, begin=at + bias, end=at + bias)
    for stack_base in (0x2ec, 0x32d, 0x315):
        events.clear(); trace.clear(); phase = 'open'
        w32(CURRENT_ID, 0xc2); w32(NEW_ID, 0xd9); w32(FALLBACK, 0x4cf)
        w64(CONTROLLER_PTR, MAIN_CONTROLLER)
        for i, obj in enumerate([MAIN_PRESENTER, 0, 0]): w64(PRESENTERS + i * 8, obj)
        u.mem_write(DATA, struct.pack('<6I', stack_base, 0x4cf, 0x4cf, 0, 0, 0))
        w64(NODES, DATA)
        for off, value in [(0x10, DATA), (0x18, DATA), (0x20, DATA + 0x1f4), (0x28, NODES),
                           (0x30, DATA + 12), (0x38, DATA), (0x40, DATA + 0x1f4), (0x48, NODES)]: w64(DEQUE + off, value)
        def run(entry, args):
            for i, r in enumerate(GPRS): u.reg_write(r, 0x123450000000 + i)
            u.reg_write(R.UC_ARM64_REG_SP, SP); u.reg_write(R.UC_ARM64_REG_LR, STOP)
            for i, value in enumerate(args): u.reg_write(GPRS[i], value)
            before = [u.reg_read(r) for r in GPRS]
            try: u.emu_start(entry + bias, STOP, count=50000)
            except Exception:
                print(json.dumps(dict(phase=phase, error_pc=hex(u.reg_read(R.UC_ARM64_REG_PC)), trace=list(map(hex, trace[-25:])), events=events))); raise
            assert u.reg_read(R.UC_ARM64_REG_PC) == STOP
            assert u.reg_read(R.UC_ARM64_REG_SP) == SP
            assert [u.reg_read(r) for r in GPRS[19:30]] == before[19:30]
        # open_screen_ii arg9 supplies the same native screen-group deque.
        # Main screen descriptor+1c=1 permits stacking. Actual Enter queues
        # mode0, which captures the current presenter screen IDs.
        w64(SP, DEQUE); w32(SP + 8, 0); w32(SP + 16, 0)
        run(0x1ec5304, [MANAGER, CURRENT_ID, NEW_ID, CURRENT_ID, 0, CONTROLLER_PTR, PRESENTERS, PRESENTERS])
        assert r64(DEQUE + 0x30) == DATA + 24
        assert bytes(u.mem_read(DATA + 12, 12)) == struct.pack('<3I', 0xc2, 0x4cf, 0x4cf)
        assert bytes(u.mem_read(DATA, 12)) == struct.pack('<3I', stack_base, 0x4cf, 0x4cf)
        assert trace.count(0x1ec51f4) == 1
        assert r64(CONTROLLER_PTR) == CUSTOM_CONTROLLER
        assert [r64(PRESENTERS + i * 8) for i in range(3)] == [CUSTOM_PRESENTER, 0, 0]
        open_events = list(events)
        # Native caller 1ec6604 records the newly active screen after return.
        w32(CURRENT_ID, 0xd9)
        events.clear(); trace.clear(); phase = 'close'
        run(0x1ec557c, [MANAGER, CURRENT_ID, CONTROLLER_PTR, PRESENTERS, DEQUE, FALLBACK, 0, 0])
        assert r64(DEQUE + 0x30) == DATA + 12
        assert bytes(u.mem_read(DATA, 12)) == struct.pack('<3I', stack_base, 0x4cf, 0x4cf)
        assert r64(CONTROLLER_PTR) == RESTORED_CONTROLLER
        assert [r64(PRESENTERS + i * 8) for i in range(3)] == [RESTORED_PRESENTER, 0, 0]
        assert trace.count(0x1ec5540) == 1
        closed_events = list(events)
        # Native close has installed this exact restored presenter pointer.
        # Populate its synthetic view-map storage, then run the real Fn title,
        # tile producer, tile renderer and sprite-resource writer in this VM.
        projection = vm.fn_projection('after_native_C2_pop', presenter=r64(PRESENTERS))
        rows.append(dict(bias=hex(bias), lower_screen=hex(stack_base), main_screen='0xc2', custom_screen='0xd9',
                         push_count=1, push_bytes=12, pop_count=1, pop_bytes=12,
                         restored_screen='0xc2', fn_presenter_reconstructed=True, lower_stack_unchanged=True,
                         open_events=open_events, close_events=closed_events,
                         restored_presenter_native_projection=projection, callee_saved=True))
report = dict(passed=True, AP_sha256=hashlib.sha256(raw).hexdigest(), script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), source=str(SOURCE.relative_to(ROOT)), sha256=hashlib.sha256(raw).hexdigest(),
              cases=len(rows), rows=rows,
              limits=['Native open_screen_ii(1ec5304), push(1ec51f4), close_screen_ii(1ec557c), iterator and pop execute.',
                      'Fn SIDc2 is bound by screen factory slot50707e8->1d2ba30 and ctor1d2b894/scr0135_0001_controller; D9 slot is replaced by compiled private factory.',
                      'Objects, initial deque, factories, destruction, orientation and open/close notifications are synthetic fixtures. Current-ID store represents native caller1ec6604.',
                      'Native C2 presenter reconstruction is a factory fixture; after real native pop installs its pointer, actual Fn title/tile projection and renderer/sprite resource writer execute in the same VM against that pointer. View-map/sprite storage and adjacent value/highlight rendering remain explicit fixtures.',
                      'This does not execute queued open/close event-loop dispatch, actual display or camera. Real Fn Enter and private close request are separately exercised in fn433_activation.json.'])
(OUT / 'fn433_stack_restore.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k:v for k,v in report.items() if k != 'rows'}, ensure_ascii=False))
