#!/usr/bin/env python3
"""Build only the five Erlla FL23 AP changes on the exact official R5 App.

No former R5 patched App is an input. No settings/defaults, initializer,
writer, reset, relocation, updater or hardware operation is added. Validation
executes bounded AArch64 instruction paths in synthetic memory, not a camera.
"""
import argparse
import copy
import hashlib
import json
import re
import struct
from pathlib import Path

from elf_study import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'unpacked/r5/usr_complete/lib/appFw.so'
SOURCE_SHA = '41bd8f4cda1f44c7038912837737e1ce6a650065f2108061ada30e5c7f9ce7c7'
RECIPE = ROOT / 'analysis/erlla_a7m4_comparison_20261015/upstream/Erlla-sony-a7m4-custom-firmware-086df3b/a7m4/profiles/fl23/ap-recipe.json'
RECIPE_SHA = 'e05fea2c34b8b0e78fdcd983fc83bdbf33cdafeb91a13b771765b7de6b532cc7'
OUT = ROOT / 'build_r5_m4strict_4.03_20261015'
REGISTRY, LOOK_MASK, MAIN_MASK = 0x5557088, 0x4a249b0, 0x4a25b88
COLORS = [0, 3, 2, 1, 16, 15, 17, 18, 5, 13, 19, 20]
STOP = 0xfffffffffffffff0


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def operands(text):
    return [p.strip() for p in re.split(r',\s*(?![^\[]*\])', text)]


