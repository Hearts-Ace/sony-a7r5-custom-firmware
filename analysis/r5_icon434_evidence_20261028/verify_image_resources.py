"""Native R5 libObj bank/index selection and bounded Sony LZ77 image decode.

The native selector and packed reader execute unchanged. The bank-cache fixture
returns a memory-backed original UXC by its actual header bank; no resource ID
or record address is supplied by a fixture. LZ77 decoding is a host model, not
execution of the camera's hardware /dev/ldec decoder.
"""
from pathlib import Path
import hashlib
import io
import json
import struct
import sys
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / 'vendor/audit-python'),
               str(ROOT / 'analysis/r5_custom_filter423_20261023/menu_research')]
from read_menu import Image
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as R

LIB = ROOT / 'unpacked/r5/usr_complete/lib/libObj.so'
APP = ROOT / 'unpacked/r5/usr_complete/share/app'
RAM, DATA, STOP = 0x20000000, 0x30000000, 0x200ff000


def sha(b):
    return hashlib.sha256(b).hexdigest()


def actual_look_labels(oracle):
    ap = Image(ROOT / 'analysis/r5_firmware433_20261028/ap/appFw.so')
    strings = [(path, path.read_bytes()) for path in sorted(APP.glob('string_english*.uxc'))]
    labels = {}
    for n, case in enumerate(oracle):
        address = 0x3f4a280 + n * 128
        assert struct.unpack('<I', ap.read(address + 0x34, 4))[0] == case['value']
        label_id, = struct.unpack('<I', ap.read(address + 8, 4))
        matches = []
        for path, blob in strings:
            at = blob.find(struct.pack('<I', (label_id & 0xffffff) | 0x1e000000))
            if at >= 0:
                label = blob[at + 4:blob.index(0, at + 4)].decode('utf8')
                matches.append(dict(file=str(path.relative_to(ROOT)), sha256=sha(blob),
                                    offset=hex(at), text=label))
        assert len(matches) == 1
        labels[case['value']] = dict(value=case['value'], row=case['row'], icon=case['icon'],
                                    label_resource=hex(label_id), source=matches[0],
                                    short_name=matches[0]['text'].split('(')[0])
    return labels


class ResourceVM:
    def __init__(self, orientation, bias):
        self.im = Image(LIB)
        self.bias = bias
        self.u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for seg in ELFFile(io.BytesIO(self.im.data)).iter_segments():
            if seg['p_type'] != 'PT_LOAD':
                continue
            low = (seg['p_vaddr'] + bias) & -4096
            high = (seg['p_vaddr'] + seg['p_memsz'] + bias + 4095) & -4096
            self.u.mem_map(low, high - low)
            self.u.mem_write(seg['p_vaddr'] + bias, seg.data())
        self.u.mem_map(RAM, 0x100000)
        self.paths, self.banks, self.requests = {}, {}, []
        self.u.mem_write(RAM + 0x30, struct.pack('<Q', RAM + 0x4000))
        self.u.mem_write(RAM + 0x4000, struct.pack('<Q', RAM + 0x4100))
        self.u.mem_write(RAM + 0x4110, struct.pack('<Q', RAM + 0x5000))
        # Memory-backed stream vtable getter fixture, no selector output.
        self.u.mem_write(RAM + 0x5000, bytes.fromhex('200080d2c0035fd6'))
        for bank in range(3):
            path = APP / f'image_{bank:02d}_{orientation}_IPSX.uxc'
            blob = path.read_bytes()
            assert blob[:4] == b'uxd\x07'
            assert struct.unpack_from('<H', blob, 10)[0] == bank
            base = DATA + bank * 0x1000000
            self.u.mem_map(base, (len(blob) + 4095) & -4096)
            self.u.mem_write(base, blob)
            holder = RAM + 0x1000 + bank * 0x100
            self.u.mem_write(holder + 0x18, struct.pack('<Q', base + 8))
            self.banks[bank] = holder
            self.paths[bank] = (path, blob, base)
        self.trace = set()
        self.u.hook_add(UC_HOOK_CODE, self.hook)

    def ret(self, value):
        self.u.reg_write(R.UC_ARM64_REG_X0, value)
        self.u.reg_write(R.UC_ARM64_REG_PC, self.u.reg_read(R.UC_ARM64_REG_LR))

    def hook(self, u, pc, size, data):
        if pc == STOP:
            u.emu_stop()
            return
        at = pc - self.bias
        self.trace.add(at)
        if at == 0x1237c0:
            bank = u.reg_read(R.UC_ARM64_REG_X1)
            self.requests.append(bank)
            self.ret(self.banks.get(bank, 0))

    def call(self, at, *args):
        for n, arg in enumerate(args):
            self.u.reg_write(getattr(R, f'UC_ARM64_REG_X{n}'), arg)
        self.u.reg_write(R.UC_ARM64_REG_SP, RAM + 0xf0000)
        self.u.reg_write(R.UC_ARM64_REG_LR, STOP)
        self.u.emu_start(at + self.bias, STOP, count=10000)
        assert self.u.reg_read(R.UC_ARM64_REG_PC) == STOP
        return self.u.reg_read(R.UC_ARM64_REG_X0)

    def resource(self, resource):
        pointer = self.call(0x123840, RAM, resource, RAM + 0x200)
        if not pointer:
            return None
        bank = self.requests[-1]
        path, blob, base = self.paths[bank]
        at = pointer - base
        stored, flags, width, height, length, relative = struct.unpack_from('<IIHHII', blob, at)
        assert stored == (resource & 0xffffff) | 0x1a000000
        assert self.call(0x118858, pointer) == 6
        payload_at = at + 4 + relative
        assert 0 < width < 8192 and 0 < height < 8192
        assert 0 < length < 0x1000000 and payload_at + length <= len(blob)
        payload = blob[payload_at:payload_at + length]
        decoded = inflate_lz77(payload, ((width + 15) & ~15) * height * 2)
        return dict(resource=hex(resource), file=str(path.relative_to(ROOT)),
                    file_sha256=sha(blob), bank=bank, index=resource & 0x1fff,
                    record_offset=hex(at), record_hex=blob[at:at + 20].hex(),
                    record_sha256=sha(blob[at:at + 20]), stored_resource=hex(stored),
                    native_record_type=6, flags=hex(flags), width=width, height=height,
                    payload_offset=hex(payload_at), payload_bytes=length,
                    payload_sha256=sha(payload), decoded_bytes=len(decoded),
                    decoded_sha256=sha(decoded)), decoded


