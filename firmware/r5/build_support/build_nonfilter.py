#!/usr/bin/env python3
"""Rebuild the retained AVCAM/MPR/aspect resources from original inputs."""
from pathlib import Path
import argparse
import importlib.util
import json
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / 'lib'), str(HERE / 'vendor')]
from a7r5dat.ext2_patch import reader
from a7r5dat.fat import FatImage
from stock_inputs import load_inputs, save, sha


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert __debug__
    config = load_inputs(args.inputs)
    out = args.output.resolve()
    if out.exists():
        parser.error('Output must be a new directory')
    out.mkdir(parents=True)
    with tarfile.open(config['original_tar'], 'r:') as archive:
        raw = archive.extractfile('0700_part_image/dev/nflasha3').read()
    avcam = FatImage(raw).read('/av-cam.bin')
    del raw
    av = module('owner_submit465_avcam', HERE / 'nonfilter/avcam_patch.py')
    av_report = av.patch_avcam(avcam, out / 'avcam')
    assert av_report['sha256'] == 'c83007a07a4058e63e9e984210642f18c74fbd555dcf8379001b0493b899af6b'
    fs = reader(config['stock_nflasha15'].read_bytes())
    mpr = fs.read_inode(fs.walk('/lib/libmpr.so'))
    mp = module('owner_submit465_mpr', HERE / 'nonfilter/mpr_patch.py')
    mp_report = mp.patch_mpr(mpr, out / 'mpr')
    assert mp_report['sha256'] == '81a97ba5ac2456077485fefa5eeaea441ae595f46e5edf8d3d8b7b7559ec1478'
    inputs = out / 'resource-inputs'
    inputs.mkdir()
    manifest = json.loads((HERE / 'resources/inputs.json').read_text())
    for row in manifest['resource_files']:
        raw = fs.read_inode(fs.walk('/share/app/' + row['name']))
        target = inputs / row['name']
        target.write_bytes(raw)
        assert len(raw) == row['bytes'] and sha(target) == row['sha256']
    del fs
    command = [sys.executable, '-B', str(HERE / 'resources/build_resources.py'),
        '--input-root', str(inputs), '--output', str(out / 'resources')]
    compiled = subprocess.run(command, capture_output=True, text=True)
    (out / 'resources.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    resource_sha = sha(out / 'resources/manifest.json')
    assert resource_sha == '97d53cc175b07ee72517b1e9e9a45f57d68cd9e6d4bd8370945608b501ed5c27'
    report = dict(passed=True, version='4.65', camera_io=False,
        AVCAM=av_report['sha256'], MPR=mp_report['sha256'],
        resource_manifest_sha256=resource_sha,
        previous_custom_firmware_input=False)
    save(out / 'build.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
