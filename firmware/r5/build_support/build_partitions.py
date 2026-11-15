#!/usr/bin/env python3
"""Integrate final components into new stock-derived partitions, offline only.

The AP, MPR and resources are replaced together in the reviewed original
filesystem layout. No 4.55 or 4.59 output, filter bank or previous partition is
built or consumed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / 'vendor'), str(HERE / 'lib')]
from a7r5dat.ext2_patch import reader
from a7r5dat.fat import FatImage
from partition_support import patch_partition, verify_lut_layout
from stock_inputs import apply_recipe, identity, load_inputs, save, sha


def fat_replace(raw, name, content):
    """Retain the original chain and all bytes outside this file and its size."""
    fs = FatImage(raw)
    entry = fs.entries[name.casefold()]
    allocated = sum(size for _, size in entry['extents'])
    if entry['is_directory'] or not entry['size'] <= len(content) <= allocated:
        raise ValueError('FAT component exceeds its existing allocation')
    data, used, position = bytearray(raw), [], 0
    for at, size in entry['extents']:
        take = min(size, len(content) - position)
        if take <= 0:
            break
        data[at:at + take] = content[position:position + take]
        used.append((at, take))
        position += take
    if position != len(content):
        raise ValueError('Incomplete FAT component')
    size_at = entry['directory_entry_offset'] + 28
    struct.pack_into('<I', data, size_at, len(content))
    result = FatImage(data)
    assert result.read(name) == content
    assert result.entries[name.casefold()]['extents'] == entry['extents']
    reverse = bytearray(data)
    for at, size in used:
        reverse[at:at + size] = raw[at:at + size]
    reverse[size_at:size_at + 4] = raw[size_at:size_at + 4]
    assert reverse == raw
    assert result.entries.keys() == fs.entries.keys()
    for key, row in fs.entries.items():
        if key != name.casefold():
            assert result.entries[key] == row
            if not row['is_directory']:
                assert result.read(key) == fs.read(key)
    return bytes(data), dict(passed=True, path=name, allocated_bytes=allocated,
        old_file_bytes=entry['size'], new_file_bytes=len(content),
        allocation_chain_unchanged=True, reverse_unchanged_outside_target=True,
        source_sha256=hashlib.sha256(raw).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--e2fsck', type=Path, default=Path('/opt/homebrew/opt/e2fsprogs/sbin/e2fsck'))
    for name in ('ap', 'cp', 'avcam', 'mpr', 'resources'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    assert __debug__, 'Do not run with python -O'
    config = load_inputs(args.inputs)
    out = args.output.resolve()
    if out.exists():
        parser.error('Output must be a new directory')
    components = {name.upper(): getattr(args, name).resolve() for name in ('ap', 'cp', 'avcam', 'mpr')}
    resources = json.loads((args.resources / 'manifest.json').read_text())
    assert resources['passed'] and resources['file_count'] == 70
    assert resources['text_runtime_ids'] == [hex(v) for v in range(0x0200ab4c, 0x0200ab50)]
    out.mkdir(parents=True)
    parts, evidence = out / 'partitions', out / 'evidence'
    parts.mkdir()
    evidence.mkdir()
    layout = out / 'nflasha15.layout'
    layout_receipt = apply_recipe(config['stock_nflasha15'], layout, 'nflasha15_layout')
    before = layout.read_bytes()
    assert hashlib.sha256(before).hexdigest() == layout_receipt['sha256']
    layout.unlink()  # Reproducible temporary layout, already verified and held in memory.
    fs = reader(before)
    replacements = {path: (fs.read_inode(fs.walk(path)), components[key].read_bytes())
        for path, key in (('/lib/appFw.so', 'AP'), ('/lib/libmpr.so', 'MPR'))}
    for row in resources['files']:
        path = '/share/app/' + row['name']
        original = fs.read_inode(fs.walk(path))
        target = args.resources / row['name']
        assert sha(target) == row['output_sha256']
        assert hashlib.sha256(original).hexdigest() == row['input_sha256']
        replacements[path] = original, target.read_bytes()
    after, receipt = patch_partition(before, replacements)
    (parts / 'nflasha15').write_bytes(after)
    receipt.update(layout=verify_lut_layout(after, True), stock_layout_recipe=layout_receipt)
    del fs, before, after, replacements
    checked = subprocess.run([str(args.e2fsck), '-fn', str(parts / 'nflasha15')], capture_output=True, text=True)
    (evidence / 'nflasha15.e2fsck.log').write_text(checked.stdout + checked.stderr)
    assert checked.returncode == 0, 'Derived ext2 failed read-only e2fsck'
    receipt['e2fsck_readonly_passed'] = True
    save(evidence / 'nflasha15.json', receipt)
    with tarfile.open(config['original_tar'], 'r:') as archive:
        raw_n3 = archive.extractfile('0700_part_image/dev/nflasha3').read()
    for part, raw, name, key in (
        ('nflasha3', raw_n3, '/av-cam.bin', 'AVCAM'),
        ('nflasha8', config['stock_nflasha8'].read_bytes(), '/cpapp-b.bin', 'CP')):
        payload, receipt = fat_replace(raw, name, components[key].read_bytes())
        target = parts / part
        target.write_bytes(payload)
        receipt.update(identity(target))
        save(evidence / (part + '.json'), receipt)
    apply_recipe(config['stock_nflasha5'], parts / 'nflasha5', 'nflasha5')
    report = dict(passed=True, version='4.65', camera_io=False,
        source='Original R5 4.00 plus declared component/layout patches',
        previous_custom_firmware_input=False,
        components={key: identity(path) for key, path in components.items()},
        resources=70, resource_manifest_sha256=sha(args.resources / 'manifest.json'),
        partitions={path.name: identity(path) for path in parts.iterdir()},
        ratios=['809/500', '239/100', '5/4', '37/20'], menu_order=[0, 4, 1, 6, 2, 7, 5, 3],
        device_acceptance_tested=False)
    save(out / 'build.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
