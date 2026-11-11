#!/usr/bin/env python3
"""Compile existing AP state/menu plus the replacement five-page UI module.

No old guide source, diagnostics, packaging, device access or baseline writes.
The functions UI_SOURCES, UI_NATIVE, layout_header and wrappers are the parent
integration interface; parent may add separately reviewed cancel sources.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AP = HERE.parent / 'ap'
CANCEL = HERE.parent / 'cancel'
sys.path[:0] = [str(ROOT / 'vendor/audit-python'), str(AP), str(HERE.parent / 'integration'),
               str(ROOT / 'projects/firmware/development/shutter-sound-recovery455/src/lib')]
from strict_ap_link import link
from compile_module import NATIVE as AP_NATIVE, SOURCES as AP_SOURCES
from inspect_ap import Image

BASE_SHA = '23f5b11d8f79c7c984fc42a4e6d2cac9dc5b5d74bb327b3b36e77985112f3bf6'
BASE = ROOT / 'projects/firmware/releases/4.55-sound-recovery-20261105/appFw.so'
UI_SOURCES = tuple(HERE / n for n in ('preview_core.c', 'ui_create.c', 'ui_preview.c', 'ui_draw.c', 'ui_hooks.S'))
CANCEL_SOURCES = tuple(CANCEL / n for n in ('r5_aspect_cancel.c', 'r5_aspect_cancel_hooks.S'))
CANCEL_NATIVE = {'r5_aspect_capture_continue': 0x2adfd40,
                 'r5_aspect_restore_continue': 0x2adfd60,
                 'r5_native_aspect_saved': 0x8410778,
                 'r5_native_restore_alias': 0x1bc50ec}
UI_NATIVE = {
    'r5_ui_native_guide_update_continue': 0x182e13c,
    'r5_ui_native_guide_destroy_continue': 0x182e1b0,
    'r5_ui_native_guide_model_0_continue': 0x2146228,
    'r5_ui_native_guide_model_1_continue': 0x2156e74,
    'r5_ui_native_guide_producer': 0x240dae0,
    'r5_ui_native_guide_body': 0x240dd00,
    'r5_ui_native_guide_rect': 0x182da28,
    'r5_ui_native_guide_show_no': 0x240db10,
    'r5_ui_native_guide_show_yes': 0x240de30,
    'r5_ui_native_model_lock': 0x2e7d208, 'r5_ui_native_model_unlock': 0x2e7cee4,
    'r5_ui_native_model_x': 0x28c4fcc, 'r5_ui_native_model_y': 0x28c4ff4,
    'r5_ui_native_model_w': 0x28c501c, 'r5_ui_native_model_h': 0x28c5044,
    'r5_ui_native_model_route': 0x28c6674, 'r5_ui_native_model_format': 0x28d416c,
    'r5_ui_native_model_direction': 0x28e4934, 'r5_ui_native_model_mapping': 0x28a6924,
    'r5_ui_native_model_mode': 0x28a3c28, 'r5_ui_native_model_aspect': 0x28aace8,
    'r5_ui_native_widget_position': 0x16db870, 'r5_ui_native_widget_mode': 0x16dac20,
    'r5_ui_native_rect_position': 0x16da960, 'r5_ui_native_rect_size': 0x16dbce0,
    'r5_ui_native_rect_color': 0x16da040, 'r5_ui_native_color_construct': 0x16da300,
    'r5_ui_native_sprite_image': 0x16d97a0,
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def layout_header(layout):
    report = json.loads(layout.read_text())
    assert report['passed'] and report['AP_sha256'] == BASE_SHA
    image = Image(BASE)
    assert sha(image.raw) == BASE_SHA
    for page in report['pages']:
        for table in page['tables']:
            at = image.offset(table['VA'])
            assert sha(image.raw[at:at + page['count'] * 52]) == table['sha256']
    count = max(map(int, report['allocation_bytes'])) + 1
    lines = ['/* Generated from exact455 actual native null-allocator evidence. */',
             '#ifndef R5_UI_LAYOUT_H', '#define R5_UI_LAYOUT_H', '#include <stdint.h>',
             '#define R5_UI_ALLOCATOR_COUNT ' + str(count)]
    for name, key in (('allocation', 'allocation_bytes'), ('disabled', 'disabled_allocation_bytes')):
        values = [report[key].get(str(i), 0) for i in range(count)]
        lines += ['static const uint32_t r5_ui_' + name + '_bytes[] = {' + ','.join(map(str, values)) + '};']
    for key in ('count', 'row', 'kind'):
        lines += ['static const unsigned r5_ui_page_' + key + '[5] = {' +
                  ','.join(str(p[key]) for p in report['pages']) + '};']
    lines += ['static inline const void *r5_ui_page_table(unsigned page, unsigned direction) {',
              'switch (page * 2 + direction) {']
    bindings = {}
    for i, page in enumerate(report['pages']):
        for j, table in enumerate(page['tables']):
            name = 'r5_ui_table_' + str(i) + '_' + str(j)
            lines += [f'case {i * 2 + j}: {{ extern const unsigned char {name}[]; return {name}; }}']
            bindings[name] = table['VA']
    lines += ['default: return 0;', '}}', '#endif']
    return '\n'.join(lines) + '\n', bindings


def wrappers():
    def save():
        out = ['sub sp,sp,#0x320']
        out += [f'stp x{i},x{i+1},[sp,#{i*8}]' for i in range(0, 30, 2)]
        out += ['str x30,[sp,#0xf0]', 'mrs x9,nzcv', 'mrs x10,fpsr', 'mrs x11,fpcr',
                'stp x9,x10,[sp,#0x100]', 'str x11,[sp,#0x110]']
        return out + [f'stp q{i},q{i+1},[sp,#{0x120+i*16}]' for i in range(0, 32, 2)]
    def restore():
        out = [f'ldp q{i},q{i+1},[sp,#{0x120+i*16}]' for i in range(0, 32, 2)]
        out += ['ldp x9,x10,[sp,#0x100]', 'ldr x11,[sp,#0x110]', 'msr nzcv,x9',
                'msr fpsr,x10', 'msr fpcr,x11', 'ldr x30,[sp,#0xf0]']
        return out + [f'ldp x{i},x{i+1},[sp,#{i*8}]' for i in range(0, 30, 2)] + ['add sp,sp,#0x320']
    lines = ['/* Native call inputs/results, including all Q registers and flags, survive. */',
             '.section .text.r5_ui_create_hook,"ax",%progbits', '.global r5_ui_create_hook',
             '.type r5_ui_create_hook,%function', 'r5_ui_create_hook:',
             'sub sp,sp,#0x20', 'stp x0,x5,[sp]', 'str x30,[sp,#0x10]']
    lines += save() + ['bl r5_ui_before_create', 'str w0,[sp,#0x338]'] + restore() + ['blr x8']
    lines += save() + ['add x9,sp,#0x320', 'ldp x0,x1,[x9]', 'ldr w2,[sp,#0x338]',
                      'bl r5_ui_after_create'] + restore()
    lines += ['ldr x30,[sp,#0x10]', 'add sp,sp,#0x20', 'ret', '.size r5_ui_create_hook,.-r5_ui_create_hook']
    # One shared implementation for all three post-update wrappers. X30 is
    # already the BL return address and is saved before it carries page ID;
    # the replaced BLR X2 overwrites it anyway. No native input GPR is changed.
    lines += ['.section .text.r5_ui_page_hooks,"ax",%progbits']
    for i in range(3):
        name = 'r5_ui_page_hook_' + str(i)
        lines += ['.global ' + name, '.type ' + name + ',%function', name + ':',
                  'str x30,[sp,#-0x10]!', f'mov x30,#{i}', 'str w30,[sp,#8]',
                  'b .Lr5_ui_page_common', '.size ' + name + ',.-' + name]
    lines += ['.Lr5_ui_page_common:', 'blr x2'] + save()
    lines += ['mov x0,x19', 'ldr w1,[sp,#0x328]', 'bl r5_ui_page_draw'] + restore()
    lines += ['ldr x30,[sp],#0x10', 'ret']
    return '\n'.join(lines) + '\n'


def compile_ui(output, layout):
    assert not output.exists(), 'Build output must be new'
    output.mkdir(parents=True)
    header, table_bindings = layout_header(layout)
    (output / 'ui_layout.h').write_text(header)
    generated = output / 'ui_wrappers.S'
    generated.write_text(wrappers())
    sources = [AP / n for n in AP_SOURCES] + list(UI_SOURCES) + list(CANCEL_SOURCES) + [generated]
    commands, objects = [], []
    for source in sources:
        obj = output / (source.stem + '.o')
        command = ['clang', '--target=aarch64-none-elf', '-Oz', '-ffreestanding', '-fno-builtin',
                   '-fno-stack-protector', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
                   '-fno-jump-tables', '-fno-pic', '-ffunction-sections', '-fdata-sections',
                   '-mno-outline-atomics', '-Wall', '-Wextra', '-Werror',
                   '-I', str(AP), '-I', str(HERE), '-I', str(output)]
        if source.suffix == '.c':
            command += ['-std=c11']
            if source.name != 'ui_draw.c':
                command += ['-mgeneral-regs-only']
        command += ['-c', str(source), '-o', str(obj)]
        result = subprocess.run(command, capture_output=True, text=True)
        (output / (source.name + '.log')).write_text(result.stdout + result.stderr)
        commands.append(command)
        assert result.returncode == 0, (source.name, result.returncode, result.stderr)
        objects.append(obj)
    native = {**AP_NATIVE, **UI_NATIVE, **CANCEL_NATIVE, **table_bindings}
    rx, rw = 0x8ee1000, 0x8ef0000
    code, data, memory, symbols, relocations, sections = link(objects, rx, rw, b'', native)
    assert len(code) < rw - rx and memory < 0x10000
    assert not any(n.startswith('r5_ui_') and ('trace' in n or 'capacity_failure' in n or 'stage' in n) for n in symbols)
    (output / 'rx.bin').write_bytes(code)
    (output / 'rw.bin').write_bytes(data)
    inputs = sources + [HERE / 'preview_core.h', HERE / 'ui_preview.h', AP / 'r5_aspect_state.h',
                       output / 'ui_layout.h', layout, Path(__file__).resolve()]
    report = dict(status='NONINSTALLABLE_COMPONENT', base_sha256=BASE_SHA,
                  rx=rx, rw=rw, rx_bytes=len(code), rw_file_bytes=len(data), rw_memory_bytes=memory,
                  symbols=symbols, native_symbols=native, relocations=relocations, sections=sections,
                  commands=commands, sources={str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in inputs},
                  rx_sha256=sha(code), rw_sha256=sha(data),
                  cancel_sources='candidate-f production sources; same paired native capture/restore contract',
                  limitations=['UI + current AP + Fn cancel component; final-ELF replay is separate',
                               'No old guide source/hooks and no diagnostics in candidate',
                               'No package, signing, camera, IPC, RAW or JPEG encoder modification'])
    (output / 'module.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('status', 'rx_bytes', 'rw_file_bytes', 'rw_memory_bytes', 'rx_sha256')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', type=Path, default=HERE / 'evidence/layout/ui-layout.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    compile_ui(args.output.resolve(), args.layout.resolve())
