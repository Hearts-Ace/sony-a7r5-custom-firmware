"""Validate the public C2 and M4 downloads against their R5 source filters."""
import base64
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/m4-adapter'))
from convert import codec, validate as validate_m4

def load(path):
    return json.loads(path.read_bytes())

def sha(data):
    return hashlib.sha256(data).hexdigest()

def validate_library(model, extension, fmt, template):
    directory = ROOT/f'{model}-filters'
    metadata_paths = set(directory.glob('*/*.meta.json'))
    payload_paths = {
        path for path in directory.glob(f'*/*{extension}') if not path.name.endswith('.meta.json')
    }
    assert metadata_paths
    assert payload_paths == {p.with_name(p.name[:-10]+extension) for p in metadata_paths}
    names = set()
    ids = set()
    for meta_path in sorted(metadata_paths):
        path = ROOT/'filters'/meta_path.parent.name/(meta_path.name[:-10]+'.json')
        source = load(path)
        r5_bin = path.with_suffix('.bin').read_bytes()
        assert sha(r5_bin) == source['sha256']
        config = codec.unpack(r5_bin)
        assert len(config['entries']) == 1
        entry = config['entries'][0]
        grid = entry['grid_5x9x9']['coefficients']
        stem = path.stem
        meta = load(meta_path)
        blob = (directory/path.parent.name/f'{stem}{extension}').read_bytes()
        doc = json.loads(blob)
        assert meta['schema'] == 'sony-single-filter-download/1'
        assert meta['model'] == model and meta['format'] == fmt
        assert meta['short_name'] == entry['short_name'] == stem and stem not in names
        names.add(stem)
        assert doc['name'] == meta['name'] == entry['full_name']
        assert sha(blob) == meta['sha256'] and not meta['camera_tested']
        assert meta['metric_source_model'] == 'r5' and meta['training_error'] == source['training_error']
        if model == 'c2':
            assert doc['schema'] == 'a7c2-creative-look/1'
            assert doc['target'] == {'model': 'ILCE-7CM2', 'firmware': '2.01'}
            assert doc['base'] == 'ST' and doc['table_format'] == 'native-5x9x9-s7-planar'
            assert not {'edit_native', 'menu_icon', 'native_photo'}.intersection(doc)
            packed = bytes(v & 255 for plane in grid for layer in plane for row in layer for v in row)
            assert len(packed) == 1215 and base64.b64decode(doc['table_base64'], validate=True) == packed
            assert meta['source_bin_sha256'] == source['sha256']
        else:
            assert len(blob) <= 131072 and doc['id'] not in ids
            ids.add(doc['id'])
            assert doc['provenance']['source_bin_sha256'] == source['sha256']
            validate_m4(doc, template)
            for branch in ('photo', 'live'):
                params = doc['parameters'][branch]
                assert params['coefficients']['values'] == entry['cc1_delta']
                assert params['matrices']['values'] == entry['block13']
                assert doc['parameters']['grid'][branch] == grid
                expected = struct.pack('<129I', *entry['gamma_native_129'])
                assert all(bytes(record[:516]) == expected for record in params['gamma']['records'])
    print(model.upper(), len(metadata_paths), 'single-filter files verified')

if __name__ == '__main__':
    template = load(ROOT/'tools/m4-adapter/m4-template.json')
    validate_library('c2', '.a7look', 'A7Look /1', template)
    validate_library('m4', '.json', 'camera-look v2', template)
