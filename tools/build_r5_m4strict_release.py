#!/usr/bin/env python3
"""Reproduce the author-method R5 4.03 or 4.04 package using offline tools only.

Builds AP, CP and WBI from original files, records verification receipts, then
packages with the untouched R5 updater. Does not deploy personal settings,
connect to a camera, copy to removable media or execute extracted firmware.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '086df3b1e33dfa0206553ac2bb003535c58ddb80'
STEPS = [('ap', 'build_r5_m4strict_ap.py', 'appFw.so'),
         ('cp', 'build_r5_m4strict_cp.py', 'cpapp-b.bin'),
         ('wbi', 'build_r5_m4strict_wbi.py', 'nflasha5')]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 << 20), b''):
            h.update(block)
    return h.hexdigest()


def receipts(build):
    components, evidence = {}, {}
    for kind, script, name in STEPS:
        folder = build / 'evidence' / kind
        manifest = json.loads((folder / 'manifest.json').read_text())
        verification = json.loads((folder / 'verification.json').read_text())
        require(verification['passed'] is True, kind + ' verification is incomplete')
        actual = digest_file(build / 'patched' / name)
        require(actual == manifest['output_sha256'] == verification['output_sha256'],
                kind + ' component and verification identities disagree')
        if kind == 'ap':
            require(verification['only_five_upstream_patch_groups'] and
                    verification['no_old_slotfix_input'] and
                    verification['all_original_initializers_writers_defaults_unchanged'],
                    'AP retains changes outside the author recipe')
        if kind == 'cp':
            reference_path = folder / 'reference-verification.json'
            reference = json.loads(reference_path.read_text())
            require(reference['passed'] is True and reference['output_sha256'] == actual and
                    reference['author_recipe_exact_reproduction'] is True and
                    reference['four_embedded_coefficient_rows_equal_author'] is True,
                    'CP author comparison is incomplete or has a different identity')
            require(verification['gamma_included'] is True and
                    verification['selectors_and_readers']['alternate_reader_byte_identical_to_stock'] is True,
                    'CP required gamma or restoration checks are missing')
            evidence[str(reference_path.relative_to(build / 'evidence'))] = digest_file(reference_path)
        if kind == 'wbi':
            original = ROOT / 'unpacked/r5/firmware/0700_part_image/dev/nflasha5'
            with original.open('rb') as before, (build / 'patched' / name).open('rb') as after:
                require(before.read(4) == b'WBI2' and after.read(4) == b'WBI3',
                        'WBI change must match the author marker exactly')
                while True:
                    chunk = before.read(4 << 20)
                    require(after.read(len(chunk)) == chunk, 'Unexpected WBI payload modification')
                    if not chunk:
                        require(not after.read(1), 'WBI output has extra bytes')
                        break
        components[name] = {'sha256': actual, 'builder': script,
                            'manifest': kind + '/manifest.json',
                            'verification': kind + '/verification.json'}
        for path in (folder / 'manifest.json', folder / 'verification.json'):
            evidence[str(path.relative_to(build / 'evidence'))] = digest_file(path)
    result = {'upstream_commit': COMMIT, 'offline_component_checks_passed': True,
              'components': components, 'evidence_sha256': evidence,
              'camera_io': False, 'personal_settings_embedded': False,
              'verification_scope': 'Static/host verification only; not device acceptance'}
    (build / 'evidence/component_inputs.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def run_step(build, script, *args):
    log = build / 'evidence' / (Path(script).stem + '.log')
    print('Running offline step: ' + script, flush=True)
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT / 'vendor/audit-python'), str(ROOT / 'tools')))
    with log.open('x') as output:
        p = subprocess.run([sys.executable, str(ROOT / 'tools' / script),
                            '--build', str(build), *args],
                           cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)
    require(p.returncode == 0, 'Build step failed; inspect ' + str(log))


def source_snapshot(build):
    """Archive build/verification sources, including local Python dependencies.

    This is an audit snapshot; reproduction runs from the original workspace
    so the fixed official inputs, vendor libraries and signing identity resolve.
    Neither firmware inputs nor private keys are copied into this snapshot.
    """
    pending = list((ROOT / 'tools').glob('*m4strict*.py'))
    files = set()
    while pending:
        path = pending.pop()
        if path in files:
            continue
        files.add(path)
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            modules = ([node.module] if isinstance(node, ast.ImportFrom) and node.module
                       else [n.name for n in node.names] if isinstance(node, ast.Import) else [])
            for module in modules:
                local = ROOT / 'tools' / (module.split('.')[0] + '.py')
                if local.is_file() and local not in files:
                    pending.append(local)
    upstream = ROOT / 'analysis/erlla_a7m4_comparison_20261015/upstream/Erlla-sony-a7m4-custom-firmware-086df3b'
    for name in ('a7m4/fl23.py', 'a7m4/firmware.py', 'a7m4/patching.py',
                 'a7m4/fat.py', 'a7m4/common.py', 'a7m4/offline.py',
                 'a7m4/profiles/fl23/ap-recipe.json', 'a7m4/profiles/fl23/cp-v7-recipe.json',
                 'methods/03-fl2-fl3/README.md'):
        files.add(upstream / name)
    records = []
    for path in sorted(files):
        require(path.is_file(), 'Source dependency missing: ' + str(path))
        relative = path.relative_to(ROOT)
        dst = build / 'source' / relative
        require(not dst.exists(), 'Source snapshot already exists: ' + str(dst))
        dst.parent.mkdir(parents=True, exist_ok=True)
        raw = path.read_bytes()
        dst.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        require(digest_file(dst) == digest, 'Source snapshot mismatch')
        records.append({'workspace_path': str(relative), 'snapshot': str(dst.relative_to(build)),
                        'sha256': digest})
    (build / 'evidence/source_snapshot.json').write_text(json.dumps(
        {'files': records, 'private_key_exported': False, 'upstream_commit': COMMIT}, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True,
                        help='A new output directory; existing builds are preserved')
    parser.add_argument('--version', choices=['4.03', '4.04'], default='4.03')
    parser.add_argument('--verified-components-only', action='store_true',
                        help='Use existing independently built components and receipts, then package')
    args = parser.parse_args()
    build = args.build.resolve()
    if args.verified_components_only:
        require(build.is_dir(), 'Existing component build directory is required')
        require(not (build / 'BODYDATA.DAT').exists(), 'A finished package already exists')
    else:
        require(not build.exists(), 'Choose a new output directory')
        (build / 'evidence').mkdir(parents=True)
        for _, script, _ in STEPS:
            run_step(build, script)
    receipts(build)
    run_step(build, 'build_r5_m4strict403.py', '--version', args.version)
    source_snapshot(build)
    result = json.loads((build / 'verification.json').read_text())
    print(json.dumps({key: result[key] for key in
                      ('state', 'output', 'output_bytes', 'output_sha256')}, indent=2))


if __name__ == '__main__':
    main()
