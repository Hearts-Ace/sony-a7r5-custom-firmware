"""Read-only stock Creative Look icon selectors against the frozen 4.33 AP.

No selector, current-Look getter, row lookup or resource ID is stubbed.
The inherited harness provides named offline OS/container fixtures.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / 'vendor/audit-python'),
               str(ROOT / 'analysis/r5_firmware433_20261028/fn')]
from replay_fn_save433 import SaveVM, RAM, X

AP = ROOT / 'analysis/r5_firmware433_20261028/ap/appFw.so'


class IconVM(SaveVM):
    def __init__(self, path, bias):
        super().__init__(path, bias)
        pairs = [(struct.unpack('<Q', self.im.read(a, 8))[0],
                  self.im.pointer(a + 8) + bias)
                 for a in range(0x5030590, 0x5046300, 16)]
        pairs += [(0x1600 + n, self.sy['r5_filter_menu_rows'] + n * 128)
                  for n in range(13)]
        self.map_at_got(0x5915b80, pairs, 'ptr')
        # Startup 16FBF5C..84 builds this independent row alias multimap.
        # Missing it silently resolves original rows to the default 15D8.
        aliases = list(struct.iter_unpack('<II', self.im.read(0x3e52e40, 0xaeb8)))
        assert len(aliases) == 5591
        self.map_at_got(0x592f4c8, aliases, 'u32')
        self.look_pointer = self.native(0x28ae4b0)
        self.look_calls = []

    def hook(self, u, pc, size, arg):
        at = pc - self.bias
        if at == 0x28ae4b0 and hasattr(self, 'look_calls'):
            self.look_calls.append(self.d(self.look_pointer))
        super().hook(u, pc, size, arg)


def main():
    rows = []
    for bias in (0, 0x40000000):
        vm = IconVM(AP, bias)
        for n in range(12):
            at = 0x3f4a280 + n * 128
            row_id, = struct.unpack('<I', vm.im.read(at, 4))
            value, = struct.unpack('<I', vm.im.read(at + 0x34, 4))
            vm.w32(vm.look_pointer, value)
            vm.trace.clear()
            icon = vm.native(0x1bd642c, 0x1e6)
            selected = vm.native(0x1bd62ac, 0x1e6)
            resolved = vm.native(0x1bd6384, selected)
            row_icon = vm.native(0x1bd5840, selected)
            kind = vm.native(0x2170374, RAM + 0x230000, 0x1e6)
            print(json.dumps(dict(bias=hex(bias), value=value, row=hex(row_id),
                                  selected=hex(selected), icon=hex(icon), kind=kind,
                                  resolved=hex(resolved), row_icon=hex(row_icon))), flush=True)
            rows.append(dict(bias=hex(bias), value=value, row=hex(row_id),
                             selected_row=hex(selected), icon=hex(icon), type=kind,
                             native_trace=[hex(a) for a in sorted(vm.trace)]))
    report = dict(passed=True, AP_sha256=hashlib.sha256(AP.read_bytes()).hexdigest(),
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  current_look_pointer=hex(vm.look_pointer - bias),
                  cases=rows, look_getter='0x28ae4b0',
                  selector='0x1bd642c', private_selector_not_changed=True)
    (HERE / 'stock_icons.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
