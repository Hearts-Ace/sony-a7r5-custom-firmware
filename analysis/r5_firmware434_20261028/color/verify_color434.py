"""Execute the unchanged current CP against the proposed default properties.

Writes new evidence in this directory only. This is synthetic memory/ARM
instruction validation, not camera execution or image-quality validation.
"""
from pathlib import Path
import hashlib
import importlib.util
import itertools
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / 'vendor/audit-python'), str(ROOT / 'tools')]
from color434 import patch_properties, updates, describe, SOURCE_HASHES, sha
from sony_bk4 import find_banks
from build_r5_m4strict_personal import color_updates, donors
from verify_r5_m4strict_cp_cpu import lookup, new_cpu, BASE, SCRATCH, SP, STOP, w32
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

CP_PATH = ROOT / 'analysis/r5_custom_filter423_20261023/cp/cp423.NONINSTALLABLE.bin'
CP_SHA = '8b38e753f34b1667d79b69079d911b9e6595f1ce1b873cb8e014437c6b4c494d'
BK4_PATH = ROOT / 'unpacked/r5/firmware/0110_backup/SYSIPSX-DSLR/GL/CX89200_ALLLANG.bin'


def require(value, message):
    if not value:
        raise ValueError(message)


def matrix_values(q):
    a, b, c, d, e, f = q
    return [a+b+1024, -a, -b, -c, c+d+1024, -d, -e, -f, e+f+1024]


def matrix_call(cp, prop, profile, hue):
    u = new_cpu(cp)
    u.mem_write(0x16b3414, prop)
    wrap, state, env, dst = [SCRATCH+x for x in (0x1000, 0x2000, 0x3000, 0x4000)]
    w32(u, wrap, state)
    w32(u, wrap+4, env)
    u.mem_write(env+0x1a0, struct.pack('<3H', 1024, 1024, 1024))
    u.mem_write(dst, b'\xa5'*64)
    for reg, val in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), (dst, hue, wrap, profile)):
        u.reg_write(reg, val)
    u.reg_write(UC_ARM_REG_SP, SP)
    u.reg_write(UC_ARM_REG_LR, STOP|1)
    u.emu_start((BASE+0x61641e)|1, STOP, count=10000)
    require(u.reg_read(UC_ARM_REG_PC) == STOP and u.reg_read(UC_ARM_REG_SP) == SP, 'native matrix did not return')
    output = bytes(u.mem_read(dst, 64))
    require(output[54:] == b'\xa5'*10, 'native matrix wrote outside its 54-byte result')
    return struct.unpack('<27h', output[:54])


