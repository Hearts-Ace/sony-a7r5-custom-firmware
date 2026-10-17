"""R5 gamma layout adaptation for the M4 v7 feature set; no camera I/O.

Data allocations are coordinated with r5_403_cp: five curves in the original
text segment's final padding, remaining curve/tables in rodata final padding.
The integrator extends both segment lengths to their existing page boundaries.
M4 native records have 572-byte stride, reading bytes +0x238/+0x239; its
extra four zeros are padding. R5 native 576-byte records read u32 +0x23c.
R5 and FX2 native creative-look records both carry 2 there; retain the
R5/FX2 field correspondence rather than importing unused M4 padding.
"""
from __future__ import annotations
import hashlib
import json
import struct
import sys
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build_r5_m4strict_4.03_20261015/evidence/cp/gamma'
BASE = 0x108000
STOCK_SHA = '3269bf62426339791fcfbe8529698cd4accbe6c3d2ea61cd7c368a90ab7ee7c8'
DONOR_SHA = 'eba723db657117a36d9593dacf640840aca893c0d6ee5d728de9d1996b8c5e29'
STOCK_TABLE = 0x1004fa8
STOCK_ROUTE = 0xcc467c
CURVES = (0xae74c0, 0xae7700, 0xae7940, 0xae7b80, 0xae7dc0, 0xf76728)
TABLE = 0xf76968
ROUTE = 0xf76efc
CURVE_SIZE = 0x240
TABLE_SIZE = 51 * 7 * 4
ROUTE_SIZE = 22 * 8
GAMMA_IDS = (47, 48, 49, 50)
DONOR_TABLE = 0x11130d4
DONOR_ROUTE = 0xdac014
# Six original FX2 records, in the semantic order used by the A7M4 reference.
DONORS = (
    ('FL2 still slots 0-5', 0xdb32bc, 'f28fe572c6fb73564b3466bd29a087226164076f2909bf80d49f1c0b7b5f3e5b'),
    ('FL2 still slot 6', 0xdb3500, '8cb914f31e4354754f3ee5565812d0b23b65b0ebbea9c06088bf62ee68c3eb37'),
    ('FL2 movie slot 6', 0xdb3bcc, 'ae1343995ba604c6054520bed9878eaa51e44b68fee6fab1d4cd0f18eb43d1c6'),
    ('FL3 still slots 0-5', 0xdb3744, '81f034502d32d0a1ff07221d254a63b87c669a4f08e2e423e1a7cb2bca6de1c8'),
    ('FL3 still slot 6', 0xdb3988, '2c424f305ae32e99d90f9bedf6df7b25ccfddb43169eaa522aece176671966c9'),
    ('FL3 movie slot 6', 0xdb3e10, 'bbbdd262332e79ea9d290df26eaa0a340f180bdf76e484d179b2915c75f720d8'),
)
# All exact movw/movt references discovered for the actual R5 addresses. The
# unrelated movw matches with a different movt high half are deliberately absent.
TABLE_REFS = (
    (0x30b64a, 0x30b656, 10), (0x30bd26, 0x30bd2e, 10),
    (0x30bf3a, 0x30bf42, 3), (0x30bf88, 0x30bf90, 3),
    (0x30c05e, 0x30c066, 2), (0x9a0a9a, 0x9a0aa2, 1),
)
ROUTE_REFS = (
    (0x9a0304, 0x9a0308, 2), (0x9a039e, 0x9a03a2, 1),
    (0x9a05b4, 0x9a05b8, 0), (0x9a06a6, 0x9a06ac, 2),
)
# The last site belongs to the public slot-5 availability query. Repointing its
# table without widening this validation would still reject all four new IDs.
BOUNDS = (0x9a0442, 0x9a0466, 0x9a0488, 0x9a05f6, 0x9a0a68)
MD = Cs(CS_ARCH_ARM, CS_MODE_THUMB)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def mov16(reg, value, top=False):
    assert 0 <= reg < 15 and 0 <= value < 65536
    return struct.pack('<HH', (0xf2c0 if top else 0xf240) |
                       ((value >> 12) & 15) | (((value >> 11) & 1) << 10),
                       (value & 255) | (((value >> 8) & 7) << 12) | (reg << 8))


