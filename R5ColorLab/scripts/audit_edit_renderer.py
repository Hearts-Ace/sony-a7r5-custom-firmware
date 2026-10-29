"""Read-only inventory of the installed Sony Edit rendering candidate classes.

No launch, patch, camera IO or RAW rewrite. Derives RTTI/vtable/code anchors
from a digest-bound arm64 thin copy; these are static candidates, not a trace.
"""
from pathlib import Path
import bisect
import hashlib
import json
import re
import struct
import sys
import os
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

HERE = Path(__file__).resolve().parents[1]
OUT = HERE/'evidence/edit_renderer_20261019'
APP = Path(os.environ.get('R5_EDIT_EXECUTABLE','Edit.app/Contents/MacOS/Edit'))
PIN = '43ae5e1cb4bc18a52183b430e02b16a4506b89a907a6fd0feed359fa85a82ce9'
THIN_PIN = 'c250f466835c5380d244de33a6824e9930fe3f250ce9b1d948d5e379cc4c8133'
CLASSES = ['ZcTaskLinearMatrix16', 'ZcTaskLinearMatrix', 'ZcTaskMainGamma',
    'ZcTaskHueSaturation', 'ZcPrivateColorGamma', 'ZcCameraLutMaker4L',
    'ZcCameraLutMakerArgus', 'ZcMainLutMaker', 'ZcTaskSIMDLinearMatrix',
    'ZcTaskSIMDLinearMatrix16', 'ZcTaskSIMDHueSaturation', 'ZcTaskToneCurve',
    'ZcTaskYGamma', 'ARWParser', 'TileDevForARWFull']
TAGS = {0x7842, 0x7844, 0x7845, 0x7800, 0x780f, 0x7806, 0x780c, 0x780d, 0x780e}


class Mach:
    def __init__(self, data):
        self.data = data
        if data[:4] != b'\xcf\xfa\xed\xfe':
            raise ValueError('Expected little endian 64-bit Mach-O')
        self.segments, self.sections = [], []
        at = 32
        functions = None
        for _ in range(struct.unpack_from('<I', data, 16)[0]):
            cmd, size = struct.unpack_from('<II', data, at)
            if cmd == 0x19:
                name = data[at+8:at+24].split(b'\0')[0].decode()
                va, vs, off, fs = struct.unpack_from('<4Q', data, at+24)
                self.segments.append(dict(name=name, va=va, vsize=vs, offset=off, size=fs))
                for i in range(struct.unpack_from('<I', data, at+64)[0]):
                    start = at+72+i*80
                    sect = data[start:start+16].split(b'\0')[0].decode()
                    sv, ss, so = struct.unpack_from('<QQI', data, start+32)
                    self.sections.append(dict(name=sect, segment=name, va=sv, size=ss, offset=so))
            elif cmd == 0x26:
                off, n = struct.unpack_from('<II', data, at+8)
                functions = data[off:off+n]
            at += size
        self.starts = []
        va, value, shift = next(s['va'] for s in self.segments if s['name'] == '__TEXT'), 0, 0
        if functions is not None:
            for b in functions:
                value |= (b & 127) << shift
                if b & 128:
                    shift += 7
                else:
                    if value == 0: break
                    va += value
                    self.starts.append(va)
                    value, shift = 0, 0

    def va(self, offset):
        for s in self.segments:
            if s['offset'] <= offset < s['offset']+s['size']:
                return s['va']+offset-s['offset']
        raise ValueError('Offset outside mapped bytes')

    def off(self, va):
        for s in self.segments:
            if s['va'] <= va < s['va']+s['size']:
                return s['offset']+va-s['va']
        raise ValueError('VA outside mapped bytes')

    def function(self, va):
        i = bisect.bisect_right(self.starts, va)-1
        if i < 0 or i+1 == len(self.starts):
            return None
        return self.starts[i], self.starts[i+1]

    def refs(self, va):
        return [m.start() for m in re.finditer(re.escape(struct.pack('<Q', va)), self.data)
                if m.start() % 8 == 0]