class LocalCPU:
    """Small fail-closed interpreter for the converter and real check dispatcher.

    Only three named executable ranges are admitted. Unmapped memory and any
    unimplemented instruction fail. Diagnostic code is an observed call boundary,
    not a successful stub. No external service/device call can execute.
    """
    allowed = [(0x3550354, 0x35503f0), (0x29051bc, 0x29051dc),
               (0x29053b0, 0x2905438)]

    def __init__(self, image, slide=0):
        self.image, self.slide = image, slide
        self.mem, self.cache, self.reg = {}, {}, {}
        self.instructions = 0
        self.z = self.n = self.v = self.c = False

    def get(self, r):
        if r in ('wzr', 'xzr'):
            return 0
        if r.startswith('#'):
            return int(r[1:], 0)
        key = 'x' + r[1:] if r.startswith('w') else r
        return self.reg.get(key, 0) & (0xffffffff if r.startswith('w') else 0xffffffffffffffff)

    def put(self, r, value):
        if r not in ('wzr', 'xzr'):
            self.reg['x' + r[1:] if r.startswith('w') else r] = value & (
                0xffffffff if r.startswith('w') else 0xffffffffffffffff)

    def store(self, address, value, size):
        for i, b in enumerate((value & ((1 << (size * 8)) - 1)).to_bytes(size, 'little')):
            self.mem[address + i] = b

    def load(self, address, size):
        data = []
        for i in range(size):
            a = address + i
            data.append(self.mem[a] if a in self.mem else self.image.read(a - self.slide, 1)[0])
        return int.from_bytes(bytes(data), 'little')

    def extend(self, value, spec):
        kind, _, count = spec.partition(' #')
        if kind.startswith('sxt'):
            bits = {'sxtb': 8, 'sxtw': 32}[kind]
            value &= (1 << bits) - 1
            if value & (1 << (bits - 1)):
                value -= 1 << bits
        elif kind == 'uxtw':
            value &= 0xffffffff
        elif kind != 'lsl':
            raise ValueError('Unsupported extension: ' + spec)
        return value << (int(count, 0) if count else 0)

    def address(self, operand):
        p = operands(operand.rstrip('!')[1:-1])
        value = self.get(p[0])
        if len(p) > 1:
            index = self.get(p[1])
            value += self.extend(index, p[2]) if len(p) > 2 else index
        return value

    def condition(self, cc):
        return {'eq': self.z, 'ne': not self.z, 'lt': self.n != self.v,
                'le': self.z or self.n != self.v, 'hi': self.c and not self.z}[cc]

    def run(self, entry, args):
        self.reg = {'sp': 0x100010000, 'x30': STOP}
        for i in range(19, 30):
            self.put('x' + str(i), 0x123400000000 + i * 0x100)
        for i, arg in enumerate(args):
            self.put('x' + str(i), arg)
        saved = {k: self.get(k) for k in ['sp'] + ['x' + str(i) for i in range(19, 30)]}
        pc = entry + self.slide
        for steps in range(200):
            if pc == STOP or pc == 0x35b858c + self.slide:
                require(all(self.get(k) == v for k, v in saved.items()), 'ABI violation')
                self.instructions += steps
                return {'value': self.get('w0'), 'diagnostic': pc != STOP}
            va = pc - self.slide
            require(any(a <= va < b for a, b in self.allowed), f'Unexpected execution {va:#x}')
            if pc not in self.cache:
                ins = next(self.image.md.disasm(self.image.read(va, 4), pc))
                self.cache[pc] = ins.mnemonic, operands(ins.op_str)
            op, p = self.cache[pc]
            nxt = pc + 4
            bits = 32 if p and p[0].startswith('w') else 64
            if op in ('stp', 'ldp'):
                at, size = self.address(p[2]), 4 if p[0].startswith('w') else 8
                if p[2].endswith('!'):
                    self.put(p[2][1:].split(',')[0], at)
                for i, r in enumerate(p[:2]):
                    if op == 'stp':
                        self.store(at + size * i, self.get(r), size)
                    else:
                        self.put(r, self.load(at + size * i, size))
                if len(p) == 4:
                    base = p[2][1:-1]
                    self.put(base, self.get(base) + self.get(p[3]))
            elif op in ('ldr', 'ldrb', 'str', 'strb'):
                size = 1 if op.endswith('b') else 4 if p[0].startswith('w') else 8
                at = self.address(p[1])
                if op.startswith('str'):
                    self.store(at, self.get(p[0]), size)
                else:
                    self.put(p[0], self.load(at, size))
            elif op in ('mov', 'adr', 'adrp', 'sxtw', 'uxtb', 'mvn'):
                value = self.get(p[1])
                if op == 'sxtw':
                    value = self.extend(value, 'sxtw')
                elif op == 'uxtb':
                    value &= 0xff
                elif op == 'mvn':
                    value = ~value
                self.put(p[0], value)
            elif op in ('add', 'sub', 'mul'):
                a, b = self.get(p[1]), self.get(p[2])
                if len(p) == 4:
                    b = self.extend(b, p[3])
                self.put(p[0], a + b if op == 'add' else a - b if op == 'sub' else a * b)
            elif op == 'cmp':
                a, b = self.get(p[0]), self.get(p[1])
                value, sign = (a - b) & ((1 << bits) - 1), 1 << (bits - 1)
                self.z, self.n, self.v, self.c = value == 0, bool(value & sign), bool((a ^ b) & (a ^ value) & sign), a >= b
            elif op == 'ands':
                a, b = self.get(p[1]), self.get(p[2])
                if len(p) == 4:
                    require(p[3].startswith('lsr #'), 'Unsupported AND shift')
                    b >>= int(p[3][5:], 0)
                value = a & b
                self.put(p[0], value)
                self.z, self.n, self.v, self.c = value == 0, bool(value & (1 << (bits - 1))), False, False
            elif op == 'cset':
                self.put(p[0], int(self.condition(p[1])))
            elif op in ('b', 'br', 'blr'):
                nxt = self.get(p[0])
                if op == 'blr':
                    self.put('x30', pc + 4)
            elif op.startswith('b.'):
                if self.condition(op[2:]):
                    nxt = self.get(p[0])
            elif op in ('cbz', 'cbnz'):
                if bool(self.get(p[0])) == (op == 'cbnz'):
                    nxt = self.get(p[-1])
            elif op == 'ret':
                nxt = self.get('x30')
            elif op != 'nop':
                raise ValueError(f'Unsupported instruction {pc:#x}: {op} {p}')
            pc = nxt
        raise ValueError('Instruction bound exceeded')


