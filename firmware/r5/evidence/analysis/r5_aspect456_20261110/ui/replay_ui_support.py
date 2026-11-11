#!/usr/bin/env python3
"""Offline-only exact455 final-ELF and real libObj/GCC/C++ replay support.

OS locks, allocator/libc services, global UX layer registration and palette
resource lookup are explicit fixtures. No replacement UI draw/producer/gate
implementation is installed. Unknown external calls fail closed.
"""
from pathlib import Path
import hashlib
import io
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / 'vendor/audit-python'), str(HERE.parent / 'integration')]
from replay_final_ap import FinalAP, STACK, STOP, Q
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_MEM_INVALID
from unicorn import arm64_const as A

LIBRARIES = {
    'lib/libObj.so': (0x50000000, '0d0be8f1e48b3c74330f9afab698ac352b3c2a922f7231ffc836591529a9fdf9'),
    'lib/libgcc_s.so.1': (0x51000000, '9a348469b43aaf815f32104139a62116ef1247662a965b24e38e88e574814805'),
    'lib/libstdc++.so.6.0.22': (0x52000000, '28f2d082aea5206c42ba15664f39e2eaf7febed8f6264305e7e16aa44c878389'),
}
PALETTE_SHA = 'e52bb5a3e551a2a3f6dfddd1dc95b7c27d03cf6e40449a58157297a538c3a667'
WIDGET, INIT, COMMON = 0x20010000, 0x20020000, 0x20020200
SNAPSHOT, FLAGS = 0x20100000, 0x20050000
VIEW, ARENA = 0x68000000, 0x6a000000
PRESENTER, PARAMETERS = 0x20060000, 0x20040000


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(ok, message):
    assert ok, message


