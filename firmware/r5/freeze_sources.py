#!/usr/bin/env python3
"""Write or check this source-only distribution's complete SHA256 lock."""
from pathlib import Path
import argparse
import hashlib
import json

HERE = Path(__file__).resolve().parent
LOCK = HERE / 'sources.lock.json'


def inventory():
    rows = {}
    for path in sorted(HERE.rglob('*')):
        if not path.is_file() or path == LOCK or '__pycache__' in path.parts:
            continue
        if path.is_symlink():
            raise ValueError('Source distribution must not contain symlinks: ' + str(path))
        rows[str(path.relative_to(HERE))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


def check():
    expected = json.loads(LOCK.read_text())
    actual = inventory()
    if actual != expected:
        missing = sorted(expected.keys() - actual.keys())
        extra = sorted(actual.keys() - expected.keys())
        changed = sorted(key for key in actual.keys() & expected.keys() if actual[key] != expected[key])
        raise ValueError('Source lock differs; missing=' + str(missing) + ' extra=' + str(extra) + ' changed=' + str(changed))
    return actual


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Freeze source and classified offline validation receipt')
    args = parser.parse_args()
    if args.write:
        import sys
        sys.path.insert(0, str(HERE / 'build_support'))
        from validation import load_validation
        load_validation(HERE / 'validation.lock.json')
        rows = inventory()
        LOCK.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    else:
        rows = check()
    print(json.dumps(dict(passed=True, source_files=len(rows), written=args.write)))