def verify(original, candidate):
    counts = {'converter_executions': 0, 'registry_checker_executions': 0, 'interpreted_instructions': 0}
    values = list(range(256)) + [0xffffffff, 0x80000000, 0x7fffffff]
    styles = list(range(19)) + [0xffffffff, 0x80000000, 0x7fffffff]
    output = 0x100020000
    for slide in (0, 0x10000000):
        cpus = [LocalCPU(im, slide) for im in (original, candidate)]
        for style in styles:
            for value in values:
                results = []
                for cpu in cpus:
                    cpu.store(output - 8, int.from_bytes(b'\xa5' * 32, 'little'), 32)
                    result = cpu.run(0x3550354, [style, value, output])
                    actual = cpu.load(output, 1)
                    require(cpu.load(output - 8, 8) == 0xa5a5a5a5a5a5a5a5, 'Write before output')
                    require(cpu.load(output + 1, 23) == int.from_bytes(b'\xa5' * 23, 'little'), 'Write beyond output')
                    results.append((actual, result['diagnostic']))
                    counts['converter_executions'] += 1
                expected = (255, False) if style == 16 else (COLORS[value], False) if value < 12 else (0xa5, True)
                require(results[1] == expected, f'Converter semantics {style}/{value}: {results}')
                if style == 16 or value not in (10, 11):
                    require(results[0] == results[1], 'Existing converter behavior changed')
                else:
                    require(results[0] == (0xa5, True), 'Unexpected original new-look acceptance')
        for pid in [0x690] + list(range(0x163a, 0x1670)):
            size = 19 if pid == 0x690 else 12
            row = REGISTRY + pid * 24
            for cpu, im in zip(cpus, (original, candidate)):
                require(im.pointer(row) == 0x29051bc, 'Unexpected validator function')
                require(struct.unpack('<I', im.read(row + 16, 4))[0] == size, 'Unexpected mask size')
                cpu.store(row + slide, im.pointer(row) + slide, 8)
                cpu.store(row + slide + 8, im.pointer(row + 8) + slide, 8)
            for value in [0xffffffff, 0x80000000, *range(size + 2), 0x7fffffff]:
                results = [cpu.run(0x29053b0, [pid, value, 0, 0]) for cpu in cpus]
                require(results[1] == {'value': int(value < size), 'diagnostic': False}, 'Candidate mask boundary')
                require(results[0] == {'value': int(value < size - 2), 'diagnostic': False}, 'Original mask boundary')
                counts['registry_checker_executions'] += 2
        counts['interpreted_instructions'] += sum(cpu.instructions for cpu in cpus)
    return dict(counts, backend='Bounded fail-closed Python AArch64 instruction interpreter',
                tested_slides=['0x0', '0x10000000'], diagnostic='stop at original diagnostic entry; not executed',
                converter_output_write_bounds_passed=True, callee_saved_registers_and_sp_preserved=True,
                checked_all_54_current_still_movie_look_validators=True,
                limitations=['Synthetic local instruction execution, not complete App or camera execution.',
                             'No claim of UI availability until required per-camera settings/color deployment is performed.',
                             'No image-quality, boot, updater, persistence or hardware validation.'])


