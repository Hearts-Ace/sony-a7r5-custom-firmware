import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
MD=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
def require(ok,message):
    if not ok: raise ValueError(message)

def bw(at, target):
    displacement = target-at-4
    require(displacement % 2 == 0 and -(1<<24) <= displacement < (1<<24), 'Thumb B.W outside signed25-bit range')
    value = displacement & ((1<<25)-1)
    s, i1, i2 = (value>>24)&1, (value>>23)&1, (value>>22)&1
    h1 = 0xf000 | (s<<10) | ((value>>12)&0x3ff)
    h2 = 0x9000 | (((1^i1^s)&1)<<13) | (((1^i2^s)&1)<<11) | ((value>>1)&0x7ff)
    raw = struct.pack('<HH',h1,h2)
    i = next(MD.disasm(raw,at))
    require(i.mnemonic == 'b.w' and i.op_str == f'#{target:#x}', 'Branch encoder disagreement')
    return raw
def branch(at,to,link=False):
    b=bytearray(bw(at,to)); h=struct.unpack_from('<H',b,2)[0]
    if link:struct.pack_into('<H',b,2,h|0x4000)
    return bytes(b)
TABLE_REFS = (
    (0x30b64a, 0x30b656, 10), (0x30bd26, 0x30bd2e, 10),
    (0x30bf3a, 0x30bf42, 3), (0x30bf88, 0x30bf90, 3),
    (0x30c05e, 0x30c066, 2), (0x9a0a9a, 0x9a0aa2, 1),
)

ROUTE_REFS = (
    (0x9a0304, 0x9a0308, 2), (0x9a039e, 0x9a03a2, 1),
    (0x9a05b4, 0x9a05b8, 0), (0x9a06a6, 0x9a06ac, 2),
)

BOUNDS = (0x9a0442, 0x9a0466, 0x9a0488, 0x9a05f6, 0x9a0a68)

def mov16(reg, value, top=False):
    assert 0 <= reg < 15 and 0 <= value < 65536
    return struct.pack('<HH', (0xf2c0 if top else 0xf240) |
                       ((value >> 12) & 15) | (((value >> 11) & 1) << 10),
                       (value & 255) | (((value >> 8) & 7) << 12) | (reg << 8))
