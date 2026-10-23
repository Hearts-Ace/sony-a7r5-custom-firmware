#!/usr/bin/env python3
"""Run the existing offline 4.23 codec, sidecar and runtime host fixtures."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
IMPORT = HERE.parent / 'import'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    subprocess.run([sys.executable, str(HERE / 'test_codec.py')], check=True)
    plans = (
        ('selection_store', ('r5_filter_selection423.c',), (((), 'selection_store_test'),)),
        ('runtime', ('r5_filter_runtime423.c', 'r5_filter_names423.c',
                     'r5_filter_selection423.c', 'r5_runtime_session.c',
                     'r5_stage410_codec.c'),
         (((), 'runtime_test'), (('restore',), 'runtime_restore_test'))),
    )
    for fixture, names, runs in plans:
        sources = [IMPORT / name for name in names]
        executable = HERE / ('test_' + fixture)
        command = ['clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                   '-I', str(IMPORT), str(HERE / ('test_' + fixture + '.c')),
                   *map(str, sources), '-o', str(executable)]
        subprocess.run(command, check=True)
        for arguments, report_name in runs:
            result = subprocess.run([str(executable), *arguments], check=True,
                                    capture_output=True, text=True)
            report = json.loads(result.stdout)
            report['compiler'] = command
            report['production_source_sha256'] = {
                str(path.relative_to(ROOT)): sha(path) for path in sources
            }
            (HERE / (report_name + '.json')).write_text(
                json.dumps(report, indent=2) + '\n')
            print(result.stdout.strip())
    sources = [*HERE.glob('source/*.c'), *HERE.glob('source/*.h'),
               *HERE.glob('test_*.c'), HERE / 'test_codec.py', Path(__file__)]
    production = [IMPORT / name for name in (
        'r5_filter_runtime423.c', 'r5_filter_names423.c',
        'r5_filter_selection423.c', 'r5_runtime_session.c',
        'r5_stage410_codec.c')]
    report = dict(scope='4.23 AP source and existing offline host fixtures',
                  camera_io=False,
                  sha256={str(path.relative_to(ROOT)): sha(path)
                          for path in sorted(set(sources + production))})
    (HERE / 'host_source_manifest.json').write_text(
        json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
