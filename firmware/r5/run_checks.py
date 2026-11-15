#!/usr/bin/env python3
"""Run self-contained host checks against the production AP source.

File I/O, transport, native UI refresh and clock endpoints are explicit host
fixtures. These tests do not execute camera ARM code or reproduce a camera hang.
"""
from pathlib import Path
import argparse
import json
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'build_support'))
from stock_inputs import save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        parser.error('Output must be a new directory')
    out.mkdir(parents=True)
    sources = [HERE / 'ap/tests/runtime.c', HERE / 'ap/r5_filter_runtime.c', HERE / 'ap/job.c']
    command = ['clang', '-std=c11', '-O1', '-g', '-fsanitize=address,undefined', '-Wall', '-Wextra', '-Werror',
        '-Wno-misleading-indentation', '-I', str(HERE / 'ap'), '-I', str(HERE / 'ap/shared'), '-I', str(HERE / 'common'),
        *map(str, sources), '-o', str(out / 'runtime')]
    compiled = subprocess.run(command, capture_output=True, text=True)
    (out / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    modes = []
    for mode in range(15):
        for look in (0, 1, 8, 17, 18):
            run = subprocess.run([str(out / 'runtime'), str(mode), str(look)], capture_output=True, text=True)
            (out / ('runtime-' + str(mode) + '-look-' + str(look) + '.log')).write_text(run.stdout + run.stderr)
            assert run.returncode == 0 and run.stdout.rstrip().endswith('PASS'), run.stdout + run.stderr
            modes.append(dict(mode=mode, initial_look=look, passed=True, output=run.stdout.strip()))
    files = subprocess.run([sys.executable, '-B', str(HERE / 'ap/tests/file.py')], capture_output=True, text=True)
    (out / 'file.log').write_text(files.stdout + files.stderr)
    assert files.returncode == 0, files.stdout + files.stderr
    file_report = json.loads(files.stdout)
    retired = r'\b(?:r5_boot_bank\w*|r5_stage413_transfer\w*|r5_boot_transfer\w*|R5CF_ALLOCATION_BYTES|R5_GRID422_RESTORE\w*|522152)\b'
    audited = []
    for folder in (HERE / 'ap', HERE / 'cp'):
        for path in sorted(folder.rglob('*')):
            if path.suffix not in ('.c', '.h', '.S') or 'tests' in path.parts:
                continue
            assert not re.search(retired, path.read_text()), 'Retired filter flow identifier in ' + str(path)
            audited.append(str(path.relative_to(HERE)))
    report = dict(passed=True, scope='HOST_SOURCE_FIXTURES', camera_arm_code_executed=False,
        camera_io=False, device_acceptance_tested=False, compile_command=command,
        runtime_modes=modes, file_checks=file_report,
        retired_filter_identifier_audit=dict(passed=True, pattern=retired, files=audited,
            boundary='Exact known retired filter identifiers in production AP/CP source only; not a general semantic equivalence proof'),
        source_sha256={str(path.relative_to(HERE)):sha(path) for path in sources + [HERE / 'ap/tests/file.py', HERE / 'ap/r5_filter_file.c']})
    save(out / 'checks.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
