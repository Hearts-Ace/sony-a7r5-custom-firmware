#!/usr/bin/env python3
"""Read-only R6 ST SR2 inversion and R5 stock comparison; no camera I/O.

Run from the workspace with .venv/bin/python -B. Outputs are research fragments,
not complete BK4 properties, import configurations, firmware, or flash images.
"""
from pathlib import Path
import csv
import hashlib
import importlib.util
import io
import json
import struct
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from sony_bk4 import find_banks

PATHS = {
    'r6_raw': Path('/Users/LOCAL_USER/Documents/DG707670.ARW'),
    'r5_raw': Path('/Users/LOCAL_USER/Documents/fl对比/DSC00430.ARW'),
    'reader': ROOT / 'R5ColorLab/scripts/sony_arw_metadata.py',
    'bk4_reader': ROOT / 'tools/sony_bk4.py',
    'r5_bk4': ROOT / 'unpacked/r5/firmware/0110_backup/SYSIPSX-DSLR/GL/CX89200_ALLLANG.bin',
    'fx2_bk4': ROOT / 'unpacked/fx2/firmware/0110_backup/SYSIPSX-DSLR/DOC/CX96900_ALLLANG.bin',
    'r5_cp': ROOT / 'unpacked/r5/cp_data/cpapp-b.bin',
    'fx2_cp': ROOT / 'unpacked/fx2/cp_data/cpapp-b.bin',
    'saved_raw_report': Path('/Users/LOCAL_USER/Documents/ChatGPT/ied软件/研究记录/20261016_FX2_M5_R6外观参数对照/完整比较结果.json'),
    'saved_r5_report': ROOT / 'analysis/r5_fl23_arw10_vs_firmware_20261016/raw_vs_cc1_correspondence.json',
    'saved_gamma_report': ROOT / 'analysis/r5_fl23_arw10_vs_firmware_20261016/matrix_gamma_correspondence.json',
    'saved_header_replay': ROOT / 'analysis/r5_fl23_common_fields_20261017/audit_results.json',
}
EXPECTED = {
    'r6_raw': '3167b87fba9301b3dec6822c6c7cd3898b42df2ef6563bc4229989d9f39b3a52',
    'r5_raw': '8aebb1f4fa75ce7aa3e830186d838b41fd13ad9e54781cb28f553ca548b41603',
    'r5_cp': '3269bf62426339791fcfbe8529698cd4accbe6c3d2ea61cd7c368a90ab7ee7c8',
    'fx2_cp': 'eba723db657117a36d9593dacf640840aca893c0d6ee5d728de9d1996b8c5e29',
}
SCHEMAS = {0x7842: (8, 8), 0x7844: (8, 8), 0x7845: (8, 8),
           0x7800: (8, 9), 0x780f: (7, 276), 0x7806: (9, 128),
           0x780c: (3, 1), 0x780d: (3, 1), 0x780e: (3, 10)}
