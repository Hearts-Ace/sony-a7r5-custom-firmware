"""Fn registration presenter -> native list child string -> private name bridge.

The candidate rows come from the actual Fn builder. View map, visible column
and selected-row location are fixtures; no font/backend or camera runs.
"""
from pathlib import Path
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from replay_fn434 import FnVM, CAND, RAM, X
from replay_main_menu425 import R, SP


class LabelVM(FnVM):
    def hook(self, u, pc, size, arg):
        at = pc - self.bias
        if hasattr(self, "util") and pc == self.q(self.q(self.util) + 0x78) and u.reg_read(X[1]) not in (0x635, 0x1E6):
            self.ret(0x02000000 + u.reg_read(X[1]))
            return
        if at == 0x1BD54D8 and u.reg_read(X[0]) not in (0x635, 0x1E6):
            # Other items have runtime-dependent native title callbacks, which
            # are outside the private/Creative Look name comparison.
            self.ret(0x02000000 + u.reg_read(X[0]))
            return
        if at in (0x2E7D208, 0x2E7CEE4):
            self.trace.add(at)
            self.ret()
            return
        if at == 0x1BD6B10:
            # Selection location in the external Fn candidate dataset. The
            # visible candidate rows/title resolution themselves execute.
            self.trace.add(at)
            u.reg_write(X[1], 0)
            self.ret(0)
            return
        if at in (0x1800924, 0x180093C):
            self.trace.add(at)
            self.ret(0)
            return
        super().hook(u, pc, size, arg)

    def window(self, begin, end, registers):
        self.u.reg_write(R.UC_ARM64_REG_SP, SP)
        self.u.reg_write(R.UC_ARM64_REG_LR, 0)
        for reg, value in registers.items():
            self.u.reg_write(X[reg], value)
        self.u.emu_start(begin + self.bias, end + self.bias, count=100000)
        assert self.u.reg_read(R.UC_ARM64_REG_PC) == end + self.bias

    def labels(self, kind):
        groups = self.candidates(0x1B if kind == "still" else 0x1C)
        candidate_group = next(g for g in groups if 0x635 in g["items"])
        rows = candidate_group["items"]
        assert 2 <= len(rows) <= 7
        presenter = RAM + 0x1A0000
        viewmap = RAM + 0x1A8000
        param = RAM + 0x1AA000
        dummy = RAM + 0x1AC000
        context = RAM + 0x1B0000
        self.u.mem_write(presenter, bytes(0x4000))
        self.u.mem_write(viewmap, bytes(0x200))
        self.u.mem_write(param, bytes(0x1000))
        self.u.mem_write(context, bytes(0x300))
        self.w64(presenter + 0x40, viewmap)
        for offset in (0x10, 0x30, 0x150, 0x160):
            self.w32(viewmap + offset, 0)
            self.w64(viewmap + offset + 8, dummy)
        self.w32(viewmap + 0x40, 6)
        self.w64(viewmap + 0x48, param)
        self.w32(presenter + 0x1010, 0x38F if kind == "still" else 0x39B)
        self.w32(presenter + 0x1028, 2)
        self.trace.clear()
        position = RAM + 0x1AD000
        self.w32(position, candidate_group["tab"])
        self.w32(position + 4, candidate_group["group"])
        self.w32(position + 8, 0)
        # Actual Fn candidate-context producer reads the real builder output,
        # resolves every title and populates the presenter column data.
        self.native(0x1BC69A0, self.util, position, self.output, context)
        assert self.d(context + 0x138) == len(rows)
        assert [self.d(context + 0x158 + i * 4) for i in range(len(rows))] == rows
        self.native(0x21E77C0, presenter, context)
        resources = [self.d(param + 0x30 + (7 + index) * 4) for index in range(len(rows))]
        private_index = rows.index(0x635)
        display_index = 7 + private_index
        assert resources[private_index] == 0x02FF4230, (kind, resources)
        creative_index = rows.index(0x1E6)
        assert resources[creative_index] == 0x0200A2FD
        assert 0x1BC6A64 in self.trace
        assert 0x21E794C in self.trace or 0x21E7A78 in self.trace
        presenter_store = 0x21E794C if 0x21E794C in self.trace else 0x21E7A78
        # Run the native label-to-child movement in the actual type6 list
        # update. Position/animation calculation and other rows are out of
        # scope for this bounded window.
        owner = RAM + 0x200000
        group = RAM + 0x1D0000
        child = RAM + 0x1E0000
        child_param = child + 0x1D8
        image_param = RAM + 0x1F0000
        self.u.mem_write(child, bytes(0xC00))
        self.w32(owner + 0x208 + display_index * 4, resources[private_index])
        self.w64(group + 0x38, child_param)
        self.w64(group + 0xA8, image_param)
        self.window(0x185B9D8, 0x185BA40,
                    {26: owner, 28: group, 20: display_index, 24: 0, 21: 1, 29: SP - 0x200})
        assert self.d(child_param + 0x30) == 0x02FF4230
        assert self.q(child_param + 0x38) == 0
        self.events.clear()
        # Real view_string resource-path code reads the child model resource,
        # calls its native resolver and then the exact patched name callsite.
        self.window(0x1885B20, 0x1885B3C,
                    {19: child, 20: RAM + 0x1FF000, 29: SP - 0x200})
        assert self.events == [("name_char", "自定义滤镜")], self.events
        return dict(kind=kind, native_builder_mids=[hex(n) for n in rows],
                    resource_ids=[hex(n) for n in resources],
                    private_index=private_index, private_list_cell=display_index,
                    private_child_resource=hex(self.d(child_param + 0x30)),
                    private_text_dispatch=self.events.copy(),
                    creative_look_index=creative_index,
                    creative_look_resource=hex(resources[creative_index]),
                    native_candidate_title_store="0x1bc6a64",
                    native_presenter="0x21e77c0", native_title_call=hex(presenter_store),
                    native_list_label_store="0x185ba10",
                    native_string_name_call="0x1885b38")


