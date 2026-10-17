#!/usr/bin/env python3
"""Inspect Git-tracked publication files, without reading camera data or devices."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    forbidden = {'.dat', '.img', '.bin', '.pem', '.key', '.uf2', '.zip', '.arw', '.jpg'}
    secret = re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}')
    errors = []
    count = 0
    for name in filter(None, paths):
        p = ROOT / name
        if p.is_symlink() or p.suffix.lower() in forbidden or p.stat().st_size > 2_000_000:
            errors.append(name + ': forbidden type, link or size')
            continue
        text = p.read_text()
        if secret.search(text):
            errors.append(name + ': possible credential')
        if p.suffix == '.py':
            ast.parse(text, filename=name)
        count += 1
    for item in json.loads((ROOT / 'SOURCE_MANIFEST.json').read_text())['sources']:
        if hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest() != item['public_sha256']:
            errors.append(item['path'] + ': source manifest mismatch')
    deploy = ast.parse((ROOT / 'tools/deploy_r5_m4strict_personal.py').read_text())
    pins = next(ast.literal_eval(n.value) for n in deploy.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'PINS' for t in n.targets))
    for name, expected in pins.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            errors.append(name + ': deployment source pin mismatch')
    print(json.dumps({'tracked_files_checked': count, 'errors': errors}, ensure_ascii=False))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
