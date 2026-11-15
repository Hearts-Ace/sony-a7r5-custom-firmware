"""Validate immutable R5 inputs and apply a declared stock-to-component recipe.

No previous custom firmware is an input. The baseline recipe contains the
existing FL2/FL3 and filter mount/layout changes, not the retired
custom-filter bank or its loader.
"""
from pathlib import Path
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda: f.read(4 << 20), b''):
            h.update(data)
    return h.hexdigest()


def identity(path):
    path = Path(path)
    return dict(bytes=path.stat().st_size, sha256=sha(path))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def load_inputs(path, *, signing=False):
    values = json.loads(Path(path).read_text())
    paths = {key: Path(value).expanduser().resolve() for key, value in values.items()}
    locked = json.loads((HERE / 'inputs.lock.json').read_text())
    for key, expected in locked.items():
        actual = paths.get(key)
        if actual is None or not actual.is_file() or identity(actual) != expected:
            raise ValueError('Wrong or unavailable immutable input: ' + key)
    if signing:
        private = paths['private_key']
        if not private.is_file() or private.stat().st_mode & 0o777 != 0o600:
            raise ValueError('Signing private key must exist with mode 0600')
    return paths


def recipe(name):
    return json.loads((HERE / 'dependencies/baseline_recipes.json').read_text())[name]


def apply_recipe(source, target, name):
    """Apply nonoverlapping before-byte patches to a separate derived output."""
    source, target = Path(source), Path(target)
    spec = recipe(name)
    if target.exists() or source.resolve() == target.resolve():
        raise ValueError('Derived output must be a new separate file')
    if source.stat().st_size != spec['bytes'] or sha(source) != spec['source_sha256']:
        raise ValueError('Wrong stock source for ' + name)
    ranges = []
    for row in spec['patches']:
        before, after = bytes.fromhex(row['before']), bytes.fromhex(row['after'])
        lo, hi = row['offset'], row['offset'] + len(before)
        if len(before) != len(after) or not 0 <= lo <= hi <= spec['bytes']:
            raise ValueError('Invalid patch geometry')
        if any(lo < b and a < hi for a, b in ranges):
            raise ValueError('Overlapping stock patches')
        ranges.append((lo, hi))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    try:
        with target.open('r+b') as stream:
            for row in spec['patches']:
                before, after = bytes.fromhex(row['before']), bytes.fromhex(row['after'])
                stream.seek(row['offset'])
                if stream.read(len(before)) != before:
                    raise ValueError('Stock preimage differs: ' + name)
                stream.seek(row['offset'])
                stream.write(after)
        if sha(target) != spec['target_sha256']:
            raise ValueError('Derived stock recipe identity differs: ' + name)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return dict(recipe=name, patches=len(spec['patches']), **identity(target))
