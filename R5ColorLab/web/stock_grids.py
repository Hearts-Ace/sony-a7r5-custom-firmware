"""Verified factory grids, independent of any installed firmware/image at runtime."""
from pathlib import Path
import copy
import hashlib
import json

CATALOG_PATH = Path(__file__).resolve().parent / 'data' / 'stock_grids423.json'
CATALOG_SHA256 = 'dda8140f032181e86f59124f835695426cd2b18a83461982204786dd8a2cb0a5'


def catalog():
    """Return only verified v4-compatible factory 5x9x9 options; fail closed."""
    raw = CATALOG_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CATALOG_SHA256:
        raise ValueError('原厂网格目录身份校验失败')
    value = json.loads(raw)
    if value.get('schema') != 'r5-stock-grid-catalog/1':
        raise ValueError('原厂网格目录格式错误')
    entries = value['entries']
    ids = set()
    for entry in entries:
        if entry['id'] in ids:
            raise ValueError('原厂网格编号重复')
        ids.add(entry['id'])
        grid = entry['grid_5x9x9']
        if set(grid) != {'coefficients'}:
            raise ValueError('原厂网格结构错误')
        planes = grid['coefficients']
        if len(planes) != 3 or any(len(p) != 5 for p in planes):
            raise ValueError('原厂网格尺寸错误')
        if any(len(y) != 9 or any(len(row) != 9 for row in y) for p in planes for y in p):
            raise ValueError('原厂网格尺寸错误')
        values = [v for p in planes for y in p for row in y for v in row]
        if any(type(v) is not int or not -64 <= v <= 63 for v in values):
            raise ValueError('原厂网格系数超出 v4 范围')
        raw_coefficients = bytes(v & 255 for v in values)
        if hashlib.sha256(raw_coefficients).hexdigest() != entry['provenance']['raw_sha256']:
            raise ValueError('原厂网格系数散列错误')
    return copy.deepcopy(entries)
