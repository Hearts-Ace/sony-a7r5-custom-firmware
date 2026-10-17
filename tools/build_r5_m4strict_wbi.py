#!/usr/bin/env python3
"""Apply the author's one-byte WBI marker change, with R5 loader evidence.

Offline files only. Does not execute firmware on a camera or change an updater.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor/audit-python'))
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

WBI = ROOT / 'unpacked/r5/firmware/0700_part_image/dev/nflasha5'
BOOT0 = ROOT / 'analysis/r5_live_system_20261014/boot_probe_B/emmc_boot0.raw.img'
ROM = ROOT / 'backups/R5_4.00_20261014_full/ap_bootrom.raw.A.bin'
HASHES = {
    'wbi': '15020d1afe7f1cf40b3822ea0a7426c5c9b40f6330f163d72cf82fb08b1363e8',
    'boot0': '77ff69b4d1ab702c955a4820a7049b2af029c9c165355f00948c3f46eee59ad5',
    'rom': 'f93eaef410a47ec65f3487cd1edf63e1982df77163f3461206118ba5d6ee3fc3',
    'loader': '72f295dd9961ed2b63486060ef377296311f5bd19e3abd846c47316201d31a83',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def load_bootloader():
    raw, rom = BOOT0.read_bytes(), ROM.read_bytes()
    require(sha(raw) == HASHES['boot0'] and sha(rom) == HASHES['rom'], 'Wrong historical R5 boot evidence')
    word = lambda data, offset: struct.unpack_from('<I', data, offset)[0]
    start, address, size, entry = [word(raw, i) for i in (0x68, 0x6c, 0x74, 0x78)]
    require(raw[:4] == b'EXBL' and (start, address, size, entry) == (4, 0xfe040800, 188416, 0xfe049000), 'Unsupported boot layout')
    indices = [word(rom, 0x6984 + i) for i in range(0, 0x100, 4)]
    require(max(indices) < 0x400, 'Invalid ROM key derivation layout')
    # Derivation stays in memory; no key bytes are written to evidence or logs.
    key = bytes(rom[0xb800 + i] for i in indices)
    encrypted = raw[start * 512:start * 512 + size]
    clear = bytearray()
    for offset in range(0, size, 512):
        dec = Cipher(algorithms.AES(key), modes.XTS((start + offset // 512).to_bytes(16, 'little'))).decryptor()
        clear += dec.update(encrypted[offset:offset + 512]) + dec.finalize()
    require(sha(clear) == HASHES['loader'], 'Loader plaintext identity mismatch')
    return bytes(clear), address, entry


def verify_marker_predicate(loader, base):
    """Bind the exact disassembled predicate; derive its four-byte outcomes."""
    require(loader[0xfe066e76 - base:0xfe066e76 - base + 5] == b'WBI2\0', 'Wrong loader marker')
    require(loader[0xfe059c14 - base:0xfe059c58 - base].hex() ==
            'ffc301d1e0230091fe3300f95810009460000034e0031f2a08000014600000b000d83991e1230091e2031e32c3c5ff971f000071e0179f1afe3340f9ffc30191c0035fd6',
            'WBI predicate instructions changed')
    require(sha(loader[0xfe04b34c - base:0xfe04b444 - base]) ==
            'c6d29071dd57d8fbb8d74dd8ec6b08154e5f6bd037684a6cada9a693edfe6ba4',
            'Original strncmp implementation changed')
    # The routine calls the original strncmp with n=4 and returns result==0.
    # This is a semantic projection from observed code, not CPU or camera replay.
    return [{'marker_hex': marker.hex(), 'accepted': marker == b'WBI2',
             'basis': 'derived from exact four-byte strncmp after successful header read'}
            for marker in (b'WBI2', b'WBI3', b'WBI0', b'invl', bytes(4))]


def write_new_or_same(path, data):
    if path.exists():
        require(path.read_bytes() == data, 'Refuse to replace differing evidence: ' + str(path))
    else:
        path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    build = args.build.resolve()
    evidence = build / 'evidence/wbi'
    evidence.mkdir(parents=True, exist_ok=True)
    (build / 'patched').mkdir(parents=True, exist_ok=True)
    destination = build / 'patched/nflasha5'
    require(not destination.exists(), 'Choose a new build output; WBI already exists')
    source = WBI.read_bytes()
    require(sha(source) == HASHES['wbi'] and source[:4] == b'WBI2', 'Wrong original R5 WBI')
    loader, base, entry = load_bootloader()
    cases = verify_marker_predicate(loader, base)
    output = source[:3] + b'3' + source[4:]
    require(len(source) == len(output) and source[:3] == output[:3] and source[4:] == output[4:], 'Unexpected WBI changes')
    write_new_or_same(evidence / 'emmc_loader.plain.bin', loader)
    write_new_or_same(evidence / 'emmc_loader.entry.bin', loader[entry - base:])
    disassembly = []
    decoder = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    for label, start, end in [('WBI2 predicate', 0xfe059c14, 0xfe059c58),
                              ('Original bounded string comparison', 0xfe04b34c, 0xfe04b444),
                              ('R5 eMMC WBI header read', 0xfe05dd80, 0xfe05df80)]:
        disassembly.append(label)
        disassembly.extend(f'{i.address:#x}: {i.bytes.hex()} {i.mnemonic} {i.op_str}'
                           for i in decoder.disasm(loader[start - base:end - base], start))
    write_new_or_same(evidence / 'loader_disassembly.txt', ('\n'.join(disassembly) + '\n').encode())
    destination.write_bytes(output)
    require(sha(destination.read_bytes()) == sha(output), 'WBI file readback failed')
    manifest = {
        'method': 'Erlla 086df3b firmware.py WBI2 -> WBI3; R5 exact header predicate checked',
        'source': str(WBI), 'source_sha256': sha(source), 'output_sha256': sha(output), 'size': len(output),
        'changes': [{'offset': 3, 'old_hex': '32', 'new_hex': '33'}],
        'boot_evidence': {'boot0': str(BOOT0), 'boot0_sha256': HASHES['boot0'], 'bootrom': str(ROM),
                          'bootrom_sha256': HASHES['rom'], 'plaintext_sha256': sha(loader),
                          'load_address': hex(base), 'entrypoint': hex(entry)},
        'predicate': '0xfe059c14; header load 0xfe05dd80; four-byte strncmp 0xfe04b34c; WBI2 literal 0xfe066e76',
        'table_references': ['0xfe064860: wbi_vali -> 0xfe051510 -> predicate',
                             '0xfe0648b0: ssboot -> 0xfe0519f4 -> predicate'],
        'no_bootloader_output_in_package': True, 'no_updater_changes': True, 'camera_io': False,
    }
    verification = {
        'passed': True, 'output_sha256': sha(output), 'only_one_byte_changed': True,
        'original_snapshot_payload_retained': True, 'header_predicate_cases': cases,
        'scope': 'Static exact R5 loader bytes and disassembled four-byte header predicate',
        'hardware_tested': False,
        'limitations': ['The loader is from the saved pre-incident body readback, not a current readback.',
                       'Predicate cases are a semantic projection, not CPU or device execution.',
                       'Rejecting WBI3 as a WBI2 snapshot does not prove successful recovery from this incident.'],
    }
    for name, data in [('manifest.json', manifest), ('verification.json', verification)]:
        (evidence / name).write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps({'output': str(destination), 'output_sha256': sha(output), 'passed': True,
                      'hardware_tested': False, 'camera_io': False}))


if __name__ == '__main__':
    main()