FORMATS = {1: 'B', 3: 'H', 4: 'I', 6: 'b', 8: 'h', 9: 'i', 11: 'f', 12: 'd'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def values(entry):
    if entry['type'] == 2:
        return entry['data'].split(b'\0', 1)[0].decode('ascii')
    if entry['type'] in FORMATS:
        return list(struct.unpack('<' + str(entry['count']) + FORMATS[entry['type']], entry['data']))
    return None


def cc_inverse(entries):
    groups = []
    for tag in (0x7842, 0x7844, 0x7845):
        r = values(entries[tag])
        require(all(v % 2 == 0 for v in r[4:]), 'CC1 is not exactly divisible by 2')
        v = [r[1], r[2], r[3], r[0], r[5] // 2, r[6] // 2, r[7] // 2, r[4] // 2]
        forward = [v[3], v[0], v[1], v[2], 2*v[7], 2*v[4], 2*v[5], 2*v[6]]
        require(struct.pack('<8h', *forward) == entries[tag]['data'], 'CC1 forward mismatch')
        groups.append(v)
    return groups


def absolute_cc(groups):
    return [groups[0][:]] + [[a+b for a, b in zip(groups[0], g)] for g in groups[1:]]


def matrix(q):
    a, b, c, d, e, f = q
    return [a+b+1024, -a, -b, -c, c+d+1024, -d, -e, -f, e+f+1024]


def block_inverse(entries):
    raw = entries[0x780f]['data']
    v = struct.unpack('<96h', raw[24:216])
    require(all(x % 4 == 0 for x in v), 'block13 is not exactly divisible by 4')
    q = [[0] * 6 for _ in range(16)]
    for k in range(6):
        for j in range(16):
            q[j ^ 1][k] = v[16*k+j] // 4
    forward = struct.pack('<96h', *[4*q[j ^ 1][k] for k in range(6) for j in range(16)])
    require(forward == raw[24:216], 'block13 forward mismatch')
    m = values(entries[0x7800])
    require(matrix(q[0]) == m, 'independent 7800 matrix mismatch')
    require(all(sum(m[i:i+3]) == 1024 for i in (0, 3, 6)), 'matrix row sum mismatch')
    return q


def runtime_header(raw):
    """Invert the packed runtime values, not the entire original BK4 header.

    Derived from R5 packer file 0x624cae..0x624e7c, retained in native_ranges.txt.
    Axes/intervals/bases/flags have truncated bit widths; original high bits and
    default-vs-property selection are not encoded by this output.
    """
    w = list(struct.unpack('<69I', raw))
    axes = [(w[0] >> 11) & 1023, w[0] & 1023]
    for i in range(1, 5):
        axes += [(w[i] >> 22) & 1023, (w[i] >> 11) & 1023, w[i] & 1023]
    axes += [(w[5] >> 22) & 1023, (w[5] >> 11) & 1023]
    intervals = [v for word in w[54:62] for v in ((word >> 18) & 4095, (word >> 2) & 4095)]
    bases = [(w[62] >> 18) & 16383, (w[62] >> 2) & 16383, (w[63] >> 18) & 16383]
    controls = [(w[63] >> 8) & 255, w[63] & 255]
    for word in w[64:67]:
        controls += [(word >> shift) & 255 for shift in (24, 16, 8, 0)]
    controls += [(w[67] >> 24) & 255, (w[67] >> 16) & 255]
    flags = [(w[0] >> 26) & 3, (w[0] >> 31) & 1, (w[0] >> 30) & 1, (w[0] >> 28) & 3]
    terminal = w[67] & 65535
    # Repack all 84 non-coefficient bytes using decoded values, without copying them.
    h = [0] * 6
    h[0] = 0x03000000 | flags[0] << 26 | flags[1] << 31 | flags[2] << 30 | flags[3] << 28
    for n in range(5):
        h[n] += axes[3*n] << 11 | axes[3*n+1]
        h[n+1] += axes[3*n+2] << 22
    h[5] += axes[15] << 11
    tail = [(intervals[i] << 18) | (intervals[i+1] << 2) for i in range(0, 16, 2)]
    tail += [(bases[0] << 18) | (bases[1] << 2), (bases[2] << 18) | controls[0] << 8 | controls[1]]
    for i in (2, 6, 10):
        tail.append(sum(controls[i+j] << shift for j, shift in enumerate((24, 16, 8, 0))))
    tail += [(controls[14] << 24) | (controls[15] << 16) | terminal, terminal << 16 | terminal]
    require(struct.pack('<6I', *h) == raw[:24], 'runtime header forward mismatch')
    require(struct.pack('<15I', *tail) == raw[216:], 'runtime tail forward mismatch')
    return {'axes': axes, 'inverse_interval': intervals, 'channel_base': bases,
            'flags': flags, 'controls': controls, 'terminal_control': terminal,
            'full_84_byte_forward_match': True,
            'limit': 'Packed runtime values only; no unique original BK4 header, source branch or discarded high bits.'}


def gamma_inverse(entries):
    r = values(entries[0x7806])
    require(all(0 <= x and x % 2 == 0 for x in r), 'Gamma is not exactly divisible by 2')
    points = [x // 2 for x in r]
    require(struct.pack('<128i', *[2*x for x in points]) == entries[0x7806]['data'], 'Gamma forward mismatch')
    return points


def auxiliaries(entries):
    out = {}
    for name, tag, divisor in [('knee_point', 0x780c, 2), ('knee_slope', 0x780d, 16), ('ygain', 0x780e, 32)]:
        r = values(entries[tag])
        require(all(v % divisor == 0 for v in r), name + ' not exactly divisible')
        normalized = [v // divisor for v in r]
        require(struct.pack('<' + str(len(r)) + 'H', *[(v*divisor) & 65535 for v in normalized]) == entries[tag]['data'], name + ' forward mismatch')
        out[name] = {'canonical_values': normalized, 'input_modulus': 65536 // divisor,
                     'raw_values': r, 'tag': f'0x{tag:04X}'}
    out['limit'] = 'Canonical effective values in normal range. uint16 output wraps: original inputs are known modulo the given modulus; pointer identity/default/override is not recoverable.'
    return out


def native_color(data, expected_encoding):
    banks = find_banks(data)
    require(len(banks) == 2, 'unexpected BK4 bank count')
    b = banks[1]
    cc, block = [b.property(tag).data for tag in (0x02a40001, 0x02a4000d)]
    require(cc[0xefe] == expected_encoding, 'unexpected CC1 encoding')
    require(cc[0x1200] == 0 and block[0x196] == 0, 'ST photo is not bank0')
    groups = [list(struct.unpack_from('<8h', cc, 0x1250+i*16)) for i in range(3)]
    if expected_encoding:
        groups = [groups[0]] + [[a-b for a, b in zip(g, groups[0])] for g in groups[1:]]
    q = [list(struct.unpack_from('<6h', block, 0x1e0+192+i*12)) for i in range(16)]
    return groups, q, block, {'bk4_bank_offset': b.offset, 'bk4_checksum_valid': True,
                            'cc1_property': '0x02A40001', 'block13_property': '0x02A4000D'}


def native_gamma(cp, table, route):
    gamma_id = struct.unpack_from('<I', cp, route)[0]
    ptr = struct.unpack_from('<I', cp, table+28*gamma_id+6*4)[0]
    offset = ptr-0x108000
    require(0 <= offset <= len(cp)-516, 'Gamma pointer outside CP')
    return list(struct.unpack_from('<129I', cp, offset)), {'gamma_id': gamma_id, 'slot': 6, 'file_offset': hex(offset)}


def metrics(a, b):
    require(len(a) == len(b), 'comparison length mismatch')
    delta = [y-x for x, y in zip(a, b)]
    return {'total': len(a), 'different': sum(v != 0 for v in delta),
            'max_absolute_delta': max(map(abs, delta), default=0), 'delta_r6_minus_r5': delta}


def flatten(rows):
    return [v for row in rows for v in row]


def main():
    blobs = {k: p.read_bytes() for k, p in PATHS.items()}
    digests = {k: sha(b) for k, b in blobs.items()}
    require(all(digests[k] == v for k, v in EXPECTED.items()), 'source identity mismatch')
    spec = importlib.util.spec_from_file_location('sony_read_only', PATHS['reader'])
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    parsed, groups, st = {}, {}, {}
    for camera, key, model in [('R5', 'r5_raw', 'ILCE-7RM5'), ('R6', 'r6_raw', 'ILCE-7RM6')]:
        p = reader.parse(blobs[key])
        require(p['model'] == model, 'camera model mismatch')
        names = [reader.look_name(g) for g in p['styles']]
        require(len(names) == len(set(names)) and names.count('Standard') == 1, 'ambiguous ST record')
        groups[camera] = {reader.look_name(g): {e['tag']: e for e in g} for g in p['styles']}
        st[camera] = groups[camera]['Standard']
        require(len(st[camera]) == 114, 'unexpected ST tag count')
        for tag, expected in SCHEMAS.items():
            e = st[camera][tag]
            require((e['type'], e['count']) == expected, f'{camera} {tag:#x} schema mismatch')
        parsed[camera] = {'path': str(PATHS[key]), 'sha256': digests[key], 'model': model,
                          'software': reader.text(reader.one(p['root'], 0x131)),
                          'sr2_offset': p['offset'], 'sr2_length': p['length'],
                          'look_count': len(names), 'ST_tag_count': len(st[camera])}
    history = json.loads(blobs['saved_raw_report'])
    old_r5 = json.loads(blobs['saved_r5_report'])
    fxst = {int(r['tag'], 16): {'type': r['type'], 'count': r['count'], 'data': bytes.fromhex(r['hex'])}
            for r in history['all_look_records'] if r['camera'] == 'FX2' and r['look'] == 'Standard'}
    r6history = {int(r['tag'], 16): r for r in history['all_look_records'] if r['camera'] == 'A7R6' and r['look'] == 'Standard'}
    require(history['sources']['A7R6']['sha256'] == digests['r6_raw'], 'historical R6 identity mismatch')
    require(old_r5['r5_ARW_sha256'] == digests['r5_raw'], 'historical R5 identity mismatch')
    for tag, e in st['R6'].items():
        h = r6history[tag]
        require((e['type'], e['count'], e['data']) == (h['type'], h['count'], bytes.fromhex(h['hex'])), 'historical R6 payload mismatch')

    cc, q, gamma, aux, headers = {}, {}, {}, {}, {}
    for cam, entries in [('R5', st['R5']), ('R6', st['R6']), ('FX2', fxst)]:
        cc[cam], q[cam], gamma[cam] = cc_inverse(entries), block_inverse(entries), gamma_inverse(entries)
        aux[cam], headers[cam] = auxiliaries(entries), runtime_header(entries[0x780f]['data'])
    native_checks = []
    native_gammas = {}
    for cam, prefix, encoding, table, route in [('R5', 'r5', 0, 0x1004fa8, 0xcc467c), ('FX2', 'fx2', 1, 0x11130d4, 0xdac014)]:
        nc, nq, block, meta = native_color(blobs[prefix+'_bk4'], encoding)
        require(nc == cc[cam] and nq == q[cam], cam + ' inversion does not match native BK4')
        ng, gm = native_gamma(blobs[prefix+'_cp'], table, route)
        require(ng[:128] == gamma[cam], cam + ' inversion does not match native CP')
        require(list(struct.unpack_from('<16H', block, 0x100)) == headers[cam]['axes'], 'native axes mismatch')
        native_gammas[cam] = ng
        native_checks.append({'camera': cam, **meta, **gm, 'cc1_24_native_exact': True,
                              'block13_A1_96_native_exact': True, 'gamma_128_native_exact': True})
    base_ygain = list(struct.unpack_from('<10H', blobs['r5_cp'], 0xdbf28c))
    require(base_ygain[1:] == aux['R5']['ygain']['canonical_values'][1:], 'native base YGain mismatch')
    replay = next(r for r in json.loads(blobs['saved_header_replay'])['header_and_780F_replay'] if r['look'] == 'Standard')
    for key in ('axes', 'inverse_interval', 'channel_base', 'flags'):
        require(replay[key] == headers['R5'][key], 'retained native runtime header mismatch')

    all_tags = []
    require(st['R5'].keys() == st['R6'].keys(), 'tag set mismatch')
    for tag in sorted(st['R6']):
        a, b = st['R5'][tag], st['R6'][tag]
        row = {'tag': f'0x{tag:04X}', 'same_schema': (a['type'], a['count']) == (b['type'], b['count']),
               'same_payload': a['data'] == b['data'], 'documented_firmware_mapping': tag in SCHEMAS}
        for cam, e in [('R5', a), ('R6', b)]:
            row[cam] = {'type': e['type'], 'count': e['count'], 'values': values(e),
                        'hex': e['data'].hex(), 'sha256': sha(e['data']), 'entry_offset': e['entry'],
                        'same_across_all_looks_in_sample': len({(g[tag]['type'], g[tag]['count'], g[tag]['data']) for g in groups[cam].values()}) == 1}
        if tag in (0x7312, 0x7313):
            row['interpretation'] = 'WB_RGGBLevelsAuto' if tag == 0x7312 else 'WB_RGGBLevels'
        all_tags.append(row)

    different_tags = [r['tag'] for r in all_tags if not (r['same_schema'] and r['same_payload'])]
    shared_differences = [r['tag'] for r in all_tags if r['tag'] in different_tags and all(r[c]['same_across_all_looks_in_sample'] for c in ('R5', 'R6'))]
    cc_metric = metrics(flatten(cc['R5']), flatten(cc['R6']))
    abs_metric = metrics(flatten(absolute_cc(cc['R5'])), flatten(absolute_cc(cc['R6'])))
    q_metric = metrics(flatten(q['R5']), flatten(q['R6']))
    gm = metrics(gamma['R5'], gamma['R6'])
    report = {
        'camera_io': False, 'scope': 'R6 and stock R5 Standard / ST photo metadata; no video inference',
        'raw_sources': parsed,
        'sources': {k: {'path': str(PATHS[k]), 'sha256': digests[k], 'bytes': len(b)} for k, b in blobs.items()},
        'script_sha256': sha(Path(__file__).read_bytes()),
        'validation': {'original_sources_hash_unchanged_after_read': True,
                       'r6_all114_match_historical_report': True, 'native_reference_checks': native_checks,
                       'all_inverted_values_forward_match': True, 'independent_7800_match': True,
                       'runtime_header_matches_retained_R5_native_replay': True},
        'cc1': {'r6_R5_delta_encoding_groups_B_A1minusB_A2minusB': cc['R6'],
                'r5_stock_delta_groups': cc['R5'], 'delta_encoding_comparison': cc_metric,
                'r6_absolute_groups_B_A1_A2': absolute_cc(cc['R6']),
                'r5_stock_absolute_groups_B_A1_A2': absolute_cc(cc['R5']), 'absolute_comparison': abs_metric,
                'R5_property_offset': '0x1250', 'coefficient_bytes': 48, 'unknown_row_tail_bytes': 16,
                'limit': 'Converted to verified R5 representation; R6 native BK4 layout is not independently available.'},
        'block13': {'r6_A1_slots16x6': q['R6'], 'r5_stock_A1_slots16x6': q['R5'],
                    'comparison': q_metric, 'R5_property_A1_offset': '0x2A0',
                    'r6_slot0_matrix': matrix(q['R6'][0]), 'r5_slot0_matrix': matrix(q['R5'][0]),
                    'r6_B': None, 'r6_A2': None, 'r6_bank_tail192': None,
                    'limit': 'Only A1 is uniquely represented; 7800 duplicates A1 slot0, not a second endpoint.'},
        'gamma': {'r6_exact_first128': gamma['R6'], 'r5_stock_first128': native_gammas['R5'][:128],
                  'comparison': gm, 'r6_point128_of129': None,
                  'r5_native_point128': native_gammas['R5'][128], 'fx2_native_point128': native_gammas['FX2'][128],
                  'r5_and_fx2_full129_equal': native_gammas['R5'] == native_gammas['FX2'],
                  'limit': 'RAW has no 129th point or full ancillary record/pointers; no R6 record reconstruction claimed.'},
        'auxiliary_effective_values': {'R6': aux['R6'], 'R5_saved_RAW': aux['R5'],
                                      'equal': aux['R6'] == aux['R5'], 'r5_native_base_ygain': base_ygain,
                                      'limit': 'R5 comparison uses saved RAW effective output; ST override RAM initialization has not been replayed.'},
        'block13_packed_runtime': {'R6': headers['R6'], 'R5': headers['R5'], 'equal': headers['R6'] == headers['R5']},
        'all114_raw_comparison': {'total': len(all_tags), 'same': len(all_tags)-len(different_tags),
                                 'different': len(different_tags), 'different_tags': different_tags,
                                 'different_but_shared_by_all_looks_within_each_sample': shared_differences,
                                 'rows': all_tags},
        'limits': [
            'Exact parameter arithmetic, not a sensor-to-JPEG equivalence or camera operation test.',
            'R5 native reference is original 4.00 BK4 and CP; saved R5 RAW provenance/edit history is not independently certified.',
            'Unsupported RAW tags are fully exported and compared, but their unknown firmware mappings are not invented.',
            'Sample-shared differences cannot be attributed uniquely to ST; scene, WB, calibration and other sources may differ.',
            'No complete CC1 property, block13 bank, Gamma record, import BIN or firmware image is generated.',
        ],
    }
    require(all(sha(p.read_bytes()) == digests[k] for k, p in PATHS.items()), 'source changed during analysis')

    outputs = {
        'r6_st_cc1_R5_delta48.bin': struct.pack('<24h', *flatten(cc['R6'])),
        'r6_st_block13_A1_192.bin': struct.pack('<96h', *flatten(q['R6'])),
        'r6_st_gamma_first128_u32.bin': struct.pack('<128I', *gamma['R6']),
    }
    report['binary_fragments'] = {k: {'bytes': len(v), 'sha256': sha(v)} for k, v in outputs.items()}
    outputs['comparison.json'] = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode()
    buf = io.StringIO(newline='')
    writer = csv.writer(buf)
    writer.writerow(['point_zero_based', 'R5_stock_u32', 'R6_recovered_u32', 'R6_minus_R5'])
    for i, (a, b) in enumerate(zip(gamma['R5'], gamma['R6'])):
        writer.writerow([i, a, b, b-a])
    outputs['gamma128_comparison.csv'] = buf.getvalue().encode()
    outputs['comparison.md'] = render(report).encode()
    require(all(not (HERE / name).exists() for name in outputs), 'refusing to overwrite previous analysis outputs')
    for name, payload in outputs.items():
        with (HERE / name).open('xb') as fp:
            fp.write(payload)
    print(json.dumps({'CC1_delta': cc_metric, 'CC1_absolute': abs_metric, 'block13_A1': q_metric,
                      'Gamma': gm, 'auxiliary_equal': report['auxiliary_effective_values']['equal'],
                      'runtime_equal': report['block13_packed_runtime']['equal'],
                      'RAW114': {k: report['all114_raw_comparison'][k] for k in ('total', 'same', 'different')},
                      'outputs': list(outputs)}, ensure_ascii=False))


def render(r):
    c, b, g, a = r['cc1'], r['block13'], r['gamma'], r['auxiliary_effective_values']
    rows = [
        '# R6 ST RAW 逆算及与 R5 原厂参数比较（2026-10-28）', '',
        'R6来源为 DG707670.ARW（ILCE-7RM6 v1.01）。R5机内基线为原厂4.00的BK4与CP；短字段及114标签比较另用已保存的DSC00430.ARW。源文件身份及全部数值在 [comparison.json](comparison.json)。', '',
        '| 项目 | 可逆算范围 | 与R5比较 |', '|---|---|---|',
        f"| CC1 | B、A1−B、A2−B共24个int16 | 差分存储值{c['delta_encoding_comparison']['different']}/24不同；还原绝对端点后{c['absolute_comparison']['different']}/24不同 |",
        f"| block13 | A1的16槽×6项，共96个int16 | {b['comparison']['different']}/96不同，最大绝对差{b['comparison']['max_absolute_delta']} |",
        '| Gamma | 前128个u32点 | 128/128完全相同 |',
        '| Knee／YGain | 正常范围的有效值；原始输入有uint16回绕歧义 | 与R5保存RAW有效值全部相同 |',
        '| 780F公共打包值 | 坐标、间隔换算、通道基准、控制位及控制字节 | 全部相同，84字节可正向精确重建 |', '',
        '## CC1', '',
        'RAW→R5差分格式：`v=[r1,r2,r3,r0,r5/2,r6/2,r7/2,r4/2]`。三组分别来自7842、7844、7845，所有除法精确整除。R6原厂BK4未提供，故这是转换成R5表示，不是认证R6原机存储布局。', '',
        '| 组 | R5原厂 | R6反算 | R6−R5 |', '|---|---|---|---|',
    ]
    for name, x, y in zip(('B', 'A1−B', 'A2−B'), c['r5_stock_delta_groups'], c['r6_R5_delta_encoding_groups_B_A1minusB_A2minusB']):
        rows.append(f'| {name} | `{x}` | `{y}` | `{[v-u for u,v in zip(x,y)]}` |')
    rows += ['', '48字节片段：[r6_st_cc1_R5_delta48.bin](r6_st_cc1_R5_delta48.bin)。不含每行后16字节或整个CC1属性。', '',
             '## block13', '',
             '逆算`q[j XOR 1][k]=int16(RAW780F[24+2*(16*k+j):])/4`，恢复A1全部96项。7800矩阵独立验证首槽；各行和均为1024。', '',
             '| 槽（零基） | R5 A1(a,b,c,d,e,f) | R6 A1(a,b,c,d,e,f) | R6−R5 |', '|---|---|---|---|']
    for i, (x, y) in enumerate(zip(b['r5_stock_A1_slots16x6'], b['r6_A1_slots16x6'])):
        rows.append(f'| {i} | `{x}` | `{y}` | `{[v-u for u,v in zip(x,y)]}` |')
    rows += ['', f"R5首槽矩阵：`{b['r5_slot0_matrix']}`。R6首槽矩阵：`{b['r6_slot0_matrix']}`。", '',
             '192字节片段：[r6_st_block13_A1_192.bin](r6_st_block13_A1_192.bin)。B、A2及bank末尾192字节无法由这些RAW标签唯一恢复；没有填零或复制A1假装恢复完整bank。', '',
             '## Gamma及配套参数', '',
             '逐点`CP[i]=RAW7806[i]/2`，i=0..127，所有点精确整除。反算值与R5原厂ST照片slot6（CP文件0xCC4A0C）的前128点全部相同，也与FX2原厂ST相同。', '',
             f"前8点：`{g['r6_exact_first128'][:8]}`；最后8个可见点：`{g['r6_exact_first128'][-8:]}`。", '',
             'R5和FX2的完整129点曲线相同，第129点均为130946。R6 RAW没有保存此点，因此不能证明R6该点也是130946；采用R5值补全会得到与R5相同的129点曲线，但属于带来源假设的补全，本次未生成该文件。', '',
             '逐点比较：[gamma128_comparison.csv](gamma128_comparison.csv)。512字节片段：[r6_st_gamma_first128_u32.bin](r6_st_gamma_first128_u32.bin)。RAW也不能还原完整Gamma记录的尾部和指针。', '',
             '| 短字段 | RAW值 | 正常范围反算值 | 与R5保存RAW |', '|---|---|---|---|']
    for key, label in [('knee_point', 'Knee point（780C÷2）'), ('knee_slope', 'Knee slope（780D÷16）'), ('ygain', '十档有效YGain（780E÷32）')]:
        v = a['R6'][key]
        rows.append(f"| {label} | `{v['raw_values']}` | `{v['canonical_values']}` | 相同 |")
    rows += ['', '短字段原厂输出是uint16，反算只在正常取值范围内唯一；原始point／slope／YGain分别仅能确定模32768／4096／2048的值。不能由输出恢复指针地址、默认或覆盖路径。R5静态Baseband表首项512，ST有效首项540是覆盖后的输出；没有声称直接从CP读到了该覆盖RAM值。', '',
             '## 780F公共部分', '',
             f"16个分区坐标：`{r['block13_packed_runtime']['R6']['axes']}`；间隔换算值均256，三通道基准均1024，控制位`{r['block13_packed_runtime']['R6']['flags']}`，16个控制字节均128，末尾控制值0。全部与R5已保存的原厂指令回放一致。", '',
             '这是打包后的运行参数。部分字段只有10／12／14位，原始高位被截断；三通道基准也可来自默认分支，因此不能反推完整block13公共头部。头24字节、尾60字节均已用解出的字段重新打包，与R6 RAW逐字节相等。', '',
             '## 全部114字段核对', '',
             '两份ST记录字段集合和类型完全一致，90个负载相同、24个不同。以下给出全部差异，完整114项原始十六进制、数值与逐标签散列见JSON。', '',
             '| 标签 | 在本样片所有外观内相同（R5／R6） | 已建立机内逆算关系 |', '|---|---|---|']
    for row in r['all114_raw_comparison']['rows']:
        if not row['same_payload']:
            state = '／'.join('是' if row[cam]['same_across_all_looks_in_sample'] else '否' for cam in ('R5', 'R6'))
            rows.append(f"| {row['tag']} | {state} | {'是' if row['documented_firmware_mapping'] else '未建立'} |")
    rows += ['', '其中7312／7313为自动及实际白平衡RGGB输出。另17个未建立机内对应的私有字段也在各自样片所有外观内共用，不能直接归因于ST调色或当作可移植的ST常量。其值已导出，但没有虚构固件偏移或换算。', '',
             '## 核验与限制', '',
             '新逆算函数对R5、FX2已知ST样本恢复的CC1全部24项、block13 A1全部96项、Gamma前128点，与各自原厂BK4／CP原始字节精确相等；R6全部114标签与历史独立解析记录相同。所有已逆算字段均完成正向回算，7800另作矩阵验证；所有输入读前／读后SHA256保持。', '',
             '计算说明的是保存文件与原厂基线之间的参数关系，未验证R6完整固件布局、当前R5运行时选择或最终JPG颜色。R5保存RAW的拍摄／编辑历史未独立认证；场景、白平衡、传感器标定和其它处理会影响跨机画面。', '',
             '复现脚本：[reverse_and_compare.py](reverse_and_compare.py)。仅新建本目录研究文件，无相机、固件写入、完整导入BIN或升级包操作。', '']
    return '\n'.join(rows)


if __name__ == '__main__':
    main()
