"""Native Fn registration handler and model/backup-shadow roundtrip.

Only services named in service_fixtures are replaced. The handler, switch,
model getters, per-slot setter, notifier destructor, Fn reader and shadow
save/restore helpers execute the final AP's actual A64 instructions.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from replay_fn433 import FnVM, CAND, ROOT, RAM, X


class SaveVM(FnVM):
    def __init__(self, path, bias):
        self.notifications = []
        self.log_copies = []
        self.registration_pops = 0
        super().__init__(path, bias)
        self.controller = RAM + 0x190000
        manager = RAM + 0x191000
        vtable = RAM + 0x192000
        self.pop_pc = RAM + 0x193000
        self.w64(self.controller + 0x180, manager)
        self.w64(manager, vtable)
        self.w64(vtable + 0x20, self.pop_pc)
        # These are real model-property getters into mapped AP BSS, not
        # hand-picked pointers or replacements for the native slot getter.
        self.state = self.native(0x28CC068)
        self.target = self.native(0x28A86F8)
        self.selected = self.native(0x28A8720)
        self.kind = self.native(0x28BFDCC)
        self.movie_enabled = self.native(0x28A4C8C)
        self.current = {"still": self.native(0x28B1134),
                        "movie": self.native(0x28B115C)}
        self.defaults = {"still": self.native(0x28B1148),
                         "movie": self.native(0x28B1170)}
        self.w32(self.state, 2)
        self.w32(self.selected, 0x635)
        self.w32(self.movie_enabled, 1)

    def hook(self, u, pc, size, arg):
        at = pc - self.bias
        a = [u.reg_read(r) for r in X[:5]]
        if hasattr(self, "pop_pc") and pc == self.pop_pc:
            self.registration_pops += 1
            self.ret()
            return
        if at in (0x2E7D208, 0x2E7CEE4, 0x2542A30, 0x2542A40, 0x269700C):
            self.trace.add(at)
            self.ret()
            return
        if at == 0x252D80C:
            self.trace.add(at)
            self.notifications.append(a[0])
            self.ret()
            return
        if at == 0x3694F64:
            self.trace.add(at)
            self.log_copies.append(dict(pid=hex(a[1]), size=a[4]))
            # Runtime service signature: (env, pid, destination, source, size).
            u.mem_write(a[2], bytes(u.mem_read(a[3], a[4])))
            self.ret()
            return
        super().hook(u, pc, size, arg)

    def register(self, kind, slot, default_target):
        for which, current in self.current.items():
            for index in range(12):
                self.w32(current + index * 4, 0x100 + index)
            self.u.mem_write(self.defaults[which], bytes(12 * 16))
        if default_target:
            self.w64(self.defaults[kind] + slot * 16, RAM + 0x194000)
            self.w32(RAM + 0x194000, 0x12345678)
        self.w32(self.target, (0x38F if kind == "still" else 0x39B) + slot)
        self.w32(self.kind, kind == "movie")
        self.notifications.clear()
        self.log_copies.clear()
        self.trace.clear()
        pops = self.registration_pops
        result = self.native(0x21E45C8, self.controller, 0)
        assert result == 1
        assert self.registration_pops == pops + 1
        for which, current in self.current.items():
            expected = [0x100 + i for i in range(12)]
            if which == kind:
                expected[slot] = 0x635
            actual = [self.d(current + i * 4) for i in range(12)]
            assert actual == expected, (kind, slot, which, actual, expected)
        pid = (0x7AD if kind == "still" else 0x7B9) + slot
        assert self.notifications == [pid, 0x389], self.notifications
        assert 0x21E2B64 in self.trace and 0x21E2B4C in self.trace
        setter = 0x21E40F0 if kind == "still" else 0x21E41DC
        assert setter in self.trace
        if default_target:
            assert self.d(RAM + 0x194000) == 0x635
        # Run the real per-slot current getter, save-to-shadow, restore helper.
        helper = (0x2AC9450 if kind == "still" else 0x2AC8F14) + (11 - slot) * 0x58
        restore = helper + (0x14 if slot == 0 else 0x18)
        save = helper + (0x34 if slot == 0 else 0x38)
        current = self.native(helper)
        assert current == self.current[kind] + slot * 4
        self.native(save)
        shadow = 0x8416000 + self.bias + (0x6B0 if kind == "still" else 0x7A0) + slot * 4
        assert self.d(shadow) == 0x635, (kind, slot, hex(shadow), hex(self.d(shadow)))
        self.w32(current, 0x575)
        self.native(restore)
        assert self.d(current) == 0x635
        # The real Fn first-screen reader performs mode selection and ID->MID.
        reread = self.native(0x216EB9C, self.controller, slot)
        assert reread == 0x635, (kind, slot, hex(reread))
        return dict(kind=kind, slot=slot, target_id=hex(self.d(self.target)),
                    model_pid=hex(pid), function_id=hex(self.d(current)),
                    default_target_present=default_target,
                    notification_pids=[hex(n) for n in self.notifications],
                    native_shadow_save=hex(save),
                    native_shadow_restore=hex(restore),
                    shadow_address=hex(shadow - self.bias),
                    first_screen_reader_mid=hex(reread),
                    other_slots_unchanged=True,
                    service_copies=self.log_copies.copy())


def main():
    ap = CAND / "ap/appFw.so"
    rows = []
    for bias in (0, 0x40000000):
        vm = SaveVM(ap, bias)
        cases = [vm.register(kind, slot, default_target)
                 for kind in ("still", "movie") for slot in range(12)
                 for default_target in (False, True)]
        rows.append(dict(bias=hex(bias), cases=cases))
    report = dict(
        passed=True, AP_sha256=hashlib.sha256(ap.read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        native_save_handler="0x21e45c8", native_first_screen_reader="0x216eb9c",
        native_registration_cases=sum(len(row["cases"]) for row in rows),
        native_shadow_roundtrips=sum(len(row["cases"]) for row in rows),
        rows=rows,
        service_fixtures=[
            "2e7d208/2e7cee4 and 2542a30/2542a40: lock/context services return without host OS work.",
            "3694f64: per-property logging/copy service performs only its declared byte copy.",
            "252d80c: capture property notification PID; its observer/container/backend dispatch is not run.",
            "269700c: external update/refresh service returns; its observers are not run.",
            "Registration manager virtual slot +0x20 is captured as a pop; native 21e2fb0 dispatch executes.",
        ],
        limits=[
            "FunctionID 635 is selected by environment setup; the actual handler selects its target slot through the original switch table.",
            "Native shadow-copy helpers establish model-to-backup-shadow preservation of all 24 Fn slots. Physical BKID commit, eMMC, reboot and cold-start reload are not executed.",
            "The real Fn first-screen reader reobtains MID 635 after native shadow restore; UI activation, rendering and private-page return are covered by the separate activation replay.",
        ])
    out = HERE / "fn433_save_roundtrip.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("rows", "service_fixtures", "limits")}))


if __name__ == "__main__":
    main()
