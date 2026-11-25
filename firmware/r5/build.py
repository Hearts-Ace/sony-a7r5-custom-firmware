#!/usr/bin/env python3
"""Build R5 4.67 from immutable original inputs and the locked current source.

No camera, SD-card, USB, deployment or network operation exists here. The all
stage requires a reviewed or explicitly unverified offline candidate receipt
bound to all four exact component identities. It signs locally only after reproducing those components.
"""
from pathlib import Path
import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
SUPPORT = HERE / 'build_support'
sys.path[:0] = [str(SUPPORT), str(HERE)]
from stock_inputs import identity, load_inputs, save, sha
from freeze_sources import check
from validation import load_validation, match_components


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', choices=('components', 'all'), default='components')
    parser.add_argument('--e2fsck', type=Path)
    parser.add_argument('--reference-dat', type=Path, help='Compare independently regenerated package to this read-only DAT without writing a second copy')
    args = parser.parse_args()
    assert __debug__, 'Do not disable integrity assertions with -O'
    if args.reference_dat and args.stage != 'all':
        parser.error('--reference-dat requires --stage all')
    lock = check()
    config_path = args.inputs.expanduser().resolve()
    paths = load_inputs(config_path, signing=args.stage == 'all')
    out = args.output.expanduser().resolve()
    if out.exists() or out == HERE or out.is_relative_to(HERE) or HERE.is_relative_to(out):
        parser.error('Output must be a new directory outside the source distribution')
    compiler = shutil.which('clang')
    assert compiler, 'clang is required'
    checker = args.e2fsck.expanduser().resolve() if args.e2fsck else Path(shutil.which('e2fsck') or '/opt/homebrew/opt/e2fsprogs/sbin/e2fsck')
    assert checker.is_file(), 'e2fsck is required'
    required = ('elftools', 'capstone', 'Cryptodome')
    if args.stage == 'all':
        required += ('numpy', 'cryptography')
    packages = {name: importlib.import_module(name) for name in required}
    validation = None
    if args.stage == 'all':
        validation = load_validation(HERE / 'validation.lock.json')
    out.mkdir(parents=True)
    logs = out / 'logs'
    logs.mkdir()
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    if env.get('PYTHONPATH'):
        env['PYTHONPATH'] = os.pathsep.join(str(Path(item or '.').resolve()) for item in env['PYTHONPATH'].split(os.pathsep))
    commands = []
    save(out / 'host-environment.json', dict(python=sys.version, executable=sys.executable,
        compiler=compiler, compiler_version=subprocess.run([compiler, '--version'], capture_output=True, text=True, check=True).stdout,
        e2fsck=str(checker), packages={name:dict(path=module.__file__, version=getattr(module, '__version__', None)) for name,module in packages.items()}))

    def run(label, script, *arguments):
        command = [sys.executable, '-B', str(script), *map(str, arguments)]
        log = logs / (label + '.log')
        started = time.monotonic()
        print(label, flush=True)
        with log.open('w') as stream:
            result = subprocess.run(command, cwd=HERE, env=env, stdout=stream, stderr=subprocess.STDOUT)
        commands.append(dict(stage=label, command=command, exit_code=result.returncode,
            seconds=round(time.monotonic() - started, 3), log=str(log.relative_to(out)), log_sha256=sha(log)))
        save(out / 'commands.json', commands)
        if result.returncode:
            print(log.read_text()[-6000:], file=sys.stderr)
            raise RuntimeError('Build stage failed: ' + label + '; see ' + str(log))

    ap, cp, retained = out / 'ap', out / 'cp', out / 'retained'
    run('00-host-checks', HERE / 'run_checks.py', '--output', out / 'host-checks')
    run('01-ap', HERE / 'ap/build_ap.py', '--stock-ap', paths['stock_ap'], '--output', ap)
    run('02-cp', SUPPORT / 'build_cp.py', '--stock-cp', paths['stock_cp'], '--output', cp)
    run('03-retained-features', SUPPORT / 'build_nonfilter.py', '--inputs', config_path, '--output', retained)
    components = dict(AP=ap / 'appFw.so', CP=cp / 'cpapp-b.bin',
        AVCAM=retained / 'avcam/av-cam.bin', MPR=retained / 'mpr/libmpr.so')
    actual = {key:identity(path) for key,path in components.items()}
    if validation:
        match_components(validation, actual)
    partitions = out / 'partitions-build'
    run('04-partitions', SUPPORT / 'build_partitions.py', '--inputs', config_path, '--output', partitions,
        '--e2fsck', checker, '--ap', components['AP'], '--cp', components['CP'],
        '--avcam', components['AVCAM'], '--mpr', components['MPR'], '--resources', retained / 'resources')
    package_path = None
    if args.stage == 'all':
        package_path = out / 'package'
        package_args = ['--inputs', config_path, '--build', partitions, '--output', package_path]
        if args.reference_dat:
            package_args += ['--reference-dat', args.reference_dat.expanduser().resolve()]
        run('05-package', SUPPORT / 'package_firmware.py', *package_args)
    check()  # All build intermediates must remain outside the source tree.
    report = dict(passed=True, version='4.67', stage=args.stage,
        source_lock_sha256=sha(HERE / 'sources.lock.json'), source_files=len(lock),
        components={key:dict(path=str(path.relative_to(out)), **actual[key]) for key,path in components.items()},
        partition_manifest=str((partitions / 'build.json').relative_to(out)),
        package=(dict(path=str(args.reference_dat.expanduser().resolve()), reference_stream_compared=True, **identity(args.reference_dat)) if args.reference_dat else dict(path=str((package_path / 'BODYDATA.DAT').relative_to(out)), **identity(package_path / 'BODYDATA.DAT'))) if package_path else None,
        validation_receipt_sha256=sha(HERE / 'validation.lock.json') if validation else None,
        release_status=validation.get('release_status', 'reviewed_offline') if validation else None,
        open_owner_boundaries=[k for k,v in validation['owner_handoff'].items() if not v['passed']] if validation else [],
        previous_custom_firmware_input=False, camera_io=False, device_acceptance_tested=False)
    save(out / 'build-result.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
