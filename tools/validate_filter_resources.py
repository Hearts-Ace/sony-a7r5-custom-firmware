"""Validate current resource pairs and the twelve-filter bundle (stdlib only)."""
from pathlib import Path
import hashlib
import json
import math
import struct
import sys
import zlib


def decode(blob):
    assert blob[:8] == b'R5CUST4\0', 'Expected filter protocol v4'
    version, header, size, count = struct.unpack_from('<4I', blob, 8)
    assert version == 4 and header == 128 and size == len(blob) == 128 + count * 2452
    assert 1 <= count <= 12
    check = bytearray(blob)
    checksum = struct.unpack_from('<I', check, 112)[0]
    struct.pack_into('<I', check, 112, 0)
    assert zlib.crc32(check) == checksum, 'CRC mismatch'
    entries = []
    for index in range(count):
        record = blob[128 + index * 2452:128 + (index + 1) * 2452]
        assert struct.unpack_from('<I', record)[0] == index + 1
        gamma = struct.unpack_from('<129I', record, 716)
        assert gamma[0] == 0 and all(0 <= a <= b <= 131071 for a, b in zip(gamma, gamma[1:])), 'Gamma invalid'
        grid = struct.unpack_from('<1215b', record, 1232)
        assert all(-64 <= value <= 63 for value in grid), 'signed7 grid invalid'
        assert record[2447:] == b'\0' * 5
        entries.append(record)
    return entries


def validate(root):
    ids = {}; names = set(); baseline = None
    paths = list((root / 'filters').glob('*/*.json'))
    assert paths, 'No filters found'
    for binary in (root / 'filters').rglob('*.bin'):
        assert binary.with_suffix('.json').is_file(), f'Missing descriptor: {binary}'
    for path in paths:
        item = json.loads(path.read_text(encoding='utf-8'))
        binary = path.with_suffix('.bin')
        blob = binary.read_bytes(); entries = decode(blob)
        assert len(entries) == 1
        assert item['schema'] == 'r5-filter-description/1'
        assert item['id'] not in ids and item['short_name'] not in names, 'Duplicate ID or menu name'
        assert item['name'] and item['short_name'] == path.stem
        assert hashlib.sha256(blob).hexdigest() == item['sha256'], f'Hash mismatch: {path}'
        assert entries[0][4:28].split(b'\0')[0].decode('utf-8') == item['short_name']
        metrics = item['training_error']
        assert metrics['status'] in ['available', 'pending']
        if metrics['status'] == 'available':
            assert all(isinstance(metrics[k], (int, float)) and math.isfinite(metrics[k]) and metrics[k] >= 0 for k in ['mean', 'p95', 'maximum', 'samples'])
            assert metrics['mean'] <= metrics['maximum'] and metrics['p95'] <= metrics['maximum']
            assert metrics['protocol'] and metrics['label']
        if baseline is None: baseline = blob[32:112]
        assert baseline == blob[32:112], 'Mixed camera baselines'
        if item.get('preview'):
            preview = Path(item['preview'])
            assert not preview.is_absolute() and '..' not in preview.parts and preview.parts[0] == 'filters'
            assert (root / preview).is_file()
        ids[item['id']] = entries[0]; names.add(item['short_name'])
    path = root / 'filter-bundles/常用十二款.json'
    item = json.loads(path.read_text(encoding='utf-8'))
    blob = path.with_suffix('.bin').read_bytes()
    entries = decode(blob)
    assert item['schema'] == 'r5-filter-bundle/1' and len(item['filters']) == len(entries) == 12
    assert len(set(item['filters'])) == 12
    assert hashlib.sha256(blob).hexdigest() == item['sha256'] and baseline == blob[32:112]
    for name, record in zip(item['filters'], entries):
        assert record[4:] == ids[name][4:], f'Bundle differs from current single filter: {name}'
    info = json.loads((root / 'resource-info/simulation-error.json').read_text(encoding='utf-8'))
    assert info['schema'] == 'r5-simulation-error/1'
    assert all(math.isfinite(info[k]) and info[k] >= 0 for k in ['mean', 'p95', 'maximum', 'samples'])
    assert isinstance(info['scope'], str) and info['scope'].strip()
    print(f'Validated {len(ids)} current filters and twelve-filter bundle')


if __name__ == '__main__':
    validate(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1])