def inflate_lz77(src, capacity):
    """Bounded translation of the workspace's MIT ma1co Sony LZ77 adapter.

    The original copyright/license is retained in sony-lz77.c (source binding
    below); this implementation only accepts an exact declared output length.
    """
    lengths = (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 32, 64)
    pos, out = 0, bytearray()
    while pos < len(src):
        tag = src[pos]
        pos += 1
        start = len(out)
        if tag == 15:
            assert pos + 3 <= len(src)
            count = struct.unpack_from('<H', src, pos + 1)[0]
            pos += 3
            assert pos + count <= len(src) and len(out) + count <= capacity
            out.extend(src[pos:pos + count])
            pos += count
        elif tag == 240:
            finished = False
            while not finished:
                assert pos < len(src)
                flags = src[pos]
                pos += 1
                for bit in range(8):
                    if flags & (1 << bit):
                        assert pos + 2 <= len(src)
                        first, second = src[pos:pos + 2]
                        pos += 2
                        distance = (first & 15) * 256 + second
                        if distance == 0:
                            finished = True
                            break
                        count = lengths[first >> 4]
                        assert distance <= len(out) - start and len(out) + count <= capacity
                        for _ in range(count):
                            out.append(out[-distance])
                    else:
                        assert pos < len(src) and len(out) < capacity
                        out.append(src[pos])
                        pos += 1
        else:
            raise ValueError(('Unsupported Sony LZ77 block', hex(tag), pos - 1))
    assert len(out) == capacity
    return bytes(out)


