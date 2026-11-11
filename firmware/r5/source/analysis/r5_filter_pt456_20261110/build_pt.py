#!/usr/bin/env python3
"""Add PT selection at one existing private filter-worker request call."""
from pathlib import Path
import argparse, hashlib, io, json, struct, subprocess, sys

H = Path(__file__).resolve().parent
ROOT = H.parents[1]
sys.path.insert(0, str(ROOT / 'projects/firmware/development/shutter-sound-recovery455/src/lib'))
from strict_ap_link import link, branch
from elftools.elf.elffile import ELFFile

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--audit', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    assert __debug__ and not a.output.exists()
    raw = a.base.read_bytes()
    e = ELFFile(io.BytesIO(raw)); segs = list(e.iter_segments())
    audit = json.loads(a.audit.read_text())
    obj = a.audit.parent / 'objects/r5_filter_runtime423.o'
    bindings = {}
    with obj.open('rb') as f:
        o = ELFFile(f)
        for symbol in o.get_section_by_name('.symtab').iter_symbols():
            if symbol.name in ('desired', 'command_state', 'command_kind'):
                rows = [r for r in audit['sections'] if r['index'] == symbol['st_shndx'] and
                        Path(r['object']).name == obj.name]
                assert len(rows) == 1 and rows[0]['space'] == 'bss'
                bindings['r5_filter_pt_' + symbol.name] = int(rows[0]['va'], 16) + symbol['st_value']
    assert len(bindings) == 3
    native = {**bindings, 'r5_filter_pt_native_get': 0x1c05f18,
              'r5_filter_pt_native_set': 0x1c6f208,
              'r5_native_creative_sequence_request': 0x24b0780}
    calls = [r for r in audit['relocations'] if r['symbol'] == 'r5_native_creative_sequence_request' and
             Path(r['source_object']).name == obj.name and r['kind'] == 283]
    assert len(calls) == 1
    site = int(calls[0]['site'], 16)
    refresh = [r for r in audit['sections'] if Path(r['object']).name == obj.name and r['name'] == '.text.refresh425']
    assert len(refresh) == 1 and int(refresh[0]['va'], 16) <= site < int(refresh[0]['va'], 16) + refresh[0]['size']
    ri, rs = next((i, s) for i, s in enumerate(segs) if s['p_type'] == 'PT_LOAD' and s['p_vaddr'] == 0x8ee0000)
    ws = next(s for s in segs if s['p_type'] == 'PT_LOAD' and s['p_vaddr'] == 0x8ef0000)
    rx = (rs['p_vaddr'] + rs['p_filesz'] + 15) & -16
    rw = (ws['p_vaddr'] + ws['p_memsz'] + 15) & -16
    a.output.mkdir(parents=True)
    source = H / 'r5_filter_pt_sequence.c'; output_obj = a.output / 'pt.o'
    cmd = ['clang', '--target=aarch64-none-elf', '-Oz', '-ffreestanding', '-fno-builtin',
           '-fno-stack-protector', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
           '-mgeneral-regs-only', '-mno-outline-atomics', '-ffunction-sections', '-fdata-sections',
           '-Wall', '-Wextra', '-Werror', '-c', str(source), '-o', str(output_obj)]
    subprocess.run(cmd, check=True)
    code, data, memory, sy, relocs, layout = link([output_obj], rx, rw, b'', native)
    assert not data and not memory and rx + len(code) <= ws['p_vaddr']
    assert all(r['kind'] != 257 for r in relocs)
    def off(va, n=4):
        for s in segs:
            if s['p_type'] == 'PT_LOAD' and s['p_vaddr'] <= va and va + n <= s['p_vaddr'] + s['p_filesz']:
                return s['p_offset'] + va - s['p_vaddr']
        raise ValueError(hex(va))
    assert raw[off(site):off(site)+4] == branch(site, native['r5_native_creative_sequence_request'], True)
    image = bytearray(raw); patches = []
    def edit(at, new, reason):
        old = bytes(image[at:at+len(new)]); assert len(old) == len(new)
        image[at:at+len(new)] = new
        patches.append(dict(offset=at, before=old.hex(), after=new.hex(), reason=reason))
    at = rs['p_offset'] + rx - rs['p_vaddr']
    assert raw[at:at+len(code)] == bytes(len(code))
    edit(at, code, 'PT helper in existing zero RX padding, no data/state allocation')
    size = rx + len(code) - rs['p_vaddr']
    edit(e['e_phoff'] + ri*56 + 32, struct.pack('<QQ', size, size), 'Extend existing RX file/memory size only')
    edit(off(site), branch(site, sy['r5_filter_pt_sequence_request'], True), 'One private refresh425 call; retain original request via helper')
    reverse = bytearray(image)
    for r in reversed(patches):
        reverse[r['offset']:r['offset']+len(bytes.fromhex(r['before']))] = bytes.fromhex(r['before'])
    assert reverse == raw
    target = a.output / 'appFw-NONINSTALLABLE.so'; target.write_bytes(image)
    (a.output / 'rx.bin').write_bytes(code)
    result = dict(passed=True, version='4.56', base_sha256=sha(a.base), sha256=sha(target),
                  rx=rx, rx_bytes=len(code), bss_bytes=memory, symbols=sy, native_bindings=native,
                  patches=patches, relocations=relocs, layout=layout, reverse_exact=True,
                  private_refresh_call=site, source_sha256=sha(source), builder_sha256=sha(Path(__file__)),
                  audit_sha256=sha(a.audit), runtime_object_sha256=sha(obj), command=cmd,
                  camera_io=False, device_tested=False)
    (a.output / 'build.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('passed', 'sha256', 'rx_bytes', 'bss_bytes', 'private_refresh_call')}))

if __name__ == '__main__':
    main()