def build(out):
    original = Image(SOURCE)
    require(sha(original.data) == SOURCE_SHA, 'Official R5 input identity mismatch')
    recipe_raw = RECIPE.read_bytes()
    require(sha(recipe_raw) == RECIPE_SHA, 'Pinned M4 recipe identity mismatch')
    recipe = json.loads(recipe_raw)
    require(len(recipe['patches']) == 5, 'Expected exactly five upstream AP patch groups')
    require(sorted((a - REGISTRY - 8) // 24 for a in original.references(LOOK_MASK)) == list(range(0x163a, 0x1670)), 'Look mask scope changed')
    require(original.references(MAIN_MASK) == [REGISTRY + 0x690 * 24 + 8], 'Main mask scope changed')
    require(original.read(LOOK_MASK, 12) == b'\1' * 10 + b'\0\0', 'Unexpected original look mask')
    require(original.read(MAIN_MASK, 19) == b'\1' * 17 + b'\0\0', 'Unexpected original main mask')
    for row, enum in [(0x3f4a580, 17), (0x3f4a600, 18)]:
        require(original.read(row + 0x34, 8) == struct.pack('<II', enum, 0x690), 'Wrong menu identity')
        require(original.read(row + 0x44, 40) == b'\1\0' * 4 + b'\0\0' * 16, 'Unexpected menu profile flags')
    addresses = [0x3550368, 0x3f4a5c4, 0x3f4a644, LOOK_MASK + 10, MAIN_MASK + 17]
    expected_converter = bytes.fromhex('3f2400716803005400b100d00040139100486138610000102088208b00001fd660008052f5ffff17')
    require(original.read(addresses[0], 40) == expected_converter, 'Converter preimage mismatch')
    blob, patches = bytearray(original.data), []
    for i, (va, upstream) in enumerate(zip(addresses, recipe['patches'])):
        new = bytes.fromhex(upstream['new_hex'])
        require(len(new) == (40 if i < 3 else 2), 'Patch size changed')
        offset = original.offset(va)
        before = original.read(va, len(new))
        blob[offset:offset + len(new)] = new
        patches.append(dict(group=i + 1, va=hex(va), file_offset=hex(offset), size=len(new),
                            before_hex=before.hex(), after_hex=new.hex(),
                            changed_bytes=sum(a != b for a, b in zip(before, new)),
                            m4_file_offset=hex(upstream['offset']), m4_purpose=upstream['purpose'],
                            exact_m4_patch_bytes=True))
    # Compare all unlisted byte spans, not just previously known trouble sites.
    previous = 0
    for patch in sorted(patches, key=lambda p: int(p['file_offset'], 16)):
        offset = int(patch['file_offset'], 16)
        require(blob[previous:offset] == original.data[previous:offset], 'Unlisted byte change')
        previous = offset + patch['size']
    require(blob[previous:] == original.data[previous:], 'Unlisted tail change')
    candidate = copy.copy(original)
    candidate.data = bytes(blob)
    untouched = []
    for name, start, size in [
        ('all former slot normalizers / initializers', 0x2a4a000, 0x3000),
        ('shared writer and six property writer callbacks', 0x2cf7468, 0x901c - 0x7468),
        ('direct model setter, no detour', 0x263bc58, 0x100),
        ('all 54 registered slot default rows', 0x4a422f8, 54 * 8),
        ('remaining original converter cases after M4 40-byte patch', 0x3550390, 0x48),
        ('former executable/data cave region', 0x3ecc116, 0x3ee13ec - 0x3ecc116),
    ]:
        before, after = original.read(start, size), candidate.read(start, size)
        require(before == after, 'Unexpected retained old patch: ' + name)
        untouched.append(dict(name=name, va=hex(start), size=size, sha256=sha(after), equals_official=True))
    rela = original.elf.get_section_by_name('.rela.dyn')
    start, size = int(rela['sh_offset']), int(rela['sh_size'])
    require(candidate.data[start:start + size] == original.data[start:start + size], 'Relocations changed')
    verification = verify(original, candidate)
    path, evidence = out / 'patched/appFw.so', out / 'evidence/ap'
    require(not path.exists() or path.read_bytes() == candidate.data,
            'Output already exists with different content; no overwrite')
    path.parent.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(candidate.data)
    report = dict(scope='Strict five-group M4 AP recipe mapped onto official R5 4.00 App, offline only',
                  source=str(SOURCE), source_sha256=SOURCE_SHA, original_sha256=SOURCE_SHA,
                  source_size=len(original.data),
                  upstream_commit='086df3b1e33dfa0206553ac2bb003535c58ddb80',
                  upstream_recipe=str(RECIPE), upstream_recipe_sha256=RECIPE_SHA,
                  output=str(path), output_sha256=sha(candidate.data), output_size=len(candidate.data),
                  patches=patches, only_listed_patch_ranges_changed=True,
                  total_changed_bytes=sum(p['changed_bytes'] for p in patches),
                  former_r5_patched_components_used_as_input=False,
                  original_initializers_writers_defaults_preserved=untouched,
                  all_relocations_unchanged=True, per_camera_settings_modified=False,
                  verification=verification, verification_passed=True,
                  validation_scope='Offline bounded local instruction execution and full-byte comparison; no camera execution')
    (evidence / 'manifest.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    (evidence / 'verification.json').write_text(json.dumps(dict(
        verification, original_sha256=SOURCE_SHA, output_sha256=sha(candidate.data),
        passed=True, verification_passed=True, hardware_tested=False,
        only_five_upstream_patch_groups=True, no_old_slotfix_input=True,
        full_file_unlisted_bytes_unchanged=True, all_relocations_unchanged=True,
        all_original_initializers_writers_defaults_unchanged=True), indent=2, ensure_ascii=False) + '\n')
    (evidence / 'converter_disassembly.txt').write_text('OFFICIAL\n' + original.dis(0x3550354, 0x9c) + '\n\nM4-STRICT\n' + candidate.dis(0x3550354, 0x34) + '\nINLINE TABLE @ 0x3550384: ' + candidate.read(0x3550384, 12).hex() + '\n')
    rows = ['# R5 AP：严格对应 M4 的五组改动', '',
            '输入仅为 R5 官方 4.00 `appFw.so`。没有读取旧 slotfix 或失败 4.03 App。', '',
            '| M4 原方案 | R5 地址 | 改动 |', '|---|---|---|',
            '| look→CP converter | `0x3550368` | 作者40字节补丁原样映射；look 10/11→CP color 19/20 |',
            '| FL2菜单产品flags | `0x3f4a5c4` | 原有前4项保留为1，后16项0→1 |',
            '| FL3菜单产品flags | `0x3f4a644` | 原有前4项保留为1，后16项0→1 |',
            '| look允许表 | `0x4a249ba` | 10/11放行，共享表覆盖current/still/movie全部54项 |',
            '| 主style允许表 | `0x4a25b99` | 17/18放行 |', '',
            '全文件比较确认，仅这五个范围有变化；实际改变 ' + str(report['total_changed_bytes']) + ' 个字节。',
            '全部 ELF 重定位、六槽初始化、共享 writer、直接 model setter、54个槽默认行与官方逐字节一致。',
            '前版强制槽位、初始化、复位、写入保护及18项mask指针重定位均未加入。', '',
            '验证执行了有界 AArch64 原始指令路径，覆盖完整8位look输入和有符号边界、两种加载地址、全部54项参数检查及主style检查。',
            '诊断分支在原函数边界停止；没有执行完整App、设备I/O或成像。真实机身功能仍需作者方案要求的本机六项设置及颜色部署，不能由本AP验证推定完成。', '',
            '`appFw.so` SHA-256: `' + report['output_sha256'] + '`',
            '', '机器可读精确前后字节、测试计数和原厂保留范围见 `manifest.json`。']
    (evidence / 'README.md').write_text('\n'.join(rows) + '\n')
    return {k: report[k] for k in ['output', 'output_sha256', 'output_size', 'total_changed_bytes']} | {'verification': verification}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=OUT)
    args = parser.parse_args()
    print(json.dumps(build(args.build.resolve()), indent=2, ensure_ascii=False))
