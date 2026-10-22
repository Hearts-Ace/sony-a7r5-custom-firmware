"""Read-only, exact-source LUT comparison. Outputs remain in this research folder.

No USB, subprocess, firmware patching or device operations. Capstone required.
"""
from pathlib import Path
import hashlib
import json
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
BASE = 0x108000
SOURCES = {
    'r5_ap': ('unpacked/r5/usr_complete/lib/appFw.so', '41bd8f4cda1f44c7038912837737e1ce6a650065f2108061ada30e5c7f9ce7c7'),
    'c2_ap': ('unpacked/c2/usr_complete/lib/appFw.so', '2ea02f7ecbc5bb917316fe8ef4ce5ffd87eb66efaae78ba2ce11420552df539b'),
    'r5_cp': ('unpacked/r5/cp_data/cpapp-b.bin', '3269bf62426339791fcfbe8529698cd4accbe6c3d2ea61cd7c368a90ab7ee7c8'),
    'c2_cp': ('unpacked/c2/cp_data/cpapp-b.bin', 'f5a477588698ef965748903b8959a39ce4f59ffd4aee4d4234ef1670f56a1428'),
    'r5_404_ap': ('build_r5_m4strict_4.04_20261015/patched/appFw.so', '8ee4d5876b7e127df39f8f820b9d21834c300ff895e02ca522636ed4733efc4b'),
    'r5_404_cp': ('build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin', '8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32'),
}
# C2 VA, R5 file offset, exact seed length, bounded disassembly length.
# Analyst-selected homologues, NOT patch locations or device validation.
ANCHORS = {
    'correction_controller': (0x23d380, 0x128da8, 32, 0x8ac),
    'correction_builder': (0x23dc2c, 0x129654, 24, 0x900),
    'correction_uploader': (0x42cd28, 0x30cf44, 32, 0x1f2),
    'correction_bank_copy': (0x78aa20, 0x64f068, 16, 0xae),
    'user_mlut_upload': (BASE+0x44615c, 0xa6b0d6, 0, 0x40),
}

def sha(blob):
    return hashlib.sha256(blob).hexdigest()

def matches(data, seed):
    result, start = [], 0
    while True:
        at = data.find(seed, start)
        if at < 0:
            return result
        if at % 2 == 0:
            result.append(at)
        start = at + 1

def excerpt(data, lo, size):
    """Non-flashable single-section ELF with source VA preserved."""
    code = data[lo:lo+size]
    offset = 0x100
    shstr = b'\0.text\0.shstrtab\0'
    names_at = offset + len(code)
    shoff = (names_at + len(shstr) + 3) & ~3
    out = bytearray(shoff + 120)
    out[:52] = struct.pack('<16sHHIIIIIHHHHHH', b'\x7fELF\x01\x01\x01'+bytes(9), 2, 40, 1,
        BASE+lo+1, 52, shoff, 0x05000000, 52, 32, 1, 40, 3, 2)
    out[52:84] = struct.pack('<8I', 1, offset, BASE+lo, BASE+lo, size, size, 5, 1)
    out[offset:offset+size] = code
    out[names_at:names_at+len(shstr)] = shstr
    out[shoff+40:shoff+80] = struct.pack('<10I', 1, 1, 6, BASE+lo, offset, size, 0, 0, 2, 0)
    out[shoff+80:shoff+120] = struct.pack('<10I', 7, 3, 0, 0, names_at, len(shstr), 0, 0, 1, 0)
    return bytes(out)

