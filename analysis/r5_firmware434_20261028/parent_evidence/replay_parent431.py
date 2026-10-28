"""Real D9 push/pop and native end-of-event parent refresh, offline fixtures.

Unlike the older 1005 test, D9 and parent 2D7 both have presenter depth zero.
The native stack must destroy/recreate the parent, then native update must read
the committed private descriptor through the native value resolver.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, struct, sys
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OLD = ROOT / "analysis/r5_custom_menu430_startup_20261027"
sys.path[:0] = [str(ROOT / "vendor/audit-python"), str(OLD / "menu_research"), str(OLD)]
import replay_page425 as page
from unicorn import UC_HOOK_CODE
from replay_main_menu425 import R, X, RAM, SP


class ParentVM(page.PageVM):
    def __init__(self, bias):
        self.stage = "prepare"
        self.lifecycle = []
        self.pool_calls = []
        super().__init__(bias)
        self.u.hook_add(UC_HOOK_CODE, self.parent_hook)
        self.current = RAM + 0x6500
        self.new_id = self.current + 4
        self.controller_ptr = self.current + 8
        self.presenters = self.current + 0x80
        self.fallback = self.current + 0x20
        self.deque = RAM + 0x6600
        self.block = RAM + 0x6800
        self.nodes = RAM + 0x6c00
        self.old_controller = RAM + 0x6000
        self.custom_controller = RAM + 0x6100
        self.restored_controller = RAM + 0x6200
        self.control_vt = RAM + 0x6300
        self.stub_delete = RAM + 0x6400
        self.stub_close = RAM + 0x6404
        self.stub_open = RAM + 0x6408
        self.stub_getid = RAM + 0x640c
        self.custom_presenter = RAM + 0x6d00
        for obj in (self.old_controller, self.custom_controller,
                    self.restored_controller, self.custom_presenter):
            self.w64(obj, self.control_vt)
        for off, addr in ((0, self.stub_delete), (0x18, self.stub_getid),
                          (0x20, self.stub_open), (0x28, self.stub_close)):
            self.w64(self.control_vt + off, addr)
        self.fresh = RAM + 0x280000
        self.fresh_map = RAM + 0x2a0000
        self.fresh_list = RAM + 0x2b0000
        self.fresh_view = RAM + 0x2d0000
        self.u.mem_write(self.fresh, bytes(self.u.mem_read(self.parent, 0x3200)))
        self.u.mem_write(self.fresh_map, bytes(self.u.mem_read(self.parentmap, 0x1000)))
        self.u.mem_write(self.fresh_list, bytes(self.u.mem_read(self.parentlist, 0x3c00)))
        self.w64(self.fresh_map + 11 * 16 + 8, self.fresh_list)
        self.w64(self.fresh + 0x30, self.fresh_map)
        self.w64(self.fresh + 0x28, self.fresh_view)
        self.w64(self.fresh_view, self.vvt)

    def parent_hook(self, cpu, pc, size, unused):
        a = [cpu.reg_read(r) for r in X[:8]]
        at = pc - self.bias
        if at == 0x1bd55fc:
            self.trace.add(at)  # PageVM deliberately omits its base fixture.
        if self.stage == "view_pool":
            if at in (0x36936bc, 0x36936fc):
                self.ret(); return
            if at == 0x182ae14:
                self.pool_calls.append(a[0]); self.ret(self.fresh_view); return
        if self.stage in ("open", "pop"):
            if pc == self.stub_delete:
                self.lifecycle.append(("delete", a[0])); self.ret(); return
            if pc == self.stub_close:
                self.lifecycle.append(("close", a[0], self.d(a[1]))); self.ret(); return
            if pc == self.stub_open:
                self.lifecycle.append(("open", a[0], self.d(a[1]))); self.ret(); return
            if pc == self.stub_getid:
                self.ret(0xd9); return
            if at == 0x1ca2028:
                self.lifecycle.append(("native_parent_destructor", a[0]))
            if at == 0x1e98444:
                self.ret(0); return
            if at == 0x1ec4488:
                self.ret(); return
            if at == 0x1e979e4:
                self.lifecycle.append(("controller_factory", a[1]))
                self.ret(self.custom_controller if self.stage == "open" else self.restored_controller); return
            if at == 0x1e97948:
                self.lifecycle.append(("presenter_factory", a[1]))
                self.ret(self.custom_presenter if self.stage == "open" else self.fresh); return
            if at in (0x16d9870, 0x1ec5060):
                raise AssertionError(("unexpected deque block operation", hex(at)))
        if self.stage == "refresh":
            if at in (0x369373c, 0x3693784, 0x3701e54):
                self.ret(); return
            if at in (0x3701cac, 0x1e97d7c, 0x1e97ea8):
                self.ret(0); return
            if at == 0x1e97bc8:
                self.ret(0x2d7); return

    def lifecycle_run(self, lower):
        self.w32(self.current, 0x2d7); self.w32(self.new_id, 0xd9)
        self.w32(self.fallback, 0x4cf)
        self.w64(self.controller_ptr, self.old_controller)
        for i, p in enumerate((self.parent, 0, 0)):
            self.w64(self.presenters + i * 8, p)
        self.u.mem_write(self.block, struct.pack("<6I", lower, 0x4cf, 0x4cf, 0, 0, 0))
        self.w64(self.nodes, self.block)
        for off, value in ((0x10, self.block), (0x18, self.block),
                           (0x20, self.block + 0x1f4), (0x28, self.nodes),
                           (0x30, self.block + 12), (0x38, self.block),
                           (0x40, self.block + 0x1f4), (0x48, self.nodes)):
            self.w64(self.deque + off, value)
        self.w64(SP, self.deque); self.w32(SP + 8, 0); self.w32(SP + 16, 0)
        self.stage = "open"
        self.native(0x1ec5304, self.manager, self.current, self.new_id,
                    self.current, 0, self.controller_ptr, self.presenters, self.presenters)
        assert ("native_parent_destructor", self.parent) in self.lifecycle
        assert self.q(self.presenters) == self.custom_presenter
        assert self.q(self.presenters + 8) == 0
        assert self.q(self.deque + 0x30) == self.block + 24
        assert bytes(self.u.mem_read(self.block + 12, 12)) == struct.pack("<3I", 0x2d7, 0x4cf, 0x4cf)
        # Native view destruction invalidates old params. Poison the fixture's
        # old list so accidental reuse cannot satisfy the new-parent assertion.
        self.w32(self.parentlist + 0x80, 0xdeadbeef)
        self.w32(self.current, 0xd9)
        self.stage = "pop"
        self.native(0x1ec557c, self.manager, self.current, self.controller_ptr,
                    self.presenters, self.deque, self.fallback, 0, 0)
        assert ("presenter_factory", 0x2d7) in self.lifecycle
        assert self.q(self.controller_ptr) == self.restored_controller
        assert self.q(self.presenters) == self.fresh
        assert self.q(self.deque + 0x30) == self.block + 12
        assert bytes(self.u.mem_read(self.block, 12)) == struct.pack("<3I", lower, 0x4cf, 0x4cf)

    def native_parent_refresh(self, selected):
        self.selected = selected
        self.w32(self.fresh_list + 0x80, 0x12345678)
        self.w64(self.manager + 0x338, self.fresh)
        self.stage = "refresh"
        self.native(0x1e97ef8, self.manager)
        expected = 0x02ff4300 + selected
        assert self.d(self.fresh_list + 0x80) == expected
        assert self.d(self.parentlist + 0x80) == 0xdeadbeef
        required = (0x1e97ef8, 0x1e97fc4, 0x1d90de8, 0x1bc4190,
                    0x1bc3f64, 0x1bd55fc, 0x1bc8eb8, 0x1bc50ec)
        assert all(at in self.trace for at in required), [hex(at) for at in required if at not in self.trace]
        # This is also the safe pre-close check, independent of any live view.
        self.stage = "resolver"
        scratch = RAM + 0x2e0000
        value = self.native(0x1bd55fc, 0x635, scratch)
        assert value == expected
        return expected

    def native_view_pools(self):
        self.stage = "view_pool"
        pairs = []
        for sid in (0xd9, 0x2d7, 0x2ed):
            self.native(0x1e97948, self.manager, sid, 0)
            pool = self.pool_calls[-1]
            assert pool == (1 if sid == 0x2ed else 0)
            pairs.append(dict(screen_id=hex(sid), native_view_pool_index=pool))
        return pairs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=HERE.parent / "ap/appFw.so")
    parser.add_argument("--output", type=Path, default=HERE / "parent431_verified.json")
    args = parser.parse_args()
    page.CAND = args.candidate.resolve().parent.parent
    rows = []
    for bias in (0, 0x40000000):
        for lower in (0x2ec, 0x32d, 0x315):
            vm = ParentVM(bias)
            base = vm.im.pointer(0x5915668)
            assert struct.unpack("<I", vm.im.read(base + 0xd9 * 0x60 + 0x18, 4))[0] == 0
            assert struct.unpack("<I", vm.im.read(base + 0x2d7 * 0x60 + 0x18, 4))[0] == 0
            assert struct.unpack("<I", vm.im.read(base + 0x2ed * 0x60 + 0x18, 4))[0] == 1
            vm.lifecycle_run(lower)
            values = [vm.native_parent_refresh(n) for n in range(13)]
            view_pools = vm.native_view_pools()
            rows.append(dict(bias=hex(bias), lower_screen=hex(lower),
                             lifecycle=vm.lifecycle, native_values=values,
                             view_pools=view_pools,
                             old_parent_destroyed=True, fresh_parent_from_pop=True,
                             native_end_of_event_refresh=True, old_list_unchanged=True,
                             safe_preclose_resolver=True))
    digest = hashlib.sha256(args.candidate.read_bytes()).hexdigest()
    # Bind the event-loop call without pretending the OS loop was executed.
    call_bytes = vm.im.read(0x1ec7428, 4)
    instruction = next(vm.im.md.disasm(call_bytes, 0x1ec7428))
    assert instruction.mnemonic == "bl" and instruction.op_str == "#0x1e97ef8"
    report = dict(schema="r5-menu431-native-parent-lifecycle/1", passed=True,
                  source=str(args.candidate.resolve().relative_to(ROOT)),
                  source_sha256=digest, AP_sha256=digest,
                  event_end_update_call=dict(address="0x1ec7428", target="0x1e97ef8",
                                             instruction_hex=call_bytes.hex(), evidence="static"),
                  cases=len(rows), native_values_checked=len(rows) * 13, rows=rows,
                  limits=["Actual A64 D9 open/pop and event-end presenter traversal/value resolution execute.",
                          "Native OS event loop is not run; the 1EC7428 -> 1E97EF8 call is statically bound and its target runs explicitly.",
                          "Controller factories and renderer allocation/destruction use fixtures; fresh parent metadata is source-bound synthetic storage.",
                          "This establishes the lifetime/refresh contract, not actual LCD timing or camera behavior."])
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