def convert_curve(donor, at):
    """Remove the FX2-only u32 at +0x238; retain the following flag and enum.

    Actual R5 consumer reads flag +0x238 and enum +0x23c. Actual FX2 consumer
    reads extra word +0x238, flag +0x23c, enum +0x240. All six donor extra words
    and flags are zero; their enum is 2. This is not a blind 572+zero transplant.
    """
    source = donor[at:at + 0x244]
    assert len(source) == 0x244
    assert source[0x238:0x23c] == bytes(4)
    assert source[0x23c:0x240] == bytes(4)
    assert source[0x240:0x244] == struct.pack('<I', 2)
    result = source[:0x238] + source[0x23c:0x244]
    assert len(result) == CURVE_SIZE
    return result


def build_patches(stock: bytes):
    assert sha(stock) == STOCK_SHA, 'Unexpected R5 CP baseline'
    donor_path = ROOT / 'unpacked/fx2/cp_data/cpapp-b.bin'
    donor = donor_path.read_bytes()
    assert sha(donor) == DONOR_SHA
    assert len(stock) == 17617008
    # Fixed ranges are original section-tail padding, never existing records.
    assert stock[0xae7218:0xae8000] == bytes(0xde8)
    assert stock[0xf76728:0xf77000] == bytes(0x8d8)
    assert CURVES[4] + CURVE_SIZE == 0xae8000
    assert CURVES[5] + CURVE_SIZE == TABLE
    assert TABLE + TABLE_SIZE == ROUTE and ROUTE + ROUTE_SIZE <= 0xf77000
    inventories = []
    for old, expected in ((STOCK_TABLE, TABLE_REFS), (STOCK_ROUTE, ROUTE_REFS)):
        address, found = BASE + old, []
        for reg in range(13):
            low, high = mov16(reg, address & 65535), mov16(reg, address >> 16, True)
            pos = 0
            while True:
                pos = stock.find(low, pos)
                if pos < 0:
                    break
                if not pos % 2:
                    for distance in range(4, 18, 2):
                        if stock[pos + distance:pos + distance + 4] == high:
                            found.append((pos, pos + distance, reg))
                pos += 1
        assert set(found) == set(expected), 'Reference inventory changed'
        assert stock.find(struct.pack('<I', address)) < 0, 'Unexpected literal table pointer'
        inventories.append({'address': hex(address), 'reference_pairs': len(found),
                            'scope': 'All r0-r12 MOVW/MOVT same-register pairs, +4..+16 bytes; no exact u32 literal pointer found'})
    patches, occupied, records = [], set(), []

    def add(at, after, reason):
        assert 0 <= at <= len(stock) - len(after)
        touched = set(range(at, at + len(after)))
        assert not occupied.intersection(touched), 'Overlapping gamma patches'
        occupied.update(touched)
        patches.append({'offset': at, 'before': stock[at:at + len(after)],
                        'after': bytes(after), 'reason': reason})

    # Prove the donor records are the actual FX2 native FL2/FL3 selections.
    donor_routes = [struct.unpack_from('<II', donor, DONOR_ROUTE + c * 8) for c in (19, 20)]
    assert donor_routes == [(48, 50), (49, 51)]
    donor_expected_rows = {
        48: [BASE + DONORS[0][1]] * 6 + [BASE + DONORS[1][1]],
        49: [BASE + DONORS[3][1]] * 6 + [BASE + DONORS[4][1]],
        50: [0] * 6 + [BASE + DONORS[2][1]],
        51: [0] * 6 + [BASE + DONORS[5][1]],
    }
    for idx, expected in donor_expected_rows.items():
        assert list(struct.unpack_from('<7I', donor, DONOR_TABLE + idx * 28)) == expected
    for (name, source, prefix_sha), dest in zip(DONORS, CURVES):
        assert sha(donor[source:source + 572]) == prefix_sha
        record = convert_curve(donor, source)
        add(dest, record, name + ': adapt FX2 gamma record to actual R5 576-byte struct')
        records.append({'name': name, 'source_file_offset': hex(source),
                        'source_record_size': 580, 'source_prefix572_sha256': prefix_sha,
                        'source_record_sha256': sha(donor[source:source + 580]),
                        'target_file_offset': hex(dest), 'target_va': hex(BASE + dest),
                        'target_size': len(record), 'target_sha256': sha(record),
                        'target_flag_0x238': record[0x238],
                        'target_enum_0x23c': struct.unpack_from('<I', record, 0x23c)[0]})

    table = bytearray(stock[STOCK_TABLE:STOCK_TABLE + 47 * 28])
    assert len(table) == 47 * 28
    # Old rows and null entries are copied exactly; the four new rows use the
    # same still/movie and slot selection pattern as native FX2.
    rows = ([BASE + CURVES[0]] * 6 + [BASE + CURVES[1]],
            [BASE + CURVES[3]] * 6 + [BASE + CURVES[4]],
            [0] * 6 + [BASE + CURVES[2]],
            [0] * 6 + [BASE + CURVES[5]])
    for row in rows:
        table += struct.pack('<7I', *row)
    assert len(table) == TABLE_SIZE
    add(TABLE, table, 'Gamma table: preserve IDs 0-46 and add native FL2/FL3 slot rows 47-50')
    route = bytearray(stock[STOCK_ROUTE:STOCK_ROUTE + ROUTE_SIZE])
    assert route[:19 * 8] == donor[DONOR_ROUTE:DONOR_ROUTE + 19 * 8]
    struct.pack_into('<II', route, 19 * 8, 47, 49)
    struct.pack_into('<II', route, 20 * 8, 48, 50)
    add(ROUTE, route, 'Color routes: retain original entries, color19->47/49 and color20->48/50')

    for refs, old, new, label in ((TABLE_REFS, STOCK_TABLE, TABLE, 'gamma pointer table'),
                                   (ROUTE_REFS, STOCK_ROUTE, ROUTE, 'color to gamma table')):
        for lo, hi, reg in refs:
            assert stock[lo:lo + 4] == mov16(reg, (BASE + old) & 0xffff)
            assert stock[hi:hi + 4] == mov16(reg, (BASE + old) >> 16, True)
            add(lo, mov16(reg, (BASE + new) & 0xffff), f'Redirect {label} low half, r{reg}')
            add(hi, mov16(reg, (BASE + new) >> 16, True), f'Redirect {label} high half, r{reg}')
    for at in BOUNDS:
        assert stock[at:at + 2] == bytes.fromhex('2f28'), f'Wrong gamma limit at {at:#x}'
        add(at, bytes.fromhex('3328'), 'Accept gamma IDs 0..50; retain original signed comparison/fallback')

    report = {'source_sha256': STOCK_SHA, 'source_bytes': len(stock), 'donor_sha256': DONOR_SHA,
              'source_pointer_table_file_offset': hex(STOCK_TABLE), 'target_pointer_table_file_offset': hex(TABLE),
              'source_route_file_offset': hex(STOCK_ROUTE), 'target_route_file_offset': hex(ROUTE),
              'reference_inventory': inventories,
              'table_refs': [{'movw': hex(a), 'movt': hex(b), 'reg': r} for a, b, r in TABLE_REFS],
              'route_refs': [{'movw': hex(a), 'movt': hex(b), 'reg': r} for a, b, r in ROUTE_REFS],
              'gamma_bound_sites': [hex(a) for a in BOUNDS], 'curves': records,
              'native_FX2_gamma_ids': donor_routes, 'R5_new_gamma_ids': [[47, 49], [48, 50]],
              'unchanged_original_table_bytes': 47 * 28, 'new_table_bytes': len(table),
              'new_route_bytes': len(route), 'patch_count': len(patches),
              'required_integrator_segment_sizes': {'text_length': '0xac8000', 'rodata_length': '0x48f000'},
              'allocations': [{'start': hex(CURVES[0]), 'end_exclusive': '0xae8000', 'role': 'first five curve records'},
                              {'start': hex(CURVES[5]), 'end_exclusive': hex(ROUTE + ROUTE_SIZE), 'role': 'sixth curve, pointer table, color route'}],
              'record_conversion': 'FX2[0:0x238]+FX2[0x23c:0x244]; omits FX2-only zero word and preserves native flag/enum',
              'limitations': ['Offline static and instruction-level evidence, no camera/ISP execution.',
                              'The private diagnostic sweep at file0x30b710 retains its original old-ID range; normal dispatch and public availability accept new IDs.',
                              'Signed negative gamma inputs retain the original function behavior; normal input contract uses nonnegative IDs.']}
    return patches, report


