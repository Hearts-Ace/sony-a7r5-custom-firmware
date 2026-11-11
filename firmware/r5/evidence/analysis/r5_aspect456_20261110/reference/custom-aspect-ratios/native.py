"""针对锁定原厂组件的只读定位辅助；结果须按实际指令和调用上下文核对。"""
import hashlib
import io
import json
from pathlib import Path
import struct

from capstone import Cs, CS_ARCH_ARM, CS_ARCH_ARM64, CS_MODE_ARM, CS_MODE_THUMB
from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent


class Native:
    def __init__(self, stock, kind):
        row = json.loads((HERE / 'inputs.lock.json').read_text())['files'][kind]
        self.raw = (Path(stock) / row['path']).read_bytes()
        if len(self.raw) != row['bytes'] or hashlib.sha256(self.raw).hexdigest() != row['sha256']:
            raise ValueError('原厂输入身份不符：' + kind)
        self.kind = kind
        self.elf = ELFFile(io.BytesIO(self.raw)) if kind == 'AP' else None
        self.decoder = Cs(CS_ARCH_ARM64 if kind == 'AP' else CS_ARCH_ARM,
                          CS_MODE_ARM if kind == 'AP' else CS_MODE_THUMB)

    def offset(self, address):
        if self.kind == 'CP':
            offset = address - 0x108000
            if 0 <= offset < len(self.raw):
                return offset
        else:
            for segment in self.elf.iter_segments():
                if segment['p_type'] == 'PT_LOAD' and segment['p_vaddr'] <= address < segment['p_vaddr'] + segment['p_filesz']:
                    return segment['p_offset'] + address - segment['p_vaddr']
        raise ValueError(f'地址不在文件映射中：{address:#x}')

    def data(self, address, size):
        position = self.offset(address)
        return self.raw[position:position + size]

    def instructions(self, address, size):
        return list(self.decoder.disasm(self.data(address, size), address))

    def dump(self, address, size):
        return '\n'.join(f'{i.address:#x} {i.mnemonic} {i.op_str}' for i in self.instructions(address, size))

    def calls(self, target, start=None, end=None):
        result = []
        if self.kind == 'AP':
            lo, hi = start or 0x16dcdd0, end or 0x371afb0
            for address in range(lo, hi, 4):
                word = struct.unpack_from('<I', self.raw, address)[0]
                if word & 0xfc000000 != 0x94000000:
                    continue
                immediate = word & 0x3ffffff
                destination = address + (((immediate ^ 0x2000000) - 0x2000000) << 2)
                if destination == target:
                    result.append(address)
        else:
            lo, hi = start or 0x108000, end or (0x108000 + len(self.raw) - 4)
            for address in range(lo, hi, 2):
                a, b = struct.unpack_from('<HH', self.raw, address - 0x108000)
                if a & 0xf800 != 0xf000 or b & 0xd000 not in (0xc000, 0xd000):
                    continue
                s = (a >> 10) & 1
                i, j = 1 ^ ((b >> 13) & 1) ^ s, 1 ^ ((b >> 11) & 1) ^ s
                immediate = ((s << 24) | (i << 23) | (j << 22)
                             | ((a & 1023) << 12) | ((b & 2047) << 1))
                immediate = (immediate ^ 0x1000000) - 0x1000000
                destination = address + 4 + immediate
                if b & 0xd000 == 0xc000:
                    destination = ((address + 4) & ~3) + (immediate & ~3)
                if destination == (target & ~1):
                    result.append(address)
        return result

    def string_references(self, target, start=0x16dcdd0, end=0x371afb0):
        if self.kind != 'AP':
            raise ValueError('此定位器仅处理 A64 ADRP/ADD 字符串引用')
        result = []
        for address in range(start, end, 4):
            word = struct.unpack_from('<I', self.raw, address)[0]
            if word & 0x9f000000 != 0x90000000:
                continue
            immediate = (((word >> 5) & 0x7ffff) << 2) | ((word >> 29) & 3)
            page = (address & ~4095) + (((immediate ^ 0x100000) - 0x100000) << 12)
            if page != target & ~4095:
                continue
            register = word & 31
            for delta in range(4, 32, 4):
                following = struct.unpack_from('<I', self.raw, address + delta)[0]
                if (following & 0xffc00000 == 0x91000000 and (following >> 5) & 31 == register
                        and page + ((following >> 10) & 4095) == target):
                    result.append(address + delta)
        return result
