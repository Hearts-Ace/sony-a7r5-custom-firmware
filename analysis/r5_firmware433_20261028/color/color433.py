"""Pure property-level R6 ST / AWB changes for the 4.33 native SD templates.

No camera access, settings-image generation or CP patch is performed. Original
R5 B/A2 block13 groups, bank tail, profile routing and Gamma remain untouched.
"""
from pathlib import Path
import hashlib
import struct

ROOT = Path(__file__).resolve().parents[3]
R6 = ROOT / 'analysis/r6_st_reverse_20261028'
SOURCE_HASHES = {
    0x02A40000: '4fd01e7ccfd55c17f00b60321b3c98ca2de5081530b970db3e715d49ca766ade',
    0x02A40001: '1fdae63d018d6f9d73de43273cb2694ef93d78dea8dff68779751956401b1f8a',
    0x02A4000D: '4a4ec0273185a2f3f08c3206e09c0d6a12b48f71a84d38f98d1247ca57d8bf8e',
}
SIZES = {0x02A40000: 0x1200, 0x02A40001: 0x2000, 0x02A4000D: 0x7000}
CC1 = [
    [-207, -269, -184, -51, 374, 526, 563, 563],
    [16, 0, -141, 0, 13, -40, 0, -93],
    [-137, 10, 0, 0, 2, -185, 0, -177],
]
CC1_SHA = 'e578cd18c4736c404f62049a2e00e0cb59dcd9b3c69ebd4096c6fff8ea419485'
A1_SHA = 'fe5a1f5c1636cd146a5f1bfa32def49cac06a58ac5004355b96f546d0f67ef4e'


def sha(value):
    return hashlib.sha256(value).hexdigest()


def updates():
    """Return property ID -> (relative offset, exact replacement bytes) pairs.

    Callers may merge these with separate FL2/FL3 patches. Inputs must be R5
    default properties, not an entire older personal/settings image.
    """
    cc = (R6 / 'r6_st_cc1_R5_delta48.bin').read_bytes()
    a1 = (R6 / 'r6_st_block13_A1_192.bin').read_bytes()
    if len(cc) != 48 or sha(cc) != CC1_SHA or cc != struct.pack('<24h', *sum(CC1, [])):
        raise ValueError('R6 recovered CC1 identity mismatch')
    if len(a1) != 192 or sha(a1) != A1_SHA:
        raise ValueError('R6 recovered block13 A1 identity mismatch')
    return {0x02A40000: [(0x930, bytes([112, 255]))],
            0x02A40001: [(0x1250, cc)],
            0x02A4000D: [(0x2A0, a1)]}


def patch_properties(properties, *, require_stock=True):
    """Apply only the three approved ranges and return fresh bytes plus ledger.

    require_stock=False is for a caller that already verified the original
    template and merged its independent FL23 changes; each local preimage is
    still required to be either the verified R5 original or this exact target.
    """
    from sony_bk4 import find_banks
    original_path = ROOT / 'unpacked/r5/firmware/0110_backup/SYSIPSX-DSLR/GL/CX89200_ALLLANG.bin'
    stock = {key: find_banks(original_path.read_bytes())[1].property(key).data for key in SOURCE_HASHES}
    ops = updates()
    result, ledger = {}, []
    for key, spans in ops.items():
        source = bytes(properties[key])
        if len(source) != SIZES[key] or sha(stock[key]) != SOURCE_HASHES[key]:
            raise ValueError(f'Unsupported property size or original identity {key:#x}')
        if require_stock and sha(source) != SOURCE_HASHES[key]:
            raise ValueError(f'Expected R5 original default {key:#x}')
        target = bytearray(source)
        allowed = set()
        for at, data in spans:
            before = source[at:at+len(data)]
            if before not in (stock[key][at:at+len(data)], data):
                raise ValueError(f'Unknown R5 source fragment {key:#x}+{at:#x}')
            target[at:at+len(data)] = data
            allowed.update(range(at, at+len(data)))
            ledger.append({'property_id': f'0x{key:08X}', 'relative_offset': hex(at),
                           'bytes': len(data), 'before_sha256': sha(before),
                           'after_sha256': sha(data), 'before_hex': before.hex(), 'after_hex': data.hex()})
        if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(source, target))):
            raise ValueError('Change outside approved parameter ranges')
        result[key] = bytes(target)
    if result[0x02A40000][0x930:0x934] != bytes([112, 255, 0, 6]):
        raise ValueError('AWB mode companion parameters changed')
    return result, ledger


def describe():
    return {
        'schema': 'r5-color433-ranges/1', 'camera_io': False,
        'R6_ST_photo_only': True, 'CP_changes_required': False,
        'implementation': 'All regional native SD default BK4 templates; attrs0x8 native firmware upgrade migration.',
        'property_source_hashes': {f'0x{k:08X}': v for k, v in SOURCE_HASHES.items()},
        'ranges': [{'property_id': f'0x{k:08X}', 'offset': hex(at), 'bytes': len(data), 'sha256': sha(data)}
                   for k, spans in updates().items() for at, data in spans],
        'AWB': {'white': {'offset': '0x930', 'old': 88, 'new': 112, 'coefficient_old': 432, 'coefficient_new': 480},
                'ambience': {'offset': '0x931', 'old': -24, 'new': -1, 'coefficient_old': 208, 'coefficient_new': 254},
                'companions_932_933': [0, 6], 'standard_branch_unchanged': True},
        'preserved': ['R5 ST block13 B/A2 and bank tail', 'CC1 row tail16', 'all non-bank0 coefficient banks and profile mappings',
                      'Gamma129 and full Gamma records', 'Knee/YGain and public header',
                      'native custom filter overrides and active-view source selection'],
        'limits': ['R6 native BK4 layout is not independently authenticated; recovered values are converted to R5 format.',
                   'Only ST photo bank0 is changed; ST movie profile21 maps to bank1 and is unchanged.',
                   'Original scene/alias profiles that already map to bank0 naturally share its updated coefficients; profile mappings are not changed.',
                   'Gamma first128 and effective short fields equal R5; missing Gamma point129 is not fabricated.',
                   'Firmware migration must be packaged and independently checked; this module alone does not update a camera.'],
    }
