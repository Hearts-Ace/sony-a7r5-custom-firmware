"""Source-bound native Fn candidate, descriptor, persistence and entry probes.

Runs the final AP's actual A64 instructions. Services that cannot run on the
host are named explicitly in the output; no target process or camera is run.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
CAND = HERE.parent
ROOT = CAND.parents[1]
sys.path[:0] = [str(ROOT / "vendor/audit-python"), str(CAND), str(CAND / "menu_research")]
from replay_main_menu425 import VM, RAM, X
from unicorn import UC_HOOK_CODE
from patch_fn433 import COUNT_VA, CREATIVE_VA, INSERT_VA


class FnVM(VM):
    def __init__(self, path, bias):
        self.shot_mode = 1
        super().__init__(path, bias)
        self.util = self.facade_use(0x582CA68)
        self.output = RAM + 0x180000
        self.u.hook_add(UC_HOOK_CODE, self.fn_hook)

    def hook(self, u, pc, size, arg):
        at = pc - self.bias
        if hasattr(self, "util") and pc == self.q(self.q(self.util) + 0x478):
            # Stock menu 1b4 resolves a model-dependent concrete menu here.
            self.ret(u.reg_read(X[1]))
            return
        if at == 0x1BC84A0 and u.reg_read(X[1]) != 0x635:
            # Other menus' product-dependent availability is an environment
            # fixture. Private 635 executes real descriptor +0x70 callback.
            self.trace.add(at)
            self.ret(1)
            return
        super().hook(u, pc, size, arg)

    def fn_hook(self, u, pc, size, arg):
        at = pc - self.bias
        if at == 0x17FFD0C:
            self.ret(self.shot_mode)
        elif at in (0x1BDD14C, 0x1BD999C):
            # Playback tab-order hash construction/destruction is not consumed
            # by the still/movie path being executed.
            self.ret(0)

    def candidates(self, kind, patched=True):
        self.w32(COUNT_VA + self.bias, 7 if patched else 6)
        self.native(0x1BC8C58, self.util, kind, self.output)
        groups = []
        for tab in range(self.d(self.output + 4)):
            tp = self.output + tab * 0xFC4
            for group in range(self.d(tp + 8)):
                gp = tp + group * 0xFC
                groups.append(dict(tab=tab, group=group, title=hex(self.d(gp + 12)),
                                   group_id=self.d(gp + 16),
                                   items=[self.d(gp + 24 + i * 8) for i in range(self.d(gp + 20))],
                                   entries=[dict(mid=self.d(gp + 24 + i * 8),
                                                 auxiliary=self.d(gp + 28 + i * 8))
                                            for i in range(self.d(gp + 20))]))
        return groups


def main():
    ap = CAND / "ap/appFw.so"
    raw = ap.read_bytes()
    rows = []
    for bias in (0, 0x40000000):
        vm = FnVM(ap, bias)
        validity = []
        for mode in range(1, 27):
            vm.shot_mode = mode
            index = vm.native(0x1BCCEC4, vm.util)
            for kind in (0x1B, 0x1C, 0x1D):
                creative = vm.native(0x1BD8D9C, vm.util, kind, CREATIVE_VA + bias)
                private = vm.native(0x1BD8D9C, vm.util, kind, INSERT_VA + bias)
                expected = raw[CREATIVE_VA + 4 + index * 3 + kind - 0x1B]
                assert creative == private == expected, (mode, kind, private, creative, expected)
                validity.append(dict(shot_mode=mode, index=index, kind=hex(kind), valid=private))
        builds = []
        for mode in (1, 2, 5, 12, 26):
            vm.shot_mode = mode
            for kind in (0x1B, 0x1C):
                before = vm.candidates(kind, False)
                after = vm.candidates(kind, True)
                without_private = [dict(g, items=[i for i in g["items"] if i != 0x635],
                                        entries=[i for i in g["entries"] if i["mid"] != 0x635])
                                   for g in after]
                without_private = [g for g in without_private if g["items"]]
                assert before == without_private
                count = sum(g["items"].count(0x635) for g in after)
                index = vm.native(0x1BCCEC4, vm.util)
                expected = raw[CREATIVE_VA + 4 + index * 3 + kind - 0x1B]
                assert count == expected
                creative_mid = vm.native(0x1BD86D8, 0x1F2)
                stock = [(g["group_id"], i) for g in after for i in g["items"] if i == creative_mid]
                assert len(stock) == expected
                builds.append(dict(shot_mode=mode, kind=hex(kind), appended_private_count=count,
                                   creative_look_count=len(stock), original_items_unchanged=True,
                                   private_groups=[g for g in after if 0x635 in g["items"]]))
        rows.append(dict(bias=hex(bias), validity=validity, builds=builds,
                         native_private_availability_executed=0x1BC84A0 in vm.trace,
                         actual_descriptor_lookup_executed=0x1BD912C in vm.trace))
    report = dict(passed=True, AP_sha256=hashlib.sha256(raw).hexdigest(),
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  native_validity_cases=sum(len(r["validity"]) for r in rows),
                  native_build_cases=sum(len(r["builds"]) for r in rows), rows=rows,
                  limits=["Actual A64 generic dispatcher, Fn table builder, private alias, descriptor lookup and availability execute at two PIE bases.",
                          "Other native menus' model/product availability and current camera shooting mode are explicit environment fixtures.",
                          "Still/movie builder does not consume the playback tab-order hash; its ctor/dtor are fixtures.",
                          "Candidate visibility is separate from persistent Fn registration, activation, return and physical LCD acceptance."])
    (HERE / "fn433_candidates.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("rows", "limits")}))


if __name__ == "__main__":
    main()
