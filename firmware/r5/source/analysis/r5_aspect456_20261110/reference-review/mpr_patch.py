"""为锁定 Sony 4.00 libmpr 安装精确 HEIF 辅助尺寸分类；只操作普通文件。"""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess

from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MPR_BYTES = 3541784
MPR_SHA256 = 'ba1aa289a142c2d0b41d0864a57a0d72a2c796de89c5caf215ebaf124143e9af'
LINKER = ROOT / 'projects/firmware/development/shutter-sound-recovery455/src/lib/strict_ap_link.py'
HOOK = 0x26717c
RAW_HOOK = 0x26c7ec
JPEG_METADATA_HOOK = 0x274320
PREFIX = 0x200


def branch(at, target, link=False):
    delta = target - at
    if delta & 3 or not -(1 << 27) <= delta < (1 << 27):
        raise ValueError('MPR A64 分支超出范围')
    return struct.pack('<I', (0x94000000 if link else 0x14000000) | ((delta >> 2) & 0x3ffffff))


def patch_mpr(raw, output):
    output = Path(output)
    if len(raw) != MPR_BYTES or hashlib.sha256(raw).hexdigest() != MPR_SHA256:
        raise ValueError('MPR 原厂输入身份不符')
    if output.exists():
        raise ValueError('MPR 输出目录已存在')
    elf = ELFFile(io.BytesIO(raw))
    if elf['e_type'] != 'ET_DYN' or elf['e_machine'] != 'EM_AARCH64' or elf['e_phentsize'] != 56:
        raise ValueError('MPR ELF 格式不符')
    loads = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']

    def offset(va):
        for segment in loads:
            if segment['p_vaddr'] <= va and va + 4 <= segment['p_vaddr'] + segment['p_filesz']:
                return segment['p_offset'] + va - segment['p_vaddr']
        raise ValueError(f'MPR 地址未映射：{va:#x}')

    if raw[offset(HOOK):offset(HOOK) + 4] != bytes.fromhex('a16340b9'):
        raise ValueError('MPR 原生 ispe 分类入口前像不符')
    # 原 LOAD（包括 BSS）地址不变，新段位于完整原映射之后。
    align = lambda value: (value + 65535) & -65536
    rx = align(max(s['p_vaddr'] + s['p_memsz'] for s in loads))
    rxfile = align(len(raw))
    output.mkdir(parents=True)
    (output / 'INCOMPLETE.json').write_text('{"state":"PATCHING_MPR"}\n')
    module = output / 'module'
    module.mkdir()
    sources = [HERE / 'source/mpr_heif.S', HERE / 'source/mpr_raw_metadata.c', HERE / 'source/mpr_jpeg_metadata.c']
    objects = []
    commands = []
    compiler = shutil.which('clang')
    if compiler is None:
        raise ValueError('MPR 构建需要 clang')
    for source in sources:
        obj = module / (source.stem + '.o')
        command = [compiler, '--target=aarch64-none-elf', '-O2', '-Wall', '-Wextra',
                   '-Werror', '-ffreestanding', '-fno-builtin', '-fno-stack-protector',
                   '-fno-vectorize', '-fno-slp-vectorize', '-fno-unwind-tables',
                   '-fno-asynchronous-unwind-tables', '-c', str(source), '-o', str(obj)]
        compiled = subprocess.run(command, capture_output=True, text=True)
        (module / (source.stem + '.compile.log')).write_text(compiled.stdout + compiled.stderr)
        if compiled.returncode:
            raise ValueError('MPR helper 编译失败：' + source.name)
        objects.append(obj)
        commands.append(command)
    spec = importlib.util.spec_from_file_location('aspect_mpr_strict_link', LINKER)
    linker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(linker)
    externals = dict(aspect_mpr_native_aux_body=0x267180,
                     aspect_mpr_native_thumb=0x267194,
                     aspect_mpr_native_scn=0x2671d0,
                     aspect_mpr_native_raw_metadata_body=RAW_HOOK + 4,
                     aspect_mpr_native_raw_metadata_error=0x26cc10,
                     aspect_mpr_native_tag=0x26f050,
                     aspect_mpr_native_jpeg_size=0x274b44,
                     aspect_mpr_native_jpeg_vtable=0x2fe800,
                     aspect_mpr_native_cammeta=0x273bbc)
    code, data, memory, symbols, relocations, layout = linker.link(
        objects, rx, rx + 65536, bytes(PREFIX), externals)
    if data or memory or len(code) > 65536:
        raise ValueError('MPR helper 必须仅含独立只读可执行段')
    image = bytearray(raw)
    changes = []

    def edit(at, after, expected):
        before = bytes(image[at:at + len(after)])
        if before != expected:
            raise ValueError(f'MPR 前像不符：{at:#x}')
        image[at:at + len(after)] = after
        changes.append(dict(offset=at, before=before.hex(), after=after.hex()))

    edit(offset(HOOK), branch(HOOK, symbols['aspect_mpr_heif_aux_entry']), bytes.fromhex('a16340b9'))
    edit(offset(RAW_HOOK), branch(RAW_HOOK, symbols['aspect_mpr_raw_metadata_entry']), bytes.fromhex('41030a8b'))
    edit(offset(JPEG_METADATA_HOOK),
         branch(JPEG_METADATA_HOOK, symbols['aspect_mpr_jpeg_metadata'], link=True),
         bytes.fromhex('27feff97'))
    names = {'PT_LOAD': 1, 'PT_DYNAMIC': 2, 'PT_GNU_EH_FRAME': 0x6474e550,
             'PT_GNU_STACK': 0x6474e551, 'PT_GNU_RELRO': 0x6474e552, 'PT_PHDR': 6}

    def ph(segment):
        return struct.pack('<II6Q', names[segment['p_type']], segment['p_flags'],
                           *[segment[key] for key in ('p_offset', 'p_vaddr', 'p_paddr',
                                                     'p_filesz', 'p_memsz', 'p_align')])

    original_headers = b''.join(ph(s.header) for s in elf.iter_segments())
    phdr_bytes = (elf['e_phnum'] + 2) * 56
    # PT_PHDR 在所有 LOAD 前，并指向新增 RX 内实际映射的完整表。
    headers = struct.pack('<II6Q', 6, 4, rxfile, rx, rx, phdr_bytes, phdr_bytes, 8)
    headers += original_headers + struct.pack('<II6Q', 1, 5, rxfile, rx, rx, len(code), len(code), 65536)
    if len(headers) > PREFIX:
        raise ValueError('MPR 程序头超出独立段保留前缀')
    code = bytearray(code)
    code[:len(headers)] = headers
    (module / 'rx.bin').write_bytes(code)
    edit(32, struct.pack('<Q', rxfile), struct.pack('<Q', elf['e_phoff']))
    edit(56, struct.pack('<H', elf['e_phnum'] + 2), struct.pack('<H', elf['e_phnum']))
    image.extend(bytes(rxfile - len(image)))
    image.extend(code)
    reverse = bytearray(image[:len(raw)])
    for row in reversed(changes):
        at = row['offset']
        reverse[at:at + len(bytes.fromhex(row['before']))] = bytes.fromhex(row['before'])
    if reverse != raw:
        raise AssertionError('MPR 反向字节核对失败')
    final_elf = ELFFile(io.BytesIO(image))
    final_headers = list(final_elf.iter_segments())
    if (b''.join(ph(s.header) for s in final_headers[1:-1]) != original_headers
            or final_elf.get_section_by_name('.rela.dyn').data() != elf.get_section_by_name('.rela.dyn').data()
            or final_elf.get_section_by_name('.rela.plt').data() != elf.get_section_by_name('.rela.plt').data()):
        raise AssertionError('MPR 原程序头或动态重定位改变')
    target = output / 'libmpr.so'
    target.write_bytes(image)
    result = dict(passed=True, camera_io=False, device_tested=False,
                  input_sha256=MPR_SHA256, input_bytes=len(raw), bytes=len(image),
                  sha256=hashlib.sha256(image).hexdigest(), patches=changes,
                  RX=rx, rx_file=rxfile, code_bytes=len(code), phdr_bytes=phdr_bytes,
                  mapped_PT_PHDR=True, original_program_headers_unchanged=True,
                  dynamic_relocations_unchanged=True, reverse_exact=True,
                  hook=HOOK, jpeg_metadata_hook=JPEG_METADATA_HOOK, symbols=symbols, relocations=relocations, layout=layout,
                  sources={**{str(s.relative_to(HERE)): hashlib.sha256(s.read_bytes()).hexdigest() for s in sources},
                           'mpr_patch.py': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
                  linker_sha256=hashlib.sha256(LINKER.read_bytes()).hexdigest(),
                  commands=commands, added_exact_pairs={'SCN': [[1616, 968], [1616, 600], [1616, 1000], [1616, 680], [1616, 872]],
                                                        'THM': [[256, 208], [240, 208]]})
    (output / 'patch.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    (output / 'INCOMPLETE.json').unlink()
    return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=patch_mpr((ROOT/'unpacked/r5/usr_complete/lib/libmpr.so').read_bytes(),a.output)
    print(json.dumps({k:r[k] for k in ('passed','sha256','bytes','code_bytes','reverse_exact')}))
