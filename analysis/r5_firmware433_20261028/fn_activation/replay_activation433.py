"""Final-AP native Fn activation, title/icon consumers and private return.

CPU replay only. The report lists the OS, object and rendering fixtures;
neither a camera nor a host target process is executed.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
CAND = HERE.parent
ROOT = CAND.parents[1]
sys.path[:0] = [str(ROOT / 'vendor/audit-python'), str(CAND / 'fn')]
from replay_fn_save433 import SaveVM, RAM, X

AP = CAND / 'ap/appFw.so'
EXPECTED = '65bd99095f626f990890156c0e536d56394c75313452caa451322e1148c1faec'
ICON = 0x021c6410
TITLE = 0x02ff4230
FN = 0xc2
PAGE = 0xd9


class ActivationVM(SaveVM):
    def __init__(self, path, bias):
        self.render_calls = []
        self.native_value = False
        self.title_stage = False
        self.tile_stage = False
        super().__init__(path, bias)
        # Complete immutable original row pairs, plus the actual initialized
        # private row descriptors. Native normalization and tree lookup run.
        pairs = [(struct.unpack('<Q', self.im.read(a, 8))[0],
                  self.im.pointer(a + 8) + bias)
                 for a in range(0x5030590, 0x5046300, 16)]
        pairs += [(0x1600 + n, self.sy['r5_filter_menu_rows'] + n * 128)
                  for n in range(13)]
        self.map_at_got(0x5915b80, pairs, 'ptr')
        self.manager = RAM + 0x210000
        self.w64(self.controller + 0x180, self.manager)
        self.w32(self.controller + 0x178, FN)
        self.w64(self.manager, 0x58d2fb8 + bias)
        self.w32(self.manager + 0x1e8, 0x4cf)
        data, node = RAM + 0x212000, RAM + 0x213000
        self.w64(node, data)
        for off, value in [(0x10, data), (0x18, data), (0x20, data + 0x1f4),
                           (0x28, node), (0x30, data), (0x38, data),
                           (0x40, data + 0x1f4), (0x48, node)]:
            self.w64(self.manager + 0x198 + off, value)
        self.open_data = data
        self.row_pid = self.native(0x28a87e8)
        self.w32(self.row_pid, 0x1607)

    def hook(self, u, pc, size, arg):
        at = pc - self.bias
        a = [u.reg_read(r) for r in X[:5]]
        if at == 0x16d95f0:
            u.mem_write(a[0], bytes([a[1] & 255]) * a[2])
            self.ret(a[0]); return
        if at in (0x36935c4, 0x369360c, 0x16da680):
            self.trace.add(at); self.ret(); return
        if at == 0x1d2e2f0:
            self.trace.add(at)
            self.w32(a[0] + 0x178, PAGE)
            self.w64(a[0] + 0x180, a[1])
            self.ret(a[0]); return
        if pc == self.sy.get('r5_filter_selected'):
            self.ret(0); return
        if self.title_stage and at in (0x21704ac, 0x21706d0):
            # Independent tile visibility/population is replayed below through
            # its actual producer. Here isolate selected-title projection.
            self.ret(); return
        if self.tile_stage and at in (0x183c284, 0x183c780):
            # Adjacent value/highlight child widgets are not the icon child.
            self.ret(); return
        if self.tile_stage and RAM + 0x2a0000 <= pc < RAM + 0x2a0100:
            self.render_calls.append((hex(pc), list(a)))
            if pc == RAM + 0x2a0004: self.ret(RAM + 0x2b1000)
            elif pc == RAM + 0x2a0008: self.ret(RAM + 0x2b2000)
            else: self.ret()
            return
        if self.native_value and at == 0x1bd55fc:
            # Do not inherit the main-title harness's value placeholder.
            self.trace.add(at); self.recent.append(hex(at)); return
        super().hook(u, pc, size, arg)

    def activation(self, kind, slot):
        self.w32(self.kind, kind == 'movie')
        self.w32(self.movie_enabled, 1)
        for name, base in self.current.items():
            for i in range(12): self.w32(base + 4 * i, 0x575)
        self.w32(self.current[kind] + 4 * slot, 0x635)
        read = self.native(0x216eb9c, self.controller, slot)
        assert read == 0x635
        # Focused MID is a genuine PID3B2 storage location, read by the
        # unmodified Fn handler through the real getter.
        self.w32(self.selected, read)
        self.w64(self.manager + 0x198 + 0x30, self.open_data)
        self.trace.clear()
        assert self.native(0x1a5de30, self.controller, 0, 0x0201000c) == 1
        record = struct.unpack('<4I2B2x', self.u.mem_read(self.open_data, 20))
        assert record == (FN, PAGE, FN, 0, 1, 0), record
        assert self.q(self.manager + 0x198 + 0x30) == self.open_data + 20
        assert self.d(self.selected) == 0x635 and self.d(self.row_pid) == 0x1607
        required = [0x1a5de30, 0x216f2d8, 0x216e9ac, 0x28a8720,
                    0x1bd70d8, 0x1bdc3d0, 0x1bd5780, 0x1bd59f0,
                    0x216ea14, 0x1d15b50, 0x1d15cfc]
        assert all(v in self.trace for v in required), [hex(v) for v in required if v not in self.trace]
        return dict(kind=kind, slot=slot, reader_mid=hex(read),
                    event='0x0201000c', queue_record=list(record),
                    selected_pid_3b2='0x635', row_pid_3b7='0x1607',
                    native_required=[hex(v) for v in required])

    def menu_icons(self):
        # Both getters execute their real virtual facade and descriptor lookup.
        assert self.native(0x1bd5630, 0x635) == ICON
        assert self.native(0x1bd642c, 0x635) == ICON
        assert self.d(self.desc + 0xc) == self.d(0x5858b08 + self.bias + 0xc) == ICON
        model, out = RAM + 0x220000, RAM + 0x226000
        self.w32(model + 0x1030, 0x2b36)
        self.w32(model + 0x1018, 0x635)
        self.trace.clear()
        self.native(0x20d34f8, model, out)
        assert self.d(out) == TITLE and self.d(out + 4) == ICON
        assert 0x1bd5630 in self.trace and 0x1bcef8c in self.trace
        # Common list/display producer's menu fallback uses descriptor+0C.
        self.w32(model + 0x10f8, 0x2b36)
        self.w32(model + 0x10e0, 0x335)
        self.w32(model + 0x1110, 0x635)
        self.trace.clear()
        self.native(0x20d1e54, model, out)
        assert self.d(out) == TITLE and self.d(out + 4) == ICON
        assert 0x1bd5630 in self.trace and 0x1bcef8c in self.trace
        draw = self.call(self.sy['r5_filter_menu_name_draw'], RAM + 0x228000, self.d(out))
        assert ('name_char', '自定义滤镜') in self.events
        return dict(normal_icon_getter='0x1bd5630', fn_icon_getter='0x1bd642c',
                    normal_menu_producer='0x20d34f8', common_list_producer='0x20d1e54',
                    stock_creative_descriptor='0x5858b08', icon=hex(ICON),
                    title_resource=hex(TITLE), title='自定义滤镜')

    def fn_projection(self, phase, presenter=None):
        presenter = presenter or RAM + 0x230000
        entries = RAM + 0x240000
        title, mode_label = RAM + 0x245000, RAM + 0x246000
        self.w64(presenter + 0x48, entries)
        self.w32(presenter + 0x39a0, 0x635)
        self.w32(presenter + 0x3d20, 1)
        self.w32(entries + 0x20, 0x18); self.w64(entries + 0x28, mode_label)
        self.w32(entries + 0xc0, 2); self.w64(entries + 0xc8, title)
        self.title_stage = True
        self.native(0x2170734, presenter)
        self.title_stage = False
        assert self.d(title + 0x30) == TITLE
        self.events.clear()
        self.call(self.sy['r5_filter_menu_name_draw'], RAM + 0x228000, self.d(title + 0x30))
        assert self.events == [('name_char', '自定义滤镜')], self.events
        table = self.q(0x5979748 + self.bias)
        icon_index = self.d(table)
        value_index = self.d(table + 4)
        icon_param, value_param = RAM + 0x247000, RAM + 0x248000
        self.w32(entries + icon_index * 16, 0x5d)
        self.w64(entries + icon_index * 16 + 8, icon_param)
        self.w32(entries + value_index * 16, 0xb)
        self.w64(entries + value_index * 16 + 8, value_param)
        self.w32(presenter + 0x38c8, 1); self.w32(presenter + 0x32c0, 1)
        self.w32(presenter + 0x39b8, 0x635)
        self.trace.clear()
        self.native(0x21705a8, presenter, 0, 0, 1)
        assert self.d(icon_param + 0x30) == 6 and self.d(icon_param + 0x34) == ICON
        assert all(v in self.trace for v in (0x21703f4, 0x2170264, 0x1bd642c, 0x2170374))
        widget, vtable, child, child_vtable = [RAM + x for x in (0x290000, 0x292000, 0x294000, 0x295000)]
        self.w64(widget, vtable)
        self.u.mem_write(widget + 0x204, b'\1')
        # Standard view-parameter binding is the sole data copy fixture.
        self.w32(widget + 0x208, self.d(icon_param + 0x30))
        self.w32(widget + 0x20c, self.d(icon_param + 0x34))
        self.w64(vtable + 0x30, RAM + 0x2a0000)
        self.w64(vtable + 0x38, RAM + 0x2a0004)
        self.w64(widget + 0x2e10, child); self.w64(child, child_vtable)
        self.w64(child_vtable + 0x140, RAM + 0x2a0008)
        self.w64(child_vtable + 0x148, RAM + 0x2a000c)
        self.w64(child_vtable + 0x150, RAM + 0x2a0010)
        self.tile_stage = True
        self.native(0x183c85c, widget)
        self.tile_stage = False
        sprite = RAM + 0x2b2000
        assert self.d(sprite + 0x3c) == ICON and self.d(sprite + 0x4c) == 1
        assert 0x183c138 in self.trace
        return dict(phase=phase, title_producer='0x2170734', title_resource=hex(TITLE),
                    title_text='自定义滤镜', tile_producer='0x21705a8',
                    tile_type=6, tile_resource=hex(ICON),
                    tile_renderer='0x183c85c', native_sprite_writer='0x183c138',
                    sprite_resource=hex(self.d(sprite + 0x3c)), sprite_resource_enabled=True)

    def private_return(self):
        self.w32(self.selected, 0x635)
        factory = self.q(0x506bf20 + PAGE * 0x60 + 8 + self.bias)
        assert factory == self.sy['r5_filter_controller425']
        controller = self.call(factory, 0, self.manager, 0, 0, 0, 0)
        assert controller and self.d(controller + 0x178) == PAGE
        # No cached main-menu presenter is supplied. The compiled private
        # controller resolves its value natively and invokes native pop.
        self.native_value = True
        self.trace.clear()
        result = self.call(self.q(self.q(controller) + 0x10), controller, 0, 0x0201000f)
        self.native_value = False
        assert result == 1
        assert self.d(self.manager + 0x1e8) == PAGE
        required = [0x1bd55fc, 0x1bc8eb8, 0x1d15798]
        assert all(at in self.trace for at in required), [hex(at) for at in required if at not in self.trace]
        assert self.d(self.selected) == 0x635 and self.d(self.row_pid) == 0x1607
        return dict(private_factory=hex(factory - self.bias),
                    controller_ctor_body_fixture='0x1d2e2f0',
                    close_event='0x0201000f', native_value_helper='0x1bd55fc',
                    native_close_screen='0x1d15798', close_request=hex(PAGE),
                    no_parent_presenter_fixture=True)


def main():
    actual = hashlib.sha256(AP.read_bytes()).hexdigest()
    assert actual == EXPECTED, actual
    rows = []
    for bias in (0, 0x40000000):
        vm = ActivationVM(AP, bias)
        # Native Fn SID binding: factory C2 -> wrapper -> ctor sets C2 and
        # installs scr0135_0001_controller's vtable.
        assert vm.im.pointer(0x50707e8) == 0x1d2ba30
        assert vm.im.pointer(0x5975478) + 0x10 == 0x58d6eb8
        cases = [vm.activation(kind, slot) for kind in ('still', 'movie') for slot in range(12)]
        icons = vm.menu_icons()
        projection = vm.fn_projection('entry')
        returned = vm.private_return()
        rows.append(dict(bias=hex(bias), activations=cases, icons=icons, private_return=returned,
                         fn_projection=[projection]))
    report = dict(passed=True, AP_sha256=actual,
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  native_activation_cases=sum(len(r['activations']) for r in rows),
                  native_icon_consumer_cases=len(rows) * 4,
                  native_private_return_cases=len(rows), rows=rows,
                  limits=[
                      'Actual final AP A64 executes at two PIE bases. Native Fn first-slot reader, real Enter dispatcher, descriptor route and open queue execute for all 24 still/movie slots.',
                      'Fn current selection is set through genuine PID3B2 storage after the real slot reader; focus navigation and physical button events are outside this replay.',
                      'Original menu/row registries are balanced-tree fixtures retaining all immutable pairs and initialized private descriptors; OS locks/logs/validation, memcpy/memset and selected-filter service=0 are explicit fixtures.',
                      'Private controller runs its compiled reserved-object factory and close dispatcher; original ctor body is an object fixture. Native committed-name lookup and manager close request execute; lower stack restoration is a separate replay.',
                      'Normal menu/common list producers and native normal/Fn icon getters execute; actual Fn title/tile producers and tile renderer/native sprite writer execute. Map objects, view-param binding copy, sprite storage/submission and adjacent value/highlight methods are fixtures; no GPU or physical LCD is executed.',
                      'Fn title projection suppresses its independent tile-refresh calls21704ac/21706d0, then actual21705a8 tile population is replayed separately. After native stack restore in fn433_stack_restore.json, native projection is replayed against reconstructed presenter storage; the actual factory/UI event loop is not run.',
                  ])
    out = HERE / 'fn433_activation.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('rows', 'limits')}))


if __name__ == '__main__': main()