def apply_patches(stock, patches):
    result = bytearray(stock)
    for p in patches:
        at = p['offset']
        assert bytes(result[at:at + len(p['before'])]) == p['before']
        result[at:at + len(p['after'])] = p['after']
    return bytes(result)


def verify_instruction_paths(stock, patched):
    """Execute original Thumb paths against old and new data, without hardware."""
    sys.path.insert(0, str(ROOT / 'vendor/audit-python'))
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
    from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
        UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
        UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
        UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_CPSR)
    REGS = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
            UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
            UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11]
    RAM, STACK, RETURN = 0x03000000, 0x03010000, 0x0301f000

    class Machine:
        def __init__(self, data):
            self.u = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
            self.u.mem_map(BASE, (len(data) + 0xfff) & ~0xfff)
            self.u.mem_write(BASE, data)
            self.u.mem_map(RAM, 0x20000)
            self.u.mem_map(0x01800000, 0x800000)
            self.stop = None
            self.logs = 0
            def hook(u, address, size, _):
                if address == self.stop or address == RETURN:
                    u.emu_stop()
                elif address == 0xb0de92:
                    self.logs += 1
                    u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
            self.u.hook_add(UC_HOOK_CODE, hook)
        def run(self, start, stop, regs):
            for r in REGS:
                self.u.reg_write(r, 0)
            self.u.reg_write(UC_ARM_REG_CPSR, 0x20)
            self.u.reg_write(UC_ARM_REG_SP, STACK)
            self.u.reg_write(UC_ARM_REG_LR, RETURN | 1)
            self.u.mem_write(RAM, bytes(0x2000))
            self.u.mem_write(STACK, bytes(0x200))
            for k, v in regs.items():
                self.u.reg_write(REGS[k], v)
            self.stop = BASE + stop if stop is not None else RETURN
            self.logs = 0
            return self
        def execute(self, start):
            self.u.emu_start((BASE + start) | 1, RETURN, count=10000)
            assert self.u.reg_read(UC_ARM_REG_PC) == self.stop, 'Emulation failed to reach declared boundary'
        def w32(self, addr, value):
            self.u.mem_write(addr, struct.pack('<I', value))
        def r32(self, addr):
            return struct.unpack('<I', self.u.mem_read(addr, 4))[0]

    machines = [Machine(stock), Machine(patched)]
    route_cases = 0
    for color in range(22):
        for mode in (0, 1):
            for which, m in enumerate(machines):
                m.run(0x9a0304, 0x9a0338, {3: color, 4: RAM, 5: RAM + 0x100, 11: mode})
                m.w32(RAM + 0x100, color)
                m.execute(0x9a0304)
                table = ROUTE if which else STOCK_ROUTE
                expected = struct.unpack_from('<II', patched if which else stock, table + color * 8)
                actual = (m.r32(RAM + 0x30), m.r32(RAM + 0x40), m.r32(RAM + 0x34))
                assert actual == (expected[mode], expected[mode], expected[0])
                route_cases += 1
    pointer_cases = 0
    for gamma in range(51):
        for slot in range(7):
            m = machines[1]
            m.run(0x30b64a, 0x30b66a, {9: RAM, 11: RAM + 0x400})
            m.w32(RAM + 0x30, gamma)
            m.u.mem_write(RAM + 0x38, bytes([slot]))
            m.execute(0x30b64a)
            expected = struct.unpack_from('<I', patched, TABLE + gamma * 28 + slot * 4)[0]
            assert m.u.reg_read(UC_ARM_REG_R1) == expected
            if gamma < 47:
                assert expected == struct.unpack_from('<I', stock, STOCK_TABLE + gamma * 28 + slot * 4)[0]
            pointer_cases += 1
    availability = []
    for gamma in range(64):
        outputs = []
        for m in machines:
            m.run(0x9a0a68, None, {0: gamma})
            m.execute(0x9a0a68)
            outputs.append((m.u.reg_read(UC_ARM_REG_R0), m.logs))
        if gamma < 47:
            assert outputs[0] == outputs[1]
        elif gamma < 51:
            assert outputs[1] == (int(gamma in (47, 48)), 0)
            assert outputs[0] == (0, 1)
        else:
            assert outputs[0] == outputs[1] == (0, 1)
        availability.append({'gamma': gamma, 'stock': outputs[0], 'patched': outputs[1]})
    bound_cases = 0
    for gamma in range(64):
        for which, m in enumerate(machines):
            m.run(0x9a043e, 0x9a04a8, {4: RAM, 8: RAM + 0x30})
            for off in (0x30, 0x40, 0x34):
                m.w32(RAM + off, gamma)
            m.execute(0x9a043e)
            expected = gamma if gamma < (51 if which else 47) else 0
            assert [m.r32(RAM + off) for off in (0x30, 0x40, 0x34)] == [expected] * 3
            assert m.logs == (0 if gamma < (51 if which else 47) else 3)
            bound_cases += 1
    # Exercise the actual 129-u32 curve copy loop and tail metadata loads.
    curve_cases = 0
    for gamma in range(51):
        for slot in range(7):
            ptr = struct.unpack_from('<I', patched, TABLE + gamma * 28 + slot * 4)[0]
            if not ptr:
                continue
            m = machines[1]
            m.run(0x30bd26, 0x30bd52, {6: RAM + 0x100})
            m.w32(STACK + 0x30, RAM + 0x400)
            m.w32(RAM + 0x130, gamma)
            m.u.mem_write(RAM + 0x138, bytes([slot]))
            m.execute(0x30bd26)
            record = patched[ptr - BASE:ptr - BASE + CURVE_SIZE]
            assert bytes(m.u.mem_read(RAM + 0x400, 129 * 4)) == record[:129 * 4]
            m.run(0x30c05e, 0x30c0be, {0: slot, 5: RAM + 0x200, 8: RAM + 0x100, 9: RAM + 0x400})
            m.u.reg_write(UC_ARM_REG_LR, gamma)
            m.execute(0x30c05e)
            for src, dst in ((0x228, 0x28), (0x22c, 0x2c), (0x230, 0x30), (0x234, 0x34), (0x23c, 0x3c)):
                assert m.r32(RAM + 0x400 + dst) == struct.unpack_from('<I', record, src)[0]
            assert m.u.mem_read(RAM + 0x438, 1)[0] == record[0x238]
            if gamma >= 47:
                assert m.r32(RAM + 0x43c) == 2
            curve_cases += 1
    return {'engine': 'Unicorn Thumb real original/patched instructions; no ISP/device execution',
            'route_core_cases': route_cases, 'pointer_lookup_cases': pointer_cases,
            'availability_cases': availability, 'range_check_cases': bound_cases,
            'curve_copy_and_metadata_cases': curve_cases,
            'stubs': ['Original error logger 0xb0de92 returns to LR; logs are counted.'],
            'boundaries': ['Core routing/copy/metadata execute actual bounded blocks; full scene/override selection is not simulated.']}