def main():
    output = HERE/'evidence'
    output.mkdir(exist_ok=True)
    images, identities = {}, {}
    for name, (path, expected) in SOURCES.items():
        data = (ROOT/path).read_bytes()
        actual = sha(data)
        if actual != expected:
            raise ValueError(f'Source mismatch: {name}')
        identities[name] = dict(path=path, sha256=actual, bytes=len(data))
        if name.endswith('_cp'):
            images[name] = data
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    rows = []
    for name, (cva, rat, seed_size, length) in ANCHORS.items():
        cat = cva-BASE
        c, r, current = images['c2_cp'], images['r5_cp'], images['r5_404_cp']
        hits = matches(r, c[cat:cat+seed_size]) if seed_size else []
        if seed_size and hits != [rat]:
            raise ValueError(f'Unique seed identity changed: {name}: {hits}')
        row = dict(name=name, c2_file_offset=hex(cat), c2_va=hex(cva),
            r5_file_offset=hex(rat), r5_va=hex(BASE+rat), seed_bytes=seed_size,
            seed_matches_r5=[hex(v) for v in hits], inspected_window_bytes=length,
            r5_404_window_unchanged=(r[rat:rat+length] == current[rat:rat+length]),
            confidence='static-homologue-candidate' if seed_size else 'historical-MLUT-anchor-recheck')
        for model, data, at in [('c2',c,cat), ('r5',r,rat)]:
            instructions = list(md.disasm(data[at:at+length], BASE+at))
            text = '\n'.join(f'{i.address:#010x} file={i.address-BASE:#010x} {i.bytes.hex():10} {i.mnemonic} {i.op_str}' for i in instructions)+'\n'
            (output/f'{model}_{name}.asm').write_text(text)
            row[model+'_direct_calls'] = [dict(va=hex(i.address), target=i.op_str)
                for i in instructions if i.mnemonic in ('bl','blx')]
        rows.append(row)
    elf = excerpt(images['r5_cp'], 0x30cf44, 0x1f2)
    (output/'r5_correction_uploader.elf').write_bytes(elf)
    permutation = images['c2_cp'][0xec7c20-BASE:0xec7c20-BASE+810]
    if sorted(struct.unpack('<405H', permutation)) != list(range(405)):
        raise ValueError('C2 hardware permutation differs')
    if matches(images['r5_cp'], permutation) != [0xd841d8]:
        raise ValueError('R5 hardware permutation differs')
    if images['r5_cp'][0xd841d8:0xd841d8+810] != images['r5_404_cp'][0xd841d8:0xd841d8+810]:
        raise ValueError('4.04 permutation differs')
    # Compare every decoded copy-function instruction, excluding relocated
    # direct calls. This checks the actual eight transfer chunks, not a title.
    ccopy = list(md.disasm(images['c2_cp'][0x682a20:0x682a20+0xae], 0x78aa20))
    rcopy = list(md.disasm(images['r5_cp'][0x64f068:0x64f068+0xae], 0x757068))
    normalized = lambda ins: [(i.mnemonic, '<relocated-call>' if i.mnemonic in ('bl','blx') else i.op_str) for i in ins]
    if normalized(ccopy) != normalized(rcopy):
        raise ValueError('Bank-copy instruction structure differs')
    result = dict(schema='r5-custom-lut-static-audit/1', camera_io=False, firmware_modified=False,
        sources=identities, anchors=rows,
        bank_copy=dict(instructions_equal_excluding_call_targets=True, inspected_function_bytes=0xae,
            chunks=[0x12c,0xf0,0xf0,0xc0,0xc8,0xa0,0xa0,0x80], total_bytes=1620,
            c2_memcpy_va='0x61e60c', r5_memcpy_va='0x5f51bc'),
        permutation=dict(entries=405, sha256=sha(permutation), c2_va='0xec7c20',
            r5_va='0xe8c1d8', r5_file_offset='0xd841d8', byte_identical=True,
            r5_404_unchanged=True, limitation='Static table equality, not proof of runtime hardware binding'),
        excerpt=dict(path='r5_correction_uploader.elf', sha256=sha(elf),
            source='r5_cp', source_file_offset='0x30cf44', source_length=0x1f2,
            load_va='0x414f44', purpose='Offline REA only; not firmware'),
        limits=['Unique short seed is not a complete semantic equivalence proof.',
            'Disassembly windows may include data or partial functions; lengths are analyst bounds.',
            'No live execution, native R5 builder replay, calibration, performance or photo/video acceptance.'])
    (output/'source_audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(source_count=len(identities), anchor_count=len(rows),
        all_404_windows_unchanged=all(r['r5_404_window_unchanged'] for r in rows),
        bank_copy=result['bank_copy'], permutation=result['permutation'], camera_io=False), indent=2))

if __name__ == '__main__':
    main()
