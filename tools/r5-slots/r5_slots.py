#!/usr/bin/env python3
"""R5 six-slot readback/unlock, with fresh same-body acquisition for every write."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import device
import session
import transport
from filesystem import require
from slots import build_image, diagnostic_snapshot
from sparse import SIZE, make_sparse

HERE = Path(__file__).resolve().parent


def configure(config_path, run):
    require(sys.platform == 'darwin', 'Device commands currently support macOS IOKit only')
    config_path = config_path.expanduser().resolve()
    config = json.loads(config_path.read_text())
    needed = ('bootloader_zip', 'body_partition_table', 'body_bootrom', 'xts_reference_source')
    require(set(config) == set(needed), 'Use the exact config.example.json keys')
    paths = {}
    for key in needed:
        p = Path(config[key]).expanduser()
        paths[key] = (config_path.parent / p).resolve() if not p.is_absolute() else p.resolve()
        require(paths[key].is_file(), 'Missing local input: ' + key)
    require(paths['body_partition_table'].stat().st_size == 65536, 'Expected complete original same-body SDM2')
    require(paths['body_bootrom'].stat().st_size == 49152, 'Expected complete original same-body AP BootROM')
    # The crypto source is supplied by the user, never included in this bundle.
    require(hashlib.sha256(paths['xts_reference_source'].read_bytes()).hexdigest() ==
            'e799ee731d5781ec6d41c998da77eb87c8c0e089df2614669e90f77e58523310', 'Unsupported public upstream XTS reference source')
    host = run.parent / (run.name + '-host-tools')
    host.mkdir(mode=0o700, exist_ok=False)
    for name in ('read_fastboot_usb_all', 'read_fastboot_usb', 'configure_fastboot_usb'):
        subprocess.run(['/usr/bin/clang', '-O2', str(HERE / 'native' / (name + '.c')),
                        '-o', str(host / name), '-framework', 'IOKit', '-framework', 'CoreFoundation'], check=True)
    device.HOST = transport.HOST = host
    device.BOOTLOADER_ZIP = paths['bootloader_zip']
    device.EXPECTED_TABLE = paths['body_partition_table']
    device.EXPECTED_ROM = paths['body_bootrom']
    transport.XTS_REFERENCE = paths['xts_reference_source']
    return paths


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    for action in ('read', 'unlock'):
        a = sub.add_parser(action, help='Fresh device readback' if action == 'read' else 'Fresh read + six-slot repair + full readback')
        a.add_argument('--config', type=Path, required=True)
        a.add_argument('--port', required=True, help='Explicit RP2040 serial port, e.g. /dev/cu.usbmodem1401')
        a.add_argument('--output', type=Path, required=True, help='New private evidence directory; parent must exist')
    a = sub.add_parser('inspect', help='Inspect a saved local 20MiB logical image; no device access')
    a.add_argument('--image', type=Path, required=True)
    a = sub.add_parser('offline', help='Create a local candidate from a saved image; never deployed by this command')
    a.add_argument('--image', type=Path, required=True)
    a.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if not __debug__:
        p.error('python -O is forbidden: integrity assertions must remain enabled')
    os.umask(0o077)
    device.verify_pins()
    if args.action in ('inspect', 'offline'):
        require(args.image.is_file() and not str(args.image.resolve()).startswith('/dev/'), 'Use a saved regular image')
        before = args.image.read_bytes()
        require(len(before) == SIZE, 'Expected full 20MiB logical settings image')
        if args.action == 'inspect':
            print(json.dumps(diagnostic_snapshot(before), ensure_ascii=False, indent=2))
            return
        out = args.output.resolve()
        out.mkdir(mode=0o700, exist_ok=False)
        after, facts = build_image(before)
        require(build_image(after)[0] == after, 'Builder must be idempotent')
        for name, data in [('candidate.logical.img', after), ('patch.sparse.img', make_sparse(before, after)),
                           ('restore.sparse.img', make_sparse(after, before))]:
            (out / name).write_bytes(data)
        facts.update(camera_io=False, deployable_without_new_acquisition=False,
                     scope='Offline candidate only; unlock always starts a new acquisition')
        device.save(out / 'verification.json', facts)
        print(json.dumps(facts, ensure_ascii=False, indent=2))
        return
    run = args.output.resolve()
    require(run.parent.is_dir() and not run.exists(), 'Output parent must exist and output must be new')
    require(Path(args.port).exists(), 'Serial port is not present')
    paths = configure(args.config, run)
    device.ACQUIRE_SLOT_GUARD = args.action == 'unlock'
    try:
        if args.action == 'read':
            device.acquire(run, args.port)
            device.reboot(run)
            state = json.loads((run / 'report.json').read_text())
            state.update(state='readback_verified_reboot_acknowledged', normal_reboot_acknowledged=True,
                         finished_utc=device.utc())
            device.save(run / 'report.json', state)
        else:
            session.run_session(run, args.port)
    finally:
        if run.exists():
            for stage in ('pre', 'post'):
                image = run / (stage + '.settings.logical.img')
                if image.exists() and image.stat().st_size == SIZE:
                    try:
                        facts = diagnostic_snapshot(image.read_bytes())
                    except Exception as exc:
                        facts = dict(diagnostic_error=repr(exc))
                    device.save(run / (stage + '.slots.json'), facts)
            # Local reference identities are useful for recovery; never publish
            # these files, settings images or UART logs with the source bundle.
            device.save(run / 'local-input-identities.json',
                {key: dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                 for key, path in paths.items()})


if __name__ == '__main__':
    main()
