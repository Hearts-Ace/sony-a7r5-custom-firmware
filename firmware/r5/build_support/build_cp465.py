#!/usr/bin/env python3
"""Compile the final CP once from original R5 and current source modules.

The filter resident source, sound module and aspect module are linked directly.
No previous custom CP, generated legacy filter source, source-text replacement
or previous-version build script participates.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import sys
import zlib

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(HERE / 'lib'))
from thumb_link import link
from thumb_ops import bw
from arm_ops import trampoline, branch, mov16
from stock_inputs import apply_recipe, recipe, save, sha

BASE = 0x108000
RX = 0x1195080
RX_END = 0x1197000
SOUND = 0x1a3a000
SOUND_SOURCE = 0x1198000
AUX = HERE / 'cp_aux'


def bl(at, target):
    code = bytearray(bw(at, target & ~1))
    struct.pack_into('<H', code, 2, struct.unpack_from('<H', code, 2)[0] | 0x4000)
    return bytes(code)


def build(stock_cp, out):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('CP output must be a new directory')
    out.mkdir(parents=True)
    baseline = out / 'cp-baseline.bin'
    apply_recipe(stock_cp, baseline, 'cp_baseline')
    raw = baseline.read_bytes()
    # Native grid permutation and original packing contract remain unchanged.
    order = struct.unpack_from('<405H', raw, 0xe8c1d8-BASE)
    assert sorted(order) == list(range(405)), 'Native grid permutation contract'

    commands = []
    compiler = shutil.which('clang')
    if not compiler:
        raise ValueError('clang is required')

    def compile_sources(sources, folder, defines=()):
        folder.mkdir(parents=True)
        objects = []
        for source in sources:
            obj = folder / (source.name + '.o')
            command = [compiler, '--target=arm-none-eabi', '-mthumb', '-march=armv7-a',
                '-mfloat-abi=soft', '-Oz', '-fno-jump-tables', '-ffreestanding',
                '-fno-builtin', '-fno-stack-protector', '-fno-unwind-tables',
                '-fno-asynchronous-unwind-tables', '-ffunction-sections', '-fdata-sections',
                '-fstack-usage', '-Wall', '-Wextra', '-Werror',
                '-I', str(PROJECT / 'cp'), '-I', str(PROJECT / 'common'),
                '-I', str(AUX), '-I', str(AUX / 'aspect'), *defines,
                '-c', str(source), '-o', str(obj)]
            result = subprocess.run(command, capture_output=True, text=True)
            (folder / (source.name + '.log')).write_text(result.stdout + result.stderr)
            commands.append(command)
            if result.returncode:
                raise ValueError('CP compilation failed: ' + source.name + '\n' + result.stdout + result.stderr)
            objects.append(obj)
        return objects

    aspect_meta = json.loads((AUX / 'aspect/contract.json').read_text())
    aspect_sources = [AUX / 'aspect' / name for name in (
        'crop_core.c', 'cp_capture_latch.c', 'cp_wrappers.S', 'raw_emb.c', 'aspect_module_dispatch.S')]
    aspect_objects = compile_sources(aspect_sources, out / 'aspect-objects')
    aspect_code, aspect_symbols = link(aspect_objects, base=0x1a3b000, read_only=True)
    assert len(aspect_code) < 4096
    assert hashlib.sha256(aspect_code).hexdigest() == aspect_meta['code_sha256'], 'Preserved aspect module differs'
    assert 0x1a3b000 <= (aspect_symbols['aspect_module_dispatch'] & ~1) < 0x1a3c000
    total_sound_bytes = 4096 + len(aspect_code)
    filter_sources = sorted((PROJECT / 'cp').glob('*.c')) + sorted((PROJECT / 'cp').glob('*.S'))
    assert filter_sources, 'Missing new filter resident sources'
    filter_objects = compile_sources(filter_sources, out / 'filter-objects')
    guard_sources = [AUX / name for name in ('r5_sound_page.S', 'r5_sound_guard_hooks.S', 'r5_sound_gain_guard.S', 'aspect_resident.S')]
    guard_objects = compile_sources(guard_sources, out / 'guard-objects', ['-DR5SS_SOUND_BYTES=' + str(total_sound_bytes)])
    native_externals = dict(aspect_module_dispatch=aspect_symbols['aspect_module_dispatch'],
        od_optional_aspect_freeze=aspect_symbols['aspect_freeze_copy'],
        od_optional_aspect_capture=aspect_symbols['aspect_capture_copy'], native_capture=0x4596f5,
        native_dimensions=0x48b9d9, native_pool_release=0xae08c9, native_raw_exif=0xade83d)
    provisional = dict(r5ss_cp_extended_consume=SOUND | 1, r5ss_cp_completion_hook=SOUND | 1,
        r5ss_cp_gain_hook=SOUND | 1, r5ss_guard_expected_crc_inverse=0xdeadbeef, **native_externals)
    _, initial_symbols = link(filter_objects + guard_objects, base=RX, externals=provisional, read_only=True)
    sound_sources = [AUX / name for name in ('r5_sound_receive.c', 'r5_sound_snapshot.c', 'r5_sound_completion.c',
        'r5_sound_completion_hooks.S', 'r5_sound_completion_state.c', 'r5_sound_gain.c', 'r5_sound_gain_hooks.S')]
    sound_objects = compile_sources(sound_sources, out / 'sound-objects',
        ['-DR5SS_FILTER_CONSUME_ADDRESS=' + hex(initial_symbols['r5_cp_stage413_consume']) + 'u'])
    sound_code, sound_symbols = link(sound_objects, base=SOUND, read_only=True)
    assert sound_symbols['r5ss_cp_extended_consume'] == SOUND | 1 and len(sound_code) == 2240
    stub = (sound_symbols['r5ss_cp_completion_original'] & ~1) - SOUND
    assert sound_code[stub + 4:stub + 8] == bytes.fromhex('dff800f0')
    assert struct.unpack_from('<I', sound_code, stub + 8)[0] == 0x6549e1
    optional_code = sound_code + bytes(4096 - len(sound_code)) + aspect_code
    crc = zlib.crc32(optional_code)
    externals = dict(r5ss_cp_extended_consume=sound_symbols['r5ss_cp_extended_consume'],
        r5ss_cp_completion_hook=sound_symbols['r5ss_cp_completion_hook'],
        r5ss_cp_gain_hook=sound_symbols['r5ss_cp_gain_hook'],
        r5ss_guard_expected_crc_inverse=(~crc) & 0xffffffff, **native_externals)
    audit = {}
    code, symbols = link(filter_objects + guard_objects, base=RX, externals=externals, read_only=True, audit=audit)
    code = bytearray(code)
    stub = (symbols['r5ss_cp_guard_original'] & ~1) - RX
    assert code[stub + 4:stub + 8] == bytes.fromhex('00bf00bf')
    code[stub + 4:stub + 8] = bw(RX + stub + 4, 0x6549e0)
    resident_used = len(code)
    save(out / 'layout.json', dict(resident_used=resident_used, resident_capacity=RX_END-RX,
        optional_bytes=len(optional_code), filter_sources=[str(p) for p in filter_sources]))
    assert resident_used <= RX_END - RX, ('CP resident capacity exceeded', resident_used, RX_END - RX)
    code += bytes(RX_END - RX - resident_used)
    candidate, patches = bytearray(raw), []

    def patch(va, data, reason, expected=None):
        at = va - BASE
        before = raw[at:at + len(data)]
        assert at >= 0 and len(before) == len(data)
        if expected is not None:
            assert before == expected, ('CP before bytes differ', hex(va), before.hex(), expected.hex())
        assert candidate[at:at + len(data)] == before
        assert all(at + len(data) <= row['offset'] or at >= row['offset'] + len(bytes.fromhex(row['after'])) for row in patches)
        candidate[at:at + len(data)] = data
        patches.append(dict(offset=at, va=hex(va), before=before.hex(), after=bytes(data).hex(), reason=reason))

    # Preserve final native map arguments/flags and reserve two immutable RX pages.
    old = trampoline()
    loader = bytearray(old[:-12])
    loader += mov16(0, 0x5000) + mov16(0, 0x119, True) + struct.pack('<III', 0xe1a02000, 0xe3a01a01, 0xe3a0300e)
    loader += branch(0x108f40 + len(loader), 0x108768, True) + old[-12:]
    loader = loader[:-12]
    loader += mov16(0, SOUND & 65535) + mov16(0, SOUND >> 16, True)
    loader += mov16(1, SOUND_SOURCE & 65535) + mov16(1, SOUND_SOURCE >> 16, True) + mov16(2, total_sound_bytes)
    loader += mov16(12, 0x2000) + mov16(12, 0x3e4, True) + struct.pack('<II', 0xe5dcc000, 0xe35c0000)
    sound_nor = 0xd0200000 + SOUND_SOURCE - BASE
    for word in (mov16(1, sound_nor & 65535), mov16(1, sound_nor >> 16, True)):
        loader += struct.pack('<I', (struct.unpack('<I', word)[0] & 0x0fffffff) | 0x10000000)
    copy_loop = 0x108f40 + len(loader)
    loader += struct.pack('<III', 0xe4913004, 0xe4803004, 0xe2522004)
    jump = struct.unpack('<I', branch(0x108f40 + len(loader), copy_loop))[0]
    loader += struct.pack('<I', (jump & 0x0fffffff) | 0x10000000)
    loader += mov16(0, SOUND & 65535) + mov16(0, SOUND >> 16, True) + struct.pack('<III', 0xe1a02000, 0xe3a01a02, 0xe3a0300f)
    loader += branch(0x108f40 + len(loader), 0x108768, True) + old[-12:]
    assert len(loader) <= 0xc0
    patch(0x108f40, loader, 'Final mapper and immutable sound/aspect copy', bytes(len(loader)))
    patch(0x1086d0, branch(0x1086d0, 0x108f40, True), 'Final native mapping detour')
    patch(0x128140, struct.pack('<I', 0x118000), 'Include resident initialized RX padding')
    patch(0x12814c, struct.pack('<I', 0x8a5000), 'Reserve optional pages through1a3c000')
    patch(0x5e3ee8, mov16(3, 0xa000), 'Native clear includes receive owner/state through sound page', mov16(3, 0x9448))
    patch(0x1083ec, mov16(1, 0x3fff), 'Preserve native L1/L2 identity placement', mov16(1, 0x4fff))
    patch(RX, code, 'New on-demand filter and resident guards', bytes(len(code)))
    patch(SOUND_SOURCE, optional_code, 'Immutable sound and aspect copy source', bytes(len(optional_code)))
    patch(0x6549dc, bw(0x6549dc, symbols['r5ss_cp_guard_cleanup'] & ~1), 'Sound cleanup guard', bytes.fromhex('f0b503af'))
    patch(0x1998b8, bw(0x1998b8, symbols['r5ss_cp_guard_gain'] & ~1) + bytes.fromhex('00bf'), 'Owned sound gain guard', bytes.fromhex('28798df80400'))
    for name, row in aspect_meta['hooks'].items():
        if name in ('freeze', 'capture', 'pool_reset'):
            continue  # ownership wrappers call the preserved aspect targets
        va = int(row['VA'], 0)
        patch(va, bl(va, symbols['aspect_resident_dispatch']), 'Aspect ' + name, bytes.fromhex(row['source_bytes']))
    hooks = []
    for filename in ('patches.json','receive_patches.json','grid_patches.json','owner_patches.json'):
        rows = json.loads((PROJECT / 'cp' / filename).read_text())
        hooks.extend(rows['patches'] if isinstance(rows, dict) else rows)
    for row in hooks:
        va = int(row['va'], 0) if isinstance(row['va'], str) else row['va']
        kind = row['kind']
        assert kind in ('b','bl','b_nop','b_nop2','bytes'), ('Unsupported hook encoding', kind)
        if kind == 'bytes':
            data = bytes.fromhex(row['after'])
        else:
            target = symbols[row['target']]
            data = bl(va, target) if kind == 'bl' else bw(va, target & ~1)
            if kind in ('b_nop','b_nop2'):
                data += bytes.fromhex('00bf') * (1 if kind == 'b_nop' else 2)
        patch(va, data, row.get('reason', row.get('target', 'Filter bytes')), bytes.fromhex(row['before']))
    for lo, hi in ((0x413df0,0x4140c0),(0x413d24,0x413d5c),(0x107e968,0x107e968+51*7*4)):
        assert candidate[lo-BASE:hi-BASE] == raw[lo-BASE:hi-BASE], ('Native Gamma metadata or fallback changed', hex(lo))
    reverse = bytearray(candidate)
    for row in reversed(patches):
        before = bytes.fromhex(row['before'])
        reverse[row['offset']:row['offset'] + len(before)] = before
    assert reverse == raw
    # Collapse the declared baseline and final source patches into one audit
    # against the original firmware. Overlapping recipe/final writes are shown
    # by their final bytes, with no intermediate firmware as a build input.
    stock = Path(stock_cp).read_bytes()
    allowed = [(row['offset'], row['offset'] + len(bytes.fromhex(row['after'])))
        for row in recipe('cp_baseline')['patches'] + patches]
    stock_patches = []
    cursor = 0
    while cursor < len(stock):
        if stock[cursor] == candidate[cursor]:
            cursor += 1
            continue
        start = cursor
        while cursor < len(stock) and stock[cursor] != candidate[cursor]:
            assert any(lo <= cursor < hi for lo, hi in allowed), ('Undeclared stock change', cursor)
            cursor += 1
        stock_patches.append(dict(offset=start, before=stock[start:cursor].hex(), after=bytes(candidate[start:cursor]).hex()))
    stock_reverse = bytearray(candidate)
    for row in stock_patches:
        before = bytes.fromhex(row['before'])
        stock_reverse[row['offset']:row['offset'] + len(before)] = before
    assert stock_reverse == stock
    save(out / 'stock-to-final-patches.json', stock_patches)
    target = out / 'cpapp-b.bin'
    target.write_bytes(candidate)
    (out / 'resident.bin').write_bytes(code)
    (out / 'optional.bin').write_bytes(optional_code)
    save(out / 'build.json', dict(passed=True, version='4.65', stock_sha256=sha(stock_cp),
        baseline_sha256=sha(baseline), sha256=sha(target), bytes=len(candidate),
        RX=hex(RX), resident_used=resident_used, resident_capacity=RX_END-RX,
        optional_crc32=hex(crc), optional_bytes=len(optional_code),
        symbols={key:hex(value) for key,value in symbols.items()},
        sound_symbols={key:hex(value) for key,value in sound_symbols.items()},
        aspect_symbols={key:hex(value) for key,value in aspect_symbols.items()},
        patches=patches, compile_commands=commands, link_audit=audit,
        reverse_to_stock_recipe_exact=True, reverse_to_original_stock_exact=True,
        stock_to_final_patch_manifest_sha256=sha(out / 'stock-to-final-patches.json'),
        previous_firmware_input=False, camera_io=False, grid_submission='native-owned-packet-descriptor-synchronous-upload',
        native_grid_permutation='0xe8c1d8', prepared_strength_classes=8,
        prepared_grid_bytes=12960, context_bytes=15352, gamma_ordinates_bytes=516,
        gamma_native_metadata_preserved=True, gamma_outer_unmodified=True,
        gamma_input_owner_offset=12, gamma_wrapper_bytes=24, gamma_wrapper_acquire_bytes=40))
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-cp', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert __debug__
    print(build(args.stock_cp, args.output))