def main():
    if hashlib.sha256(APP.read_bytes()).hexdigest() != PIN:
        raise ValueError('Installed Edit version changed')
    data = (OUT/'Edit.arm64').read_bytes()
    if hashlib.sha256(data).hexdigest() != THIN_PIN:
        raise ValueError('Thin Edit version changed')
    image = Mach(data)
    text = next(s for s in image.sections if s['name'] == '__text')
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    rows, asm, pointer_anchors = [], [], set()
    for name in CLASSES:
        needle = f'N11sony_zhacai{len(name)}{name}E'.encode()+b'\0'
        hits = [m.start() for m in re.finditer(re.escape(needle), data)]
        if len(hits) != 1:
            raise ValueError('RTTI name not unique: '+name)
        name_va = image.va(hits[0])
        type_infos, vtables = [], []
        for ref in image.refs(name_va):
            type_va = image.va(ref)-8
            type_infos.append(hex(type_va))
            for vref in image.refs(type_va):
                if struct.unpack_from('<Q', data, vref-8)[0] != 0:
                    continue  # exclude inheritance references
                methods = []
                for i in range(40):
                    ptr = struct.unpack_from('<Q', data, vref+8+i*8)[0]
                    if not text['va'] <= ptr < text['va']+text['size']:
                        break
                    bounds = image.function(ptr)
                    if not bounds or bounds[0] != ptr:
                        raise ValueError('Vtable pointer is not a function-start record')
                    methods.append(dict(index=i, va=hex(ptr), next_function_va=hex(bounds[1]),
                                        span_bytes=bounds[1]-ptr))
                    code = data[image.off(ptr):image.off(ptr)+(bounds[1]-ptr)]
                    asm.append(f'## {name} method[{i}] VA={ptr:#x} file={image.off(ptr):#x}\n'+
                        '\n'.join(f'{ins.address:#x} {ins.mnemonic} {ins.op_str}'
                                  for ins in md.disasm(code, ptr)))
                vtable_va = image.va(vref)+8
                pointer_anchors.add(vtable_va)
                vtables.append(dict(type_info_slot_va=hex(image.va(vref)),
                    address_point_va=hex(vtable_va), methods=methods))
        rows.append(dict(class_name=name, rtti_name_va=hex(name_va),
                         type_info_candidates=type_infos, vtables=vtables))
    # Single-instruction immediate candidates only. No claim that these use
    # the tags: same small integer could have an unrelated purpose.
    constants, code_refs, calls = [], [], []
    for ins in md.disasm(data[text['offset']:text['offset']+text['size']], text['va']):
        bounds = image.function(ins.address)
        if ins.mnemonic in ('mov', 'movz', 'cmp'):
            for tag in TAGS:
                if re.search(r'#'+re.escape(hex(tag))+r'\b', ins.op_str):
                    constants.append(dict(va=hex(ins.address), instruction=ins.mnemonic+' '+ins.op_str,
                        tag_candidate=hex(tag), function_va=hex(bounds[0]) if bounds else None))
        if ins.mnemonic == 'bl':
            calls.append((ins.address, ins.op_str))
    # Code address materialization: ADRP + ADD within a short linear window.
    # Verify register writes/branches; still an address-reference heuristic.
    instructions = list(md.disasm(data[text['offset']:text['offset']+text['size']], text['va']))
    for i, ins in enumerate(instructions):
        if ins.mnemonic != 'adrp': continue
        reg, addr = ins.op_str.split(', ')
        page = int(addr.lstrip('#'), 16)
        if not any(page <= v < page+4096 for v in pointer_anchors): continue
        for nxt in instructions[i+1:i+9]:
            if nxt.mnemonic == 'add':
                parts = nxt.op_str.split(', ')
                if len(parts) == 3 and parts[1] == reg and parts[2].startswith('#'):
                    target = page+int(parts[2][1:], 0)
                    if target in pointer_anchors:
                        bounds = image.function(nxt.address)
                        code_refs.append(dict(adrp_va=hex(ins.address), use_va=hex(nxt.address),
                            vtable_va=hex(target), function_va=hex(bounds[0]) if bounds else None))
            if nxt.mnemonic in ('b', 'bl', 'br', 'blr', 'ret') or nxt.op_str.split(', ')[0] == reg:
                break
    result = dict(schema='sony-edit-renderer-static-anchors/1', source_sha256=THIN_PIN,
        app_version='4.1.00.03062', function_start_records=len(image.starts),
        sections=image.sections, classes=rows, immediate_tag_candidates=constants,
        vtable_address_materialization_candidates=code_refs,
        user_engineering_assumption='Use Edit creative-look rendering as camera-equivalent target for fitting; equivalence itself is not a prerequisite.',
        application_launched=False, application_modified=False, camera_io=False,
        limits=['RTTI and vtable entries identify candidate roles, not complete pixel semantics.',
            'LC_FUNCTION_STARTS bounds may include padding, not decompiler body evidence.',
            'Immediate matches are tag candidates until caller/dataflow proves their role.',
            'ADRP/ADD scan is a bounded address heuristic, not complete xrefs.',
            'No RAW has been rendered, perturbed or modified by this script.'])
    (OUT/'static_anchors.json').write_text(json.dumps(result, indent=2)+'\n')
    (OUT/'render_tasks.asm').write_text('\n\n'.join(asm)+'\n')
    print(json.dumps(dict(classes=len(rows), immediate_tag_candidates=len(constants),
        vtable_code_candidates=len(code_refs), function_start_records=len(image.starts),
        task_methods={r['class_name']:[v['methods'] for v in r['vtables']]
                      for r in rows if r['class_name'] in ('ZcTaskLinearMatrix16','ZcTaskMainGamma','ZcTaskHueSaturation')},
        camera_io=False), indent=2))


if __name__ == '__main__': main()