def main():
    cp = CP_PATH.read_bytes()
    require(sha(cp) == CP_SHA, 'Current 4.32 CP identity mismatch')
    stock_file = BK4_PATH.read_bytes()
    bank = find_banks(stock_file)[1]
    stock = {k: bank.property(k).data for k in SOURCE_HASHES}
    require(all(bank.property(k).attributes == 8 for k in stock), 'Unexpected native migration attribute')
    changed, ledger = patch_properties(stock)
    # Construct comparison properties with the independently established FL23
    # changes already present, as the new full-template packager will do.
    old = dict(stock)
    dc, dm = donors()
    for key, data, _ in color_updates(stock[0x02a40001], stock[0x02a4000d], dc, dm):
        old[key] = data
    new, _ = patch_properties(old, require_stock=False)
    cc_rows = []
    normal_profiles = (0, 1, 2, 6, 41, 42, 43, 44, 53, 54, 55, 21, 22, 23, 27, 45, 46, 47, 48, 56, 57)
    for profile, adjustment in itertools.product(normal_profiles, ([0]*8, [-32768,32767]*4, [32767,-32768]*4)):
        before, before_calls = lookup(cp, 0x616670, profile, 0, adjustment, old[0x02a40001])
        after, after_calls = lookup(cp, 0x616670, profile, 0, adjustment, new[0x02a40001])
        if profile == 0:
            vals = struct.unpack('<24h', new[0x02a40001][0x1250:0x1280])
            base = [(vals[i]+adjustment[i]) & 65535 for i in range(8)]
            expected = base + [(base[i]+vals[8+i]) & 65535 for i in range(8)] + [(base[i]+vals[16+i]) & 65535 for i in range(8)]
            require(after[:48] == struct.pack('<24H', *expected), 'new ST CC1 not consumed by current native CP')
            require(after[48:] == before[48:], 'ST CC1 output tail changed')
        else:
            require(after == before and after_calls == before_calls, f'non-ST normal profile changed {profile}')
        cc_rows.append({'profile': profile, 'adjustment': adjustment, 'changed': before != after,
                        'output24_u16': list(struct.unpack('<24H', after[:48]))})

    matrix_rows = []
    # Main normal native profiles; profile53 is a separate native identity path.
    for profile, hue in itertools.product((0, 1, 2, 6, 41, 42, 43, 44, 21, 22, 23, 27, 45, 46, 47, 48, 54, 55, 56, 57), range(16)):
        before = matrix_call(cp, old[0x02a4000d], profile, hue)
        after = matrix_call(cp, new[0x02a4000d], profile, hue)
        if profile == 0:
            expected_a1 = matrix_values(struct.unpack_from('<6h', new[0x02a4000d], 0x2a0+hue*12))
            require(list(after[9:18]) == expected_a1, 'new ST A1 not consumed by current native CP')
            require(after[:9] == before[:9] and after[18:] == before[18:], 'ST B/A2 matrices changed')
        else:
            require(after == before, f'non-ST normal matrix profile changed {profile}')
        matrix_rows.append({'profile': profile, 'hue_slot': hue, 'changed': before != after,
                            'A1_matrix': list(after[9:18])})

    # Importing this original harness creates only a synthetic Unicorn context.
    # It does not execute its __main__ or write historical artifacts. Replacing
    # its CP memory with the exact current CP tests the actual release component.
    old_awb_script = ROOT / 'analysis/r5_awb_white_priority_20261028/replay_adjustment.py'
    spec = importlib.util.spec_from_file_location('native_awb434_fixture', old_awb_script)
    awb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(awb)
    awb.U.mem_write(BASE, cp)
    awb_rows = []
    for xy, metric, gate, branch, mode in itertools.product(
        [(10451,29051),(11284,26344),(9686,32001),(8192,40000),(14000,23000),(18000,12000),(16384,16384)],
        [0,1500,3000,12000], [0,256], [0,1], [0,1,2]):
        awb.PAR = stock[0x02a40000]
        before = awb.run(mode, xy, metric, gate, branch)
        awb.PAR = new[0x02a40000]
        after = awb.run(mode, xy, metric, gate, branch)
        if mode == 0:
            require(before['out'] == after['out'] and before['trace'] == after['trace'], 'standard AWB branch changed')
        awb_rows.append({'mode': mode, 'xy': list(xy), 'metric': metric, 'gate': gate, 'branch': branch,
                         'before': before['out'], 'after': after['out'], 'changed': before['out'] != after['out']})
    example = next(r for r in awb_rows if r['mode'] == 2 and r['xy'] == [18000,12000] and r['metric'] == 1500 and r['gate'] == 256 and r['branch'] == 1)
    require(example['before'] == [17098,12718] and example['after'] == [17302,12557], 'known white97 replay example mismatch')
    require(any(r['changed'] for r in awb_rows if r['mode'] == 1), 'ambience priority mutation never reached output')
    require(any(r['changed'] for r in awb_rows if r['mode'] == 2), 'white priority mutation never reached output')
    require(cp == CP_PATH.read_bytes() and stock_file == BK4_PATH.read_bytes(), 'input source changed')
    report = {
        **describe(), 'passed': True, 'CP_sha256': CP_SHA,
        'sources': {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in
                    (CP_PATH, BK4_PATH, HERE/'color434.py', HERE/'verify_color434.py', old_awb_script,
                     ROOT/'analysis/r6_st_reverse_20261028/comparison.json')},
        'property_changes': ledger, 'all3_properties_native_migration_attr8': True,
        'cc1': {'cases': len(cc_rows), 'rows': cc_rows,
                'native_adjustment_subservice': 'Declared input vector injected by the retained adjustment-helper seam; installed custom-source gate and CC1 arithmetic execute.'},
        'matrix': {'cases': len(matrix_rows), 'rows': matrix_rows,
                   'native_helper_stubs': False, 'ST_B_A2_preserved': True, 'ST_A1_all16_verified': True},
        'AWB': {**describe()['AWB'], 'cases': len(awb_rows), 'rows': awb_rows, 'native_helper_stubs': False,
                'standard_all112_cases_unchanged': True, 'white97_example': example},
        'CP_exactly_4_32_unchanged': True,
        'limits': describe()['limits'] + [
            'Synthetic zero-filled caller contexts and supplied calibration1024 are not live camera memory.',
            'Normal native profiles tested; scenes/aliases already mapped to bank0 share its change.',
            'AWB state gate/statistics branches have no asserted photo/video semantics; results are internal coordinates, not RGB/JPEG quality.',
            'Native upgrade migration and final firmware package are verified separately by the preservation and root stages.'],
    }
    (HERE/'color434_verified.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    (HERE/'color434_ranges.json').write_text(json.dumps(describe(), indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({'passed': True, 'CP_sha256': CP_SHA, 'CC1_cases': len(cc_rows),
                      'matrix_cases': len(matrix_rows), 'AWB_cases': len(awb_rows), 'white97_example': example}, ensure_ascii=False))


if __name__ == '__main__':
    main()
