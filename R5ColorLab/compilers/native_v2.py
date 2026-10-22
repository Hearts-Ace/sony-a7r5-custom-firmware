"""Development SD native-look compiler. No firmware/device writes or grid.

Binary v2: R5NATIVE.BIN, 128-byte header + 1..12 sorted 1200-byte records.
Native ordinal: 1 ST, 2 PT, 3 NT, 4 VV, 5 VV2, 6 FL, 7 FL2, 8 FL3,
9 IN, 10 SH, 11 BW, 12 SE. A name contains 1..31 UTF-8 bytes; camera font
coverage and visual truncation are separate hardware acceptance.
Only color values are serializable; native pointers, calibration, Gamma tail,
firmware offsets and extra compensation are deliberately not file fields.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT
AP_SHA = '8ee4d5876b7e127df39f8f820b9d21834c300ff895e02ca522636ed4733efc4b'
CP_SHA = '8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32'
NATIVE_NAMES = ('ST','PT','NT','VV','VV2','FL','FL2','FL3','IN','SH','BW','SE')
SCHEMA = 'r5-native-overwrite-config/2'
HEADER, RECORD, MAXIMUM = 128, 1200, 14528


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate key: '+key)
        result[key] = value
    return result


def load(path):
    def nonfinite(value):
        raise ValueError('Nonfinite value: '+value)
    if Path(path).stat().st_size > 131072:
        raise ValueError('Configuration exceeds 128 KiB')
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


def pack(config):
    keys(config, 'schema model baseline_ap_sha256 baseline_cp_sha256 additional_compensation_matrix_enabled compensation_grid_enabled entries')
    if (config['schema'] != SCHEMA or config['model'] != 'ILCE-7RM5' or
            config['baseline_ap_sha256'] != AP_SHA or config['baseline_cp_sha256'] != CP_SHA or
            config['additional_compensation_matrix_enabled'] is not False or
            config['compensation_grid_enabled'] is not False):
        raise ValueError('Wrong baseline/model or forbidden compensation')
    entries = config['entries']
    if type(entries) is not list or not 1 <= len(entries) <= 12:
        raise ValueError('Expected 1..12 look records')
    records, slots = [], set()
    for entry in entries:
        keys(entry, 'number name cc1_delta block13 gamma_native_129')
        slot = entry['number']
        if type(slot) is not int or not 1 <= slot <= 12 or slot in slots:
            raise ValueError('Invalid/duplicate slot')
        slots.add(slot)
        name = entry['name']
        if type(name) is not str or not 1 <= len(name.encode('utf-8')) <= 31 or any(ord(c)<32 or 127<=ord(c)<=159 or 0xd800<=ord(c)<=0xdfff for c in name):
            raise ValueError('Name must contain 1..31 UTF-8 bytes without control characters')
        cc1 = integers(entry['cc1_delta'], [3, 8], -32768, 32767)
        for group in range(3):
            absolute = [cc1[i]+(cc1[8*group+i] if group else 0) for i in range(8)]
            if any(not ( -1024 <= v <= 1023 if i < 4 else 0 <= v <= 1023) for i, v in enumerate(absolute)):
                raise ValueError('CC1 absolute endpoint exceeds native range')
        matrix = integers(entry['block13'], [3, 16, 6], -8192, 8191)
        gamma = integers(entry['gamma_native_129'], [129], 0, 131071)
        if gamma[0] != 0 or any(a > b for a, b in zip(gamma, gamma[1:])):
            raise ValueError('Gamma must be monotone with zero origin')
        record = bytearray(RECORD)
        struct.pack_into('<I32s24h288h129I', record, 0, slot, name.encode(), *cc1, *matrix, *gamma)
        records.append((slot, record))
    output = bytearray(HEADER+RECORD*len(records))
    struct.pack_into('<8s6I16s32s32s', output, 0, b'R5NAT12\0', 2, HEADER, len(output), len(records),
                     sum(1 << (s-1) for s in slots), 0, b'ILCE-7RM5', bytes.fromhex(AP_SHA), bytes.fromhex(CP_SHA))
    for index, (_, record) in enumerate(sorted(records)):
        output[HEADER+index*RECORD:HEADER+(index+1)*RECORD] = record
    struct.pack_into('<I', output, 112, zlib.crc32(output))
    return bytes(output)


def from_fit(path, capture, slot, name, gamma_endpoint128=None):
    # Existing source-bound strict reader also validates all shared 780F fields,
    # measured Gamma X and captured runtime identities. No unchecked old recipe.
    import sys
    sys.path[:0] = [str(ROOT/'scripts')]
    import numpy as np
    from edit_native_recipe import read
    recipe = load(path)
    if (recipe.get('additional_compensation_matrix_enabled') is not False or
            recipe.get('compensation_grid_enabled') is not False or 'pc_residual' in recipe):
        raise ValueError('Only uncompensated native fits accepted')
    validated, _ = read(path, capture, recipe['source']['context'], None)
    parameters = validated['parameters']
    raw = parameters['cc1_direct_raw']
    rounded = [raw[i] for i in (1, 2, 3, 0)] + [min(1023, (raw[i]+1)//2) for i in (5, 6, 7, 4)]
    cc1 = [rounded, [0]*8, [0]*8]
    payload = bytes.fromhex(parameters['matrix_780f_hex'])
    # Preserve the original signed bit-field, including asymmetric negative
    # decoding. Dividing decoded float coefficients would change those bits.
    matrix = [[struct.unpack_from('<h', payload, 24+2*(16*k+(s^1)))[0] >> 2
               for k in range(6)] for s in range(16)]
    preset=json.loads((ROOT/'data/presets.json').read_text())
    if preset['source_cp_sha256']!=CP_SHA:raise ValueError('CP provenance mismatch')
    curve=preset['native_ST_gamma_file_offset'];native=preset['ST_gamma']
    target = parameters['gamma_7806_y']
    endpoint = native[128] if gamma_endpoint128 is None else gamma_endpoint128
    if type(endpoint) is not int or not 0 <= endpoint <= 131071:
        raise ValueError('Native final ordinate outside supported range')
    gamma = [min(131071, (v+1)//2) for v in target] + [endpoint]
    if gamma[-2] > gamma[-1]:
        raise ValueError('Fit exceeds native ST final ordinate; endpoint requires independent configuration')
    config = dict(schema=SCHEMA, model='ILCE-7RM5', baseline_ap_sha256=AP_SHA,
        baseline_cp_sha256=CP_SHA, additional_compensation_matrix_enabled=False,
        compensation_grid_enabled=False, entries=[dict(number=slot, name=name,
            cc1_delta=cc1, block13=[matrix, matrix, matrix], gamma_native_129=gamma)])
    pack(config)
    back = [rounded[i] for i in (3, 0, 1, 2)] + [2*rounded[i] for i in (7, 4, 5, 6)]
    quant = dict(schema='r5-native-sd-fit-conversion/1', recipe_sha256=sha(Path(path).read_bytes()),
        source_cp_sha256=CP_SHA, native_ST_gamma_file_offset=hex(curve),
        additional_compensation_matrix_enabled=False, compensation_grid_enabled=False,
        endpoint_policy='custom fitted looks only: fixed matrix B=A1=A2; CC1 deltas zero',
        FL2_FL3_existing_endpoints_modified=False,
        cc1_raw_max_quantization_error=max(abs(a-b) for a, b in zip(raw, back)),
        gamma_raw_max_quantization_error=max(abs(a-2*b) for a, b in zip(target, gamma)),
        gamma_point128=endpoint, original_ST_gamma_point128=native[128],
        gamma_point128_policy=('preserve verified R5 ST point' if gamma_endpoint128 is None else
            'explicit development ordinate; not derivable from RAW and not hardware-validated'),
        gamma_ancillary_policy='not serialized; native adapter must preserve R5 fields and RAM references',
        matrix_coefficients_bitfield_equal=all(((matrix[s][k]<<2)&0xfffc) ==
            (struct.unpack_from('<H', payload, 24+2*(16*k+(s^1)))[0]&0xfffc) for s in range(16) for k in range(6)),
        camera_apply_allowed=False, installable=False,
        limits=['Development quantization, not a new color-accuracy measurement.',
                'Custom B/A1/A2 fixed endpoints are a selected policy, not three independently fitted endpoints.',
                'Native record tails, menu mapping, transport and persistence still require camera bindings.'])
    return config, quant


def write_new(path, data):
    with Path(path).open('xb') as stream:
        stream.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    fit = subs.add_parser('from-fit')
    fit.add_argument('recipe', type=Path)
    fit.add_argument('--capture', type=Path, required=True)
    fit.add_argument('--number', type=int, required=True, choices=range(1, 13), help='Native ordinal: 1ST 2PT 3NT 4VV 5VV2 6FL 7FL2 8FL3 9IN 10SH 11BW 12SE')
    fit.add_argument('--name', required=True)
    fit.add_argument('--gamma-endpoint128', type=int, help='Explicit missing native endpoint; default preserves R5 ST')
    fit.add_argument('--output', type=Path, required=True)
    binary = subs.add_parser('pack')
    binary.add_argument('config', type=Path)
    binary.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'from-fit':
        config, audit = from_fit(args.recipe, args.capture, args.number, args.name, args.gamma_endpoint128)
        if args.output.exists() or args.output.with_suffix('.audit.json').exists():
            raise ValueError('Refuse overwrite')
        write_new(args.output, (json.dumps(config, indent=2)+'\n').encode())
        write_new(args.output.with_suffix('.audit.json'), (json.dumps(audit, indent=2)+'\n').encode())
        print(json.dumps(audit, indent=2))
    else:
        payload = pack(load(args.config))
        write_new(args.output, payload)
        print(json.dumps(dict(bytes=len(payload), sha256=sha(payload), installable=False,
                             camera_reader_installed=False, extra_compensation=False)))


if __name__ == '__main__':
    main()
