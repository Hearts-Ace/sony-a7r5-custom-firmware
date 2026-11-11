#!/usr/bin/env python3
"""Read-only exact-4.55 five-page layout and native null-allocator audit.

Adapted from the supplied reference's inspect_ui.py. This tool writes only a
new evidence directory and never starts a build/package/device operation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / 'vendor/audit-python'), str(HERE.parent / 'integration')]
from inspect_ap import Image
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn import arm64_const as A

BASE = ROOT / 'projects/firmware/releases/4.55-sound-recovery-20261105/appFw.so'
BASE_SHA = 'a5ea55ed9251ed90b91803e8cab0c8ad6e79dbc62d202bce655a21afe78399ee'
PAGES = [
    ('select', 98, 4, 0, 0x59239e8, 0x5930f80),
    ('fn38', 38, 6, 0, 0x5969138, 0x592f0c0),
    ('fn76', 76, 6, 0, 0x597fcb8, 0x5917a40),
    ('shoot585', 585, 4, 61, 0x595b878, 0x597ba50),
    ('shoot442', 442, 3, 61, 0x593a618, 0x5919c90),
]
CREATE = (0x1db602c, 0x1d0ae64, 0x1da5d24, 0x1d0bc64, 0x1df4e50,
          0x1d0bb84, 0x1d9ba18, 0x1d1574c, 0x1e179e0, 0x1d15664)
DRAW = (0x1db648c, 0x1da61f8, 0x1df5600)
SITES = (*CREATE, *DRAW, 0x2146224, 0x2156e70, 0x182e138, 0x182e1ac,
         0x240de2c, 0x1d9bb74, 0x1e17b1c)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def inspect(base, output):
    assert not output.exists(), 'Evidence output must be new'
    image = Image(base)
    assert sha(image.raw) == BASE_SHA, 'Requires the exact read-only 4.55 AP'
    def data(va, size):
        at = image.offset(va)
        return image.raw[at:at + size]
    relocations = {at: addend for at, info, addend in
                   struct.iter_unpack('<QQq', image.elf.get_section_by_name('.rela.dyn').data())
                   if info == 1027}
    pages, types = [], set()
    for name, count, row, kind, *globals_ in PAGES:
        tables = []
        for pointer_va in globals_:
            pointer = relocations[pointer_va]
            raw = data(pointer, count * 52)
            values = [struct.unpack_from('<I', raw, i * 52)[0] for i in range(count)]
            assert values[row] == kind, (name, row, values[row])
            types.update(values)
            tables.append(dict(VA=pointer, pointer_VA=pointer_va, sha256=sha(raw), types=values))
        pages.append(dict(name=name, count=count, row=row, kind=kind, tables=tables))
    u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    u.mem_map(0x1800000, 0x40000)
    u.mem_write(0x1800000, data(0x1800000, 0x40000))
    for address, size in ((0x20000000, 0x10000), (0x30000000, 0x10000), (0x40000000, 4096)):
        u.mem_map(address, size)
    allocations = []
    for table in (0x5020be8, 0x50210e0):
        sizes, entries = {}, {}
        for kind in sorted(types):
            entry = relocations[table + kind * 8]
            for i in range(29):
                u.reg_write(getattr(A, 'UC_ARM64_REG_X' + str(i)), 0)
            for register, value in ((A.UC_ARM64_REG_X0, 0x1000000),
                                    (A.UC_ARM64_REG_X2, 0x20000000),
                                    (A.UC_ARM64_REG_X3, 0x20000100),
                                    (A.UC_ARM64_REG_X4, 0x20000200),
                                    (A.UC_ARM64_REG_SP, 0x3000f000),
                                    (A.UC_ARM64_REG_LR, 0x40000000)):
                u.reg_write(register, value)
            u.mem_write(0x20000000, bytes(4))
            u.emu_start(entry, 0x40000000, count=2000)
            size = struct.unpack('<I', u.mem_read(0x20000000, 4))[0]
            assert (u.reg_read(A.UC_ARM64_REG_PC) == 0x40000000
                    and 0 < size < 0x1000000 and size % 128 == 0
                    and u.reg_read(A.UC_ARM64_REG_X0) == 0), (kind, entry, size)
            sizes[kind], entries[kind] = size, entry
        allocations.append((sizes, entries))
    for site in CREATE:
        assert data(site, 4).hex() == '00013fd6', hex(site)
    for site in DRAW:
        assert data(site, 4).hex() == '40003fd6', hex(site)
    assert data(0x2146224, 4).hex() == '003c4191'
    assert data(0x2156e70, 4).hex() == '001c4191'
    for site in (0x182e138, 0x182e1ac):
        assert data(site, 4).hex() == 'fd7bbea9'
    report = dict(passed=True, device_tested=False, camera_io=False,
                  AP_sha256=BASE_SHA, script_sha256=sha(Path(__file__).read_bytes()),
                  pages=pages, allocation_bytes=allocations[0][0], allocators=allocations[0][1],
                  disabled_allocation_bytes=allocations[1][0], disabled_allocators=allocations[1][1],
                  allocation_validation='Actual exact455 allocator instructions with null base and zero cursor; no constructor fixture',
                  sites=[dict(va=hex(v), before=data(v, 4).hex(), instruction=image.disasm(v, v + 4)) for v in SITES])
    output.mkdir(parents=True)
    (output / 'ui-layout.json').write_text(json.dumps(report, indent=2) + '\n')
    ranges = [(v - 24, v + 28) for v in SITES]
    ranges += [(0x2146224, 0x2146270), (0x2156e70, 0x2156ebc),
               (0x240dae0, 0x240df48), (0x182e138, 0x182e1ac),
               (0x2148ee8, 0x2149050), (0x21584a8, 0x21585e0),
               (0x2158fc8, 0x2159130)]
    (output / 'native-ui.asm').write_text('\n\n'.join(image.disasm(lo, hi) for lo, hi in ranges) + '\n')
    print(json.dumps(dict(passed=True, pages=len(pages), types=len(types),
                          allocator_calls=2 * len(types), AP_sha256=BASE_SHA)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=BASE)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inspect(args.base, args.output)