def main():
    stock = (ROOT / 'unpacked/r5/cp_data/cpapp-b.bin').read_bytes()
    patches, report = build_patches(stock)
    patched = apply_patches(stock, patches)
    report['gamma_only_overlay_sha256'] = sha(patched)
    report['instruction_validation'] = verify_instruction_paths(stock, patched)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    serialized = [{'offset': hex(p['offset']), 'before_hex': p['before'].hex(),
                   'after_hex': p['after'].hex(), 'reason': p['reason']} for p in patches]
    (OUT / 'patches.json').write_text(json.dumps(serialized, indent=2, ensure_ascii=False) + '\n')
    excerpts = []
    for label, data, ranges in (
        ('R5 original', stock, [(0x9a0304, 0x34), (0x9a0a68, 0x4c), (0x30c05e, 0x62), (0x30bd26, 0x2c)]),
        ('R5 gamma overlay', patched, [(0x9a0304, 0x34), (0x9a0a68, 0x4c)]),
        ('FX2 original', (ROOT / 'unpacked/fx2/cp_data/cpapp-b.bin').read_bytes(), [(0x36f5b8, 0x7c)])):
        for at, length in ranges:
            excerpts.append(f'{label} file offset {at:#x}\n' + '\n'.join(
                f'{i.address-BASE:#010x} {i.bytes.hex():8s} {i.mnemonic} {i.op_str}'
                for i in MD.disasm(data[at:at + length], BASE + at)))
    (OUT / 'disassembly.txt').write_text('\n\n'.join(excerpts) + '\n')
    print(json.dumps({'patches': len(patches), 'gamma_only_overlay_sha256': sha(patched),
                      'verification': 'passed', 'camera_io': False}))


if __name__ == '__main__':
    main()
