#!/usr/bin/env python3
"""Offline-only compatibility checks using a private fixture supplied locally."""
import argparse
import ast
import json
from pathlib import Path
import struct
import subprocess
import tempfile

import device
from filesystem import FatImage, require
from slots import SLOTS, banks, build_image
from sparse import SIZE, apply_sparse, make_sparse
import transport


def rejected(image, expected):
    try:
        build_image(image)
    except ValueError as exc:
        require(expected in str(exc), 'Unexpected rejection reason: ' + str(exc))
    else:
        raise AssertionError('Invalid input accepted')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image', type=Path, required=True)
    p.add_argument('--expected', type=Path, help='Previously independently verified local target')
    p.add_argument('--raw', type=Path)
    p.add_argument('--xts-reference', type=Path)
    p.add_argument('--compile-native', action='store_true')
    a = p.parse_args()
    device.verify_pins()
    before = a.image.read_bytes()
    require(len(before) == SIZE, 'Need complete local logical image')
    after, facts = build_image(before)
    if a.expected:
        require(after == a.expected.read_bytes(), 'Public adaptation differs from independently verified target')
    require(build_image(after)[0] == after, 'Repeated patch changed already-correct image')
    require(apply_sparse(before, make_sparse(before, after))[0] == after, 'Forward sparse mismatch')
    require(apply_sparse(after, make_sparse(after, before))[0] == before, 'Reverse sparse mismatch')
    device.audit_candidate(before, after)
    fs = FatImage(before)
    raw = bytearray(fs.read('/backup.bin'))
    raw[0xEF020] ^= 1
    bad = bytearray(before)
    fs.patch(bad, '/backup.bin', bytes(raw))
    rejected(bytes(bad), 'checksum')
    raw = bytearray(fs.read('/backup.bin'))
    bank = banks(raw)[0]
    raw[bank.property(next(iter(SLOTS))).file_offset] = 3
    struct.pack_into('<I', raw, 0x20, sum(raw[:0x20]) + sum(raw[0x24:bank.size]))
    bad = bytearray(before)
    fs.patch(bad, '/backup.bin', bytes(raw))
    rejected(bytes(bad), 'Unexpected LOOK')
    native = []
    if a.compile_native:
        with tempfile.TemporaryDirectory(prefix='r5-slots-native-') as directory:
            for source in sorted((Path(__file__).parent / 'native').glob('*.c')):
                subprocess.run(['/usr/bin/clang', '-O2', str(source), '-o', str(Path(directory) / source.stem),
                                '-framework', 'IOKit', '-framework', 'CoreFoundation'], check=True,
                               capture_output=True)
                native.append(source.name)
    raw_verified = False
    if a.raw or a.xts_reference:
        require(a.raw and a.xts_reference, 'Both raw and XTS reference are required')
        transport.XTS_REFERENCE = a.xts_reference
        transport.raw_verify(a.raw.read_bytes(), before)
        raw_verified = True
    for source in Path(__file__).parent.glob('*.py'):
        ast.parse(source.read_text())
    print(json.dumps(dict(passed=True, camera_io=False, independently_verified_target_equal=bool(a.expected),
        native_compiled=native, all_40960_raw_sectors_verified=raw_verified,
        checks=['all source pins', 'exact target identity', 'already-correct idempotency',
                'forward and reverse sparse', 'whole-partition change allowlist',
                'bad second-bank checksum rejected', 'unknown LOOK rejected'],
        changed_bytes=facts['changed_bytes'], changed_sectors=facts['changed_sectors']), indent=2))


if __name__ == '__main__':
    main()
