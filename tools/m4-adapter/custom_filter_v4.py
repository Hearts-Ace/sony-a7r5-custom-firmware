"""R5 4.23 independent custom filters: strict v4 JSON/BIN codec, no device I/O.

Configuration numbers 1..12 are independent of the native Creative Look.
Each record has a short menu label, full name and mandatory signed7 5x9x9 grid.
Use a zero grid for no correction; selection 0 disables the entire custom filter.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
AP_SHA = '8ee4d5876b7e127df39f8f820b9d21834c300ff895e02ca522636ed4733efc4b'
CP_SHA = '8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32'
NATIVE_NAMES = ('ST', 'PT', 'NT', 'VV', 'VV2', 'FL', 'FL2', 'FL3', 'IN', 'SH', 'BW', 'SE')
SCHEMA = 'r5-custom-filter-config/4'
MAGIC = b'R5CUST4\0'
HEADER, RECORD, MAXIMUM = 128, 2452, 29552


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate key: ' + key)
        result[key] = value
    return result


def load(path):
    def nonfinite(value):
        raise ValueError('Nonfinite value: ' + value)
    if Path(path).stat().st_size > 1048576:
        raise ValueError('Configuration exceeds 1 MiB')
    return json.loads(Path(path).read_text(), object_pairs_hook=unique, parse_constant=nonfinite)


def keys(obj, required):
    if type(obj) is not dict or set(obj) != set(required.split()):
        raise ValueError('Unexpected or missing configuration fields')


def integers(values, dimensions, lo, hi):
    if type(values) is not list or len(values) != dimensions[0]:
        raise ValueError('Wrong parameter dimensions')
    if len(dimensions) > 1:
        return [v for row in values for v in integers(row, dimensions[1:], lo, hi)]
    if any(type(v) is not int or not lo <= v <= hi for v in values):
        raise ValueError('Integer parameter outside supported range')
    return values


def name_bytes(value, capacity):
    if type(value) is not str or any(ord(c) < 32 or 127 <= ord(c) <= 159 or
                                   0xd800 <= ord(c) <= 0xdfff for c in value):
        raise ValueError('Name must contain UTF-8 text without control characters')
    encoded = value.encode('utf-8')
    if not 1 <= len(encoded) < capacity:
        raise ValueError(f'Name must contain 1..{capacity-1} UTF-8 bytes')
    return encoded


def zero_grid():
    return dict(coefficients=[[[[0]*9 for _ in range(9)] for _ in range(5)] for _ in range(3)])


def config(entries):
    return dict(schema=SCHEMA, model='ILCE-7RM5', baseline_ap_sha256=AP_SHA,
                baseline_cp_sha256=CP_SHA, entries=entries)


def pack(value):
    keys(value, 'schema model baseline_ap_sha256 baseline_cp_sha256 entries')
    if (value['schema'] != SCHEMA or value['model'] != 'ILCE-7RM5' or
            value['baseline_ap_sha256'] != AP_SHA or value['baseline_cp_sha256'] != CP_SHA):
        raise ValueError('Expected R5 custom filter v4 and verified baseline')
    entries = value['entries']
    if type(entries) is not list or not 0 <= len(entries) <= 12:
        raise ValueError('Expected 0..12 custom filter records')
    records, slots = [], set()
    for entry in entries:
        keys(entry, 'number short_name full_name cc1_delta block13 gamma_native_129 grid_5x9x9')
        slot = entry['number']
        if type(slot) is not int or not 1 <= slot <= 12 or slot in slots:
            raise ValueError('Invalid/duplicate configuration number')
        slots.add(slot)
        short = name_bytes(entry['short_name'], 24)
        full = name_bytes(entry['full_name'], 64)
        cc1 = integers(entry['cc1_delta'], [3, 8], -32768, 32767)
        for group in range(3):
            absolute = [cc1[i] + (cc1[8*group+i] if group else 0) for i in range(8)]
            if any(not (-1024 <= v <= 1023 if i < 4 else 0 <= v <= 1023)
                   for i, v in enumerate(absolute)):
                raise ValueError('CC1 absolute endpoint exceeds native range')
        matrix = integers(entry['block13'], [3, 16, 6], -8192, 8191)
        gamma = integers(entry['gamma_native_129'], [129], 0, 131071)
        if gamma[0] != 0 or any(a > b for a, b in zip(gamma, gamma[1:])):
            raise ValueError('Gamma must be monotone with zero origin')
        keys(entry['grid_5x9x9'], 'coefficients')
        grid = integers(entry['grid_5x9x9']['coefficients'], [3, 5, 9, 9], -64, 63)
        record = bytearray(RECORD)
        struct.pack_into('<I24s64s24h288h129I1215b', record, 0,
                         slot, short, full, *cc1, *matrix, *gamma, *grid)
        records.append((slot, record))
    output = bytearray(HEADER + RECORD*len(records))
    struct.pack_into('<8s6I16s32s32s', output, 0, MAGIC, 4, HEADER, len(output), len(records),
                     sum(1 << (s-1) for s in slots), 0, b'ILCE-7RM5',
                     bytes.fromhex(AP_SHA), bytes.fromhex(CP_SHA))
    for index, (_, record) in enumerate(sorted(records)):
        output[HEADER+index*RECORD:HEADER+(index+1)*RECORD] = record
    struct.pack_into('<I', output, 112, zlib.crc32(output))
    return bytes(output)


def unpack(data):
    """Strict decode by canonical reconstruction; rejects old formats/padding."""
    if not HEADER <= len(data) <= MAXIMUM:
        raise ValueError('Invalid BIN size')
    if data[:8] != MAGIC or struct.unpack_from('<3I', data, 8) != (4, HEADER, len(data)):
        raise ValueError('Expected custom filter v4 BIN')
    count = struct.unpack_from('<I', data, 20)[0]
    if count > 12 or len(data) != HEADER + RECORD*count:
        raise ValueError('Invalid record count')
    entries = []
    for i in range(count):
        at = HEADER+i*RECORD
        def text_at(offset, capacity):
            raw = data[at+offset:at+offset+capacity]
            return raw.split(b'\0', 1)[0].decode('utf-8')
        cc1 = struct.unpack_from('<24h', data, at+92)
        block = struct.unpack_from('<288h', data, at+140)
        grid = struct.unpack_from('<1215b', data, at+1232)
        entries.append(dict(number=struct.unpack_from('<I', data, at)[0],
            short_name=text_at(4, 24), full_name=text_at(28, 64),
            cc1_delta=[list(cc1[g*8:g*8+8]) for g in range(3)],
            block13=[[list(block[g*96+s*6:g*96+s*6+6]) for s in range(16)] for g in range(3)],
            gamma_native_129=list(struct.unpack_from('<129I', data, at+716)),
            grid_5x9x9=dict(coefficients=[[[list(grid[c*405+y*81+u*9:c*405+y*81+u*9+9])
                for u in range(9)] for y in range(5)] for c in range(3)])))
    result = config(entries)
    if pack(result) != data:
        raise ValueError('Invalid CRC, baseline, order, text padding or reserved bytes')
    return result


def from_fit(path, capture, slot, short_name, full_name, gamma_endpoint128=None):
    """Quantize the existing checked fit parameters into the independent v4 format."""
    import sys
    sys.path[:0] = [str(ROOT/'scripts')]
    from edit_native_recipe import read
    recipe = load(path)
    if (recipe.get('additional_compensation_matrix_enabled') is not False or
            recipe.get('compensation_grid_enabled') is not False or 'pc_residual' in recipe):
        raise ValueError('Only uncompensated native fits accepted')
    validated, _ = read(path, capture, recipe['source']['context'], None)
    parameters = validated['parameters']
    raw = parameters['cc1_direct_raw']
    rounded = [raw[i] for i in (1, 2, 3, 0)] + [min(1023, (raw[i]+1)//2) for i in (5, 6, 7, 4)]
    payload = bytes.fromhex(parameters['matrix_780f_hex'])
    matrix = [[struct.unpack_from('<h', payload, 24+2*(16*k+(s^1)))[0] >> 2
               for k in range(6)] for s in range(16)]
    preset=json.loads((ROOT/'data/presets.json').read_text(encoding='utf-8'))
    if preset['source_cp_sha256']!=CP_SHA:raise ValueError('CP provenance mismatch')
    curve=preset['native_ST_gamma_file_offset'];native_endpoint=preset['ST_gamma'][128]
    endpoint = native_endpoint if gamma_endpoint128 is None else gamma_endpoint128
    if type(endpoint) is not int or not 0 <= endpoint <= 131071:
        raise ValueError('Native final ordinate outside supported range')
    target = parameters['gamma_7806_y']
    gamma = [min(131071, (v+1)//2) for v in target] + [endpoint]
    result = config([dict(number=slot, short_name=short_name, full_name=full_name,
        cc1_delta=[rounded, [0]*8, [0]*8], block13=[matrix, matrix, matrix],
        gamma_native_129=gamma, grid_5x9x9=zero_grid())])
    pack(result)
    back = [rounded[i] for i in (3, 0, 1, 2)] + [2*rounded[i] for i in (7, 4, 5, 6)]
    audit = dict(schema='r5-custom-filter-fit-conversion/4', recipe_sha256=sha(Path(path).read_bytes()),
        source_cp_sha256=CP_SHA, native_ST_gamma_file_offset=hex(curve),
        firmware_required='4.23', config_number_is_independent=True, grid_required=True, grid_is_zero=True,
        cc1_raw_max_quantization_error=max(abs(a-b) for a, b in zip(raw, back)),
        gamma_raw_max_quantization_error=max(abs(a-2*b) for a, b in zip(target, gamma)),
        gamma_point128=endpoint, original_ST_gamma_point128=native_endpoint,
        gamma_ancillary_policy='runtime actual Creative Look tail preserved; never serialized',
        matrix_coefficients_bitfield_equal=all(((matrix[s][k]<<2)&0xfffc) ==
            (struct.unpack_from('<H', payload, 24+2*(16*k+(s^1)))[0]&0xfffc)
            for s in range(16) for k in range(6)), camera_tested=False)
    return result, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    payload = pack(load(args.config))
    with args.output.open('xb') as stream:
        stream.write(payload)
    print(json.dumps(dict(bytes=len(payload), sha256=sha(payload), version=4, firmware='4.23')))


if __name__ == '__main__':
    main()