class UIReplay(FinalAP):
    def __init__(self, candidate, build, bias):
        self.externals = {}
        self.external_calls = []
        self.locked = 0
        self.on_unlock = None
        self.resource_reads = []
        self.deferred_tls = []
        self.heap = 0x60000000
        super().__init__(candidate, build, bias)
        self.u.mem_map(0x20000000, 0x400000)
        self.u.mem_map(self.heap, 0x1000000)
        self.u.mem_map(0x70000000, 0x100000)
        self.u.mem_map(VIEW, 0x200000)
        self.u.mem_map(ARENA, 0x400000)
        self.u.hook_add(UC_HOOK_MEM_INVALID, self.invalid)
        self.layout = json.loads((HERE / 'evidence/layout/ui-layout.json').read_text())
        library_root = ROOT / 'unpacked/r5/usr_complete'
        palette = (library_root / 'share/app/color_cmn.uxc').read_bytes()
        require(sha(palette) == PALETTE_SHA, 'Actual color bank hash mismatch')
        self.palette = palette
        self.library_hashes = {}
        self.ap_elf = self.im.elf
        images = [(self.ap_elf, bias)]
        for name, (base, expected) in LIBRARIES.items():
            raw = (library_root / name).read_bytes()
            require(sha(raw) == expected, 'Actual native library hash mismatch: ' + name)
            self.library_hashes[name] = expected
            elf = ELFFile(io.BytesIO(raw))
            for segment in elf.iter_segments():
                if segment['p_type'] != 'PT_LOAD':
                    continue
                at = base + segment['p_vaddr']
                lo = at & -4096
                end = (at + segment['p_memsz'] + 4095) & -4096
                if end > lo:
                    self.u.mem_map(lo, end - lo)
                if segment['p_filesz']:
                    self.u.mem_write(at, segment.data())
            images.append((elf, base))
        self.exports = {}
        for elf, base in images:
            for symbol in elf.get_section_by_name('.dynsym').iter_symbols():
                if symbol['st_shndx'] != 'SHN_UNDEF' and symbol.name:
                    self.exports[symbol.name] = symbol['st_value'] + (0 if symbol['st_shndx'] == 'SHN_ABS' else base)
        by_name = {}
        self.graphics_relocated = 0
        for elf, base in images:
            for section in elf.iter_sections():
                if section['sh_type'] != 'SHT_RELA':
                    continue
                symbols = elf.get_section(section['sh_link'])
                for relocation in section.iter_relocations():
                    kind = relocation['r_info_type']
                    if kind == 1027:
                        value = base + relocation['r_addend']
                    elif kind in (257, 1025, 1026):
                        symbol = symbols.get_symbol(relocation['r_info_sym'])
                        if symbol.name not in self.exports:
                            if symbol.name not in by_name:
                                stub = 0x70000000 + len(by_name) * 16
                                by_name[symbol.name] = stub
                                self.externals[stub] = symbol.name
                            value = by_name[symbol.name]
                        else:
                            value = self.exports[symbol.name]
                        value += relocation['r_addend']
                    elif kind in (1028, 1029, 1030, 1031):
                        self.deferred_tls.append(base + relocation['r_offset'])
                        continue
                    else:
                        raise AssertionError(('Unsupported native-library relocation', kind))
                    self.write(base + relocation['r_offset'], value, '<Q')
                    self.graphics_relocated += 1
        # Explicit zeroed UX engine counter storage, not a running display engine.
        context_pointer = self.read(0x50000000 + 0x2651a0, '<Q')
        self.write(context_pointer, 0x60f00000, '<Q')
        if not bias:
            self.u.mem_protect(0, 4096, 0)

    def invalid(self, u, access, address, size, value, data):
        raise AssertionError(('Unmapped/native boundary', hex(u.reg_read(A.UC_ARM64_REG_PC)),
                              hex(address), size, hex(self.x(30)), self.external_calls[-4:]))

    def addr(self, symbol):
        return self.sy[symbol]

    def read(self, address, fmt='<I'):
        return struct.unpack(fmt, self.u.mem_read(address, struct.calcsize(fmt)))[0]

    def write(self, address, value, fmt='<I'):
        self.u.mem_write(address, struct.pack(fmt, value))

    def returning(self, value=0):
        self.ret(value)

    def invoke(self, name, *args):
        # Named and integer addresses here are always module/native VAs; an
        # external-library address can be passed as target - self.bias.
        target = self.sy[name] if isinstance(name, str) else name + self.bias
        for i, arg in enumerate(args):
            self.putx(i, arg)
        self.u.reg_write(A.UC_ARM64_REG_SP, STACK + 0x1f000)
        self.putx(29, 0)
        self.putx(30, STOP)
        self.u.emu_start(target, STOP, count=2000000)
        require(self.u.reg_read(A.UC_ARM64_REG_PC) == STOP,
                ('Instruction limit or unexpected return', name, hex(self.u.reg_read(A.UC_ARM64_REG_PC))))
        return self.x(0)

    def hook(self, u, address, size, data):
        at = address - self.bias
        if at == 0x2e7d208:
            self.locked += 1
            return self.returning()
        if at == 0x2e7cee4:
            self.locked -= 1
            require(self.locked >= 0, 'Unlock without lock')
            if self.on_unlock:
                self.on_unlock()
            return self.returning()
        if at == 0x1bd5b40:
            # Availability of two display options only. Actual product/model
            # init, maps, gates, public setter and native visibility still run.
            return self.returning(0)
        if address == 0x50000000 + 0x174bcc:
            self.external_calls.append('MODELED:Widget::setLayerID')
            return self.returning()
        if at == 0x16db070:
            # Resource-manager lookup only; preserve actual bank RGBA. Native
            # Guide/child opacity logic, CColor and Sprite setters still run.
            sprite, index, resource = self.x(0), self.x(1), self.x(2)
            key = struct.pack('<I', (resource & 0xffffff) | 0x3a000000)
            offset = self.palette.find(key)
            require(offset >= 0 and self.palette.find(key, offset + 1) < 0, 'Palette key is not unique')
            rgba = self.palette[offset + 4:offset + 8]
            records = self.read(sprite + 0xd0, '<Q')
            self.u.mem_write(records + index * 44 + 0x22, rgba)
            self.resource_reads.append(resource)
            return self.returning()
        # Assert the graphics operation happens after releasing model locks.
        if at in (0x16db870, 0x16dac20, 0x16da960, 0x16dbce0, 0x16da040, 0x16da300, 0x182da28):
            require(not self.locked, 'Graphics while holding model lock')
        name = self.externals.get(address)
        if name is None:
            return super().hook(u, address, size, data)
        self.external_calls.append(name)
        args = [self.x(i) for i in range(3)]
        if name in ('malloc', '_Znwm', '_Znam'):
            value = self.heap
            self.heap += max((args[0] + 15) & -16, 16)
            require(self.heap < 0x60e00000, 'Fixture heap exhausted')
            return self.returning(value)
        if name in ('free', '_ZdlPv', '_ZdaPv', '__cxa_atexit'):
            return self.returning()
        if name in ('memcpy', 'memmove'):
            require(args[2] < 0x800000, 'Fixture libc copy size')
            if args[2]:
                u.mem_write(args[0], bytes(u.mem_read(args[1], args[2])))
            return self.returning(args[0])
        if name == 'memset':
            require(args[2] < 0x800000, 'Fixture memset size')
            if args[2]:
                u.mem_write(args[0], bytes([args[1] & 255]) * args[2])
            return self.returning(args[0])
        raise AssertionError(('Unmodeled native external service', name))

    def model(self, values):
        for name, value in values.items():
            pointer = self.invoke('r5_ui_native_model_' + name)
            self.write(pointer, value)

    def local_position(self, widget):
        pointer = self.invoke(self.exports['_ZNK2ux6wgtsys6Widget11getLocalPosEv'] - self.bias, widget)
        return struct.unpack('<2f', self.u.mem_read(pointer, 8))

    def construct_guide(self):
        self.u.mem_write(INIT, bytes(48))
        self.u.mem_write(COMMON, struct.pack('<12I', 0, 0, 0, 0, 0, 0, 0, 0, 640, 480, 0, 0))
        used = COMMON + 128
        self.write(used, 0)
        require(self.invoke(0x181f028, 0x400000, WIDGET, used, INIT, COMMON) == WIDGET,
                'Actual Guide allocator returned wrong widget')
        require(self.read(used) == 0x1b00, 'Actual native Guide allocation changed')
        window = self.read(self.bias + 0x59305c8, '<Q')
        self.u.mem_write(window, struct.pack('<4I', 0, 0, 640, 480))
        self.invoke(0x182d764, WIDGET)

    def snapshot(self, native_aspect=0):
        for offset, value in ((0, 1), (0x24d8, 2), (0x24b0, native_aspect),
                              (0x2500, 0), (0x2520, 26), (0x2540, 640), (0x2560, 426)):
            self.write(SNAPSHOT + offset, value)

    def child(self, index):
        widget = self.read(WIDGET + 0x1a68 + index * 8, '<Q')
        records = self.read(widget + 0x210 + 0xd0, '<Q')
        return dict(mode=self.u.mem_read(widget + 0x41, 1)[0],
                    rectangle=(*self.local_position(widget), *struct.unpack('<2f', self.u.mem_read(records + 8, 8))),
                    rgba=bytes(self.u.mem_read(records + 0x22, 4)).hex())

    def construct_image(self, widget=WIDGET):
        self.u.mem_write(INIT, bytes(48))
        self.invoke(0x1846ee0, widget, INIT)
        self.invoke(0x1846da8, widget)
        require(self.read(widget + 0x208) == 0, 'Actual Image parameter initial state')
        require(self.read(widget + 0x214) == 0xffffffff, 'Actual loaded image empty')
        require(self.read(widget + 0x248 + 0xd8) == 0x90009, 'Actual Sprite rectangle count')
        require(self.invoke('r5_ui_native_sprite_image', widget + 0x248) == 0xffffffff, 'Actual native image getter empty')

    def sprite_rects(self, widget=WIDGET):
        records = self.read(widget + 0x248 + 0xd0, '<Q')
        return [dict(rectangle=struct.unpack('<4f', self.u.mem_read(records + i * 44, 16)),
                     rgba=bytes(self.u.mem_read(records + i * 44 + 0x22, 4)).hex()) for i in range(9)]