def write_preview(items):
    # PNG is written with the standard library; no font/rendering dependencies.
    canvas_width, canvas_height = 6 * 320, 4 * 160
    pixels = bytearray(b'\x26\x26\x26' * canvas_width * canvas_height)
    for n, (meta, raw, label) in enumerate(items):
        width, height = meta['width'], meta['height']
        stride = (width + 15) & ~15
        for y in range(height):
            for x in range(width):
                value = struct.unpack_from('<H', raw, (y * stride + x) * 2)[0]
                rgba = ((value >> 12) * 17, ((value >> 8) & 15) * 17,
                        ((value >> 4) & 15) * 17, (value & 15) * 17)
                color = bytes((c * rgba[3] + 38 * (255 - rgba[3]) + 127) // 255 for c in rgba[:3])
                for dy in range(4):
                    for dx in range(4):
                        xx = n % 6 * 320 + 20 + x * 4 + dx
                        yy = n // 6 * 160 + 10 + y * 4 + dy
                        at = (yy * canvas_width + xx) * 3
                        pixels[at:at + 3] = color
    def chunk(kind, blob):
        return struct.pack('>I', len(blob)) + kind + blob + struct.pack('>I', zlib.crc32(kind + blob))
    scanlines = b''.join(b'\0' + pixels[y * canvas_width * 3:(y + 1) * canvas_width * 3] for y in range(canvas_height))
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', canvas_width, canvas_height, 8, 2, 0, 0, 0))
    png += chunk(b'tEXt', b'Description\0' + '; '.join(label for _, _, label in items).encode())
    png += chunk(b'IDAT', zlib.compress(scanlines, 9)) + chunk(b'IEND', b'')
    (HERE / 'stock_icon_resources.png').write_bytes(png)


def main():
    oracle_path = HERE / 'stock_icons.json'
    oracle = json.loads(oracle_path.read_text())
    unique = [case for case in oracle['cases'] if case['bias'] == '0x0']
    labels = actual_look_labels(unique)
    (HERE / 'look_mapping.json').write_text(json.dumps(list(labels.values()), indent=2) + '\n')
    cases, preview = [], []
    for bias in (0, 0x40000000):
        for orientation in ('23', '32'):
            vm = ResourceVM(orientation, bias)
            for case in unique:
                result, raw = vm.resource(int(case['icon'], 16))
                name = labels[case['value']]['short_name']
                result.update(look_value=case['value'], look_name=name,
                              bias=hex(bias), orientation=orientation)
                cases.append(result)
                if bias == 0:
                    preview.append((result, raw, f"{name} {orientation} {case['icon']}"))
            assert vm.resource(0x021c6410) is None
            assert vm.requests[-1] == 0xe3
            assert all(a in vm.trace for a in (0x123840, 0x1238ac, 0x1238b0,
                                             0x122930, 0x122870, 0x118858))
    help_matches = []
    for path in sorted(APP.glob('string_english*.uxc')):
        blob = path.read_bytes()
        at = blob.find(struct.pack('<I', 0x1e1c6410))
        if at >= 0:
            text = blob[at + 4:blob.index(0, at + 4)].decode('utf8')
            help_matches.append(dict(file=str(path.relative_to(ROOT)), file_sha256=sha(blob),
                                     record_offset=hex(at), text=text))
    assert help_matches
    upstream = ROOT / 'analysis/a7c2_vm_review_20261020/upstream/report/2026-10-17-qemu-native-camera/runtime/analysis/sony-lz77.c'
    report = dict(passed=True, AP_sha256=oracle['AP_sha256'], oracle_sha256=sha(oracle_path.read_bytes()),
                  libObj_path=str(LIB.relative_to(ROOT)), libObj_sha256=sha(LIB.read_bytes()),
                  script_sha256=sha(Path(__file__).read_bytes()),
                  native_bank_selector='0x123840', native_record_reader='0x122930→0x122870',
                  native_resource_type='0x118858', resource_cases=len(cases),
                  look_mapping=list(labels.values()),
                  bad_433_resource='0x021c6410', bad_resource_image_lookup_rejected=True,
                  bad_resource_is_help_string=help_matches, cases=cases,
                  lz77_reference=dict(path=str(upstream.relative_to(ROOT)), sha256=sha(upstream.read_bytes())),
                  fixtures=['Original image UXC files are mapped into read-only input memory by the host.',
                            'Memory stream vtable getter returns non-null; actual 1229E8 dispatch executes.',
                            '1237C0 bank-cache/file-load service returns a holder for an actual file with matching header bank; no per-resource pointer or ID is stubbed.'],
                  limits=['The original bank/index arithmetic, packed index reader and record-type reader execute unchanged.',
                          'Sony LZ77 is a bounded software model; decoded pixels and RGBA4444 preview are host interpretation, not hardware /dev/ldec or physical LCD execution.',
                          'Native selectors are bound to frozen 4.33 AP; final 4.34 private forwarding must be tested separately.'])
    (HERE / 'image_resources.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    write_preview(preview)
    print(json.dumps(dict(passed=True, resource_cases=len(cases), native_bank_selector=report['native_bank_selector'],
                          image_dimensions=sorted(set((c['width'], c['height']) for c in cases)),
                          bad_resource_image_lookup_rejected=True)))


if __name__ == '__main__':
    main()