def main():
    ap = CAND / "ap/appFw.so"
    rows = []
    for bias in (0, 0x40000000):
        vm = LabelVM(ap, bias)
        rows.append(dict(bias=hex(bias), cases=[vm.labels(kind) for kind in ("still", "movie")]))
    report = dict(
        passed=True, AP_sha256=hashlib.sha256(ap.read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        registration_label_cases=4, rows=rows,
        native_executed=["Fn generic candidate dispatcher and builder",
                         "1bc69a0 current candidate column and descriptor label resolution, then 21e77c0 complete registration presenter row filling",
                         "185b9d8..185ba40 actual type6 label-to-view_string model movement",
                         "1885b20..1885b3c native view_string resource path and exact existing private name bridge"],
        fixtures=["Candidate position and view map are fixtures; the candidate dataset and column context execute native builders.",
                  "Selection-location query 1bd6b10 returns the first column; it does not replace a title lookup.",
                  "List geometry/animation and other widgets are not executed in the bounded type6 update window.",
                  "A fresh child string model has no borrowed char pointer; native renderer uses its resource branch.",
                  "Camera shoot/profile flags 1800924/180093c return zero; FnVM fixtures also apply.",
                  "Other candidate items' runtime-dependent titles are fixtures; private 635 and original Creative Look 1e6 execute the real title resolver.",
                  "Lock/context services 2e7d208/2e7cee4 are fixtures.",
                  "TextSprite resource/UTF-8 entry points are captured; no rasterizer or framebuffer executes."],
        limits=["The Fn registration list is verified separately from the Fn first-screen selected title.",
                "Native label propagation and actual UTF-8 dispatch do not establish physical glyphs, truncation, layout or timing."])
    (HERE / "fn434_registration_labels.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("rows", "native_executed", "fixtures", "limits")}))


if __name__ == "__main__":
    main()
