"""Small read-only helpers for offline ELF/ARM64 investigation."""
import io
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
from elftools.elf.elffile import ELFFile

class Image:
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        self.elf = ELFFile(io.BytesIO(self.data))
        self.loads = [s for s in self.elf.iter_segments() if s['p_type'] == 'PT_LOAD']
        self.text = self.elf.get_section_by_name('.text')
        self.md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
        rela = self.elf.get_section_by_name('.rela.dyn')
        self.relocs = {address: (info, addend) for address, info, addend in
                       struct.iter_unpack('<QQq', rela.data())} if rela else {}
    def offset(self, va):
        for s in self.loads:
            if s['p_vaddr'] <= va < s['p_vaddr'] + s['p_filesz']:
                return va - s['p_vaddr'] + s['p_offset']
        raise ValueError(f'VA not file-backed: {va:#x}')
    def va(self, offset):
        for s in self.loads:
            if s['p_offset'] <= offset < s['p_offset'] + s['p_filesz']:
                return offset - s['p_offset'] + s['p_vaddr']
        raise ValueError(f'Offset not loaded: {offset:#x}')
    def read(self, va, size):
        offset = self.offset(va)
        return self.data[offset:offset + size]
    def string(self, va):
        try:
            offset = self.offset(va)
            end = self.data.index(b'\0', offset, offset + 1024)
            return self.data[offset:end].decode('ascii')
        except (ValueError, UnicodeError):
            return ''
    def dis(self, va, size):
        return '\n'.join(f'{i.address:08x}: {i.bytes.hex():8s} {i.mnemonic:7s} {i.op_str}'
                         for i in self.md.disasm(self.read(va, size), va))
    def pointer(self, va):
        if va in self.relocs:
            return self.relocs[va][1]
        return struct.unpack('<Q', self.read(va, 8))[0]
    def references(self, target):
        return [va for va, (info, addend) in self.relocs.items() if addend == target]
    def words(self):
        return struct.iter_unpack('<I', self.text.data())
    def calls(self, target):
        matches = []
        base = self.text['sh_addr']
        for i, (word,) in enumerate(self.words()):
            if word & 0x7c000000 == 0x14000000:
                imm = word & 0x3ffffff
                if imm & 0x2000000:
                    imm -= 0x4000000
                if base + i * 4 + imm * 4 == target:
                    matches.append(base + i * 4)
        return matches

    def address_candidates(self, targets):
        """Heuristic ADRP + ADD/load references, not a data-flow proof.

        Returns effective addresses in targets. Stops on branches or a write
        to the page register for the common ADD/load forms being inspected.
        Inspect returned disassembly before drawing conclusions.
        """
        targets = set(targets)
        pages = {a & ~0xfff for a in targets}
        words = [w for (w,) in self.words()]
        base = self.text['sh_addr']
        hits = []
        for i, word in enumerate(words):
            if word & 0x9f000000 != 0x90000000:
                continue
            imm = ((word >> 29) & 3) | (((word >> 5) & 0x7ffff) << 2)
            if imm & (1 << 20):
                imm -= 1 << 21
            page = ((base + i * 4) & ~0xfff) + (imm << 12)
            if page not in pages:
                continue
            reg = word & 31
            for j in range(i + 1, min(i + 13, len(words))):
                w = words[j]
                address = None
                if (w >> 5) & 31 == reg:
                    if w & 0xff000000 == 0x91000000:
                        address = page + (((w >> 10) & 0xfff) << (12 if w & (1 << 22) else 0))
                    elif w & 0x3b000000 == 0x39000000:
                        address = page + (((w >> 10) & 0xfff) << (w >> 30))
                if address in targets:
                    hits.append((base + i * 4, base + j * 4, address))
                if w & 0x7c000000 == 0x14000000 or w & 0xfffffc1f == 0xd65f0000:
                    break
                if w & 31 == reg and (w & 0xff000000 == 0x91000000 or
                                     w & 0x3b400000 == 0x39400000):
                    break
        return hits
