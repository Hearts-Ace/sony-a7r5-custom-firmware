#!/usr/bin/env python3
"""Read only local R5/M4/FX2 inputs; reconstruct author CP and bind comparisons."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / 'analysis/erlla_a7m4_comparison_20261015/upstream/Erlla-sony-a7m4-custom-firmware-086df3b'
sys.path.insert(0, str(UP))
from a7m4.fat import Fat
from a7m4.fl23 import patch_program
from sony_bk4 import find_banks
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from build_r5_m4strict_cp import OUT, SOURCE, SOURCE_SHA


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=OUT)
    args = parser.parse_args()
    out = args.build.resolve() / 'evidence/cp'
    out.mkdir(parents=True, exist_ok=True)
    m4 = Fat((ROOT / 'analysis/m4_stock_package_compare_20261015/unpacked/firmware/0700_part_image/dev/nflasha8').read_bytes()).read('CPAPP-B.BIN')
    r5, fx2 = SOURCE.read_bytes(), (ROOT/'unpacked/fx2/cp_data/cpapp-b.bin').read_bytes()
    recipe_path = UP / 'a7m4/profiles/fl23/cp-v7-recipe.json'
    recipe = json.loads(recipe_path.read_text())
    donor_template = sorted((ROOT/'unpacked/fx2/firmware/0110_backup').rglob('*ALLLANG.bin'))[0]
    props = {}
    for bank in find_banks(donor_template.read_bytes()):
        for key in (0x02a40001, 0x02a4000d):
            try:
                props[key] = bank.property(key).data
            except KeyError:
                pass
    author = patch_program(m4, recipe, {'fx2_cp':fx2, 'fx2_cc1':props[0x02a40001], 'fx2_block13':props[0x02a4000d]})
    assert sha(r5) == SOURCE_SHA
    final = (args.build/'patched/cpapp-b.bin').read_bytes()
    (out/'m4-stock-cp.bin').write_bytes(m4)
    (out/'m4-author-v7-cp.bin').write_bytes(author)
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    sections = []
    for label, data, ranges in (
        ('M4 stock', m4, [(0x2c911a, 0xa4), (0x59ce88, 0x66), (0x11dab4, 0x20), (0x11deb6, 0x12)]),
        ('M4 author v7', author, [(0x2c911a, 0xa4), (0x59ce88, 0x66), (0xa08f10, 0x5c), (0x11dab4, 0x20), (0x11deb6, 0x12)]),
        ('R5 stock', r5, [(0x30c05e, 0xa4), (0x616670, 0x78)]),
        ('R5 final', final, [(0x30c05e, 0xa4), (0x616670, 0x78), (0xae73cc, 0x20)]),
    ):
        for at, size in ranges:
            sections.append(label+' file '+hex(at)+'\n'+'\n'.join(f'{i.address:#010x} {i.bytes.hex():12s} {i.mnemonic} {i.op_str}' for i in md.disasm(data[at:at+size], at)))
    (out/'reference-disassembly.txt').write_text('\n\n'.join(sections)+'\n')
    # Native record spacing and actual consumers distinguish M4 padding from
    # the R5 u32 tail field. Do not assign hardware semantics to that field.
    native = {}
    for name, data, table, count, size in (('M4',m4,0xeb3a78,47,572),('R5',r5,0x1004fa8,47,576),('FX2',fx2,0x11130d4,52,580)):
        ptrs = set()
        for idx in range(count):
            ptrs.update(struct.unpack_from('<7I',data,table+idx*28))
        ptrs.discard(0)
        tails = Counter(data[p-0x108000+0x238:p-0x108000+size].hex() for p in ptrs)
        native[name] = {'native_record_size':size,'nonnull_unique_records':len(ptrs),'record_tails':dict(tails)}
    recipe_curve_ops = [x for x in recipe['donor_operations'] if x.get('source')=='fx2_cp' and not x.get('name','').startswith('retained')]
    manifest = json.loads((out/'manifest.json').read_text())
    comparisons=[]
    for r5curve,m4curve in zip(manifest['gamma']['curves'], recipe_curve_ops):
        r5at=int(r5curve['target_file_offset'],16);m4at=m4curve['offset']
        assert final[r5at:r5at+572] == author[m4at:m4at+572]
        assert author[m4at+572:m4at+576] == bytes(4)
        assert final[r5at+572:r5at+576] == struct.pack('<I',2)
        comparisons.append({'name':r5curve['name'],'first_572_bytes_equal_author':True,'M4_padding_u32':0,'R5_consumed_tail_u32':2})
    for row in manifest['cc1_direct_coefficients']['records']:
        bank=row['bank']
        op=next(x for x in recipe['donor_operations'] if x.get('name')==f'bank {bank}')
        r5at=int(row['offset'],16)
        assert final[r5at:r5at+48]==author[op['offset']:op['offset']+48]
    result={'camera_io':False,'passed':True,'source_sha256':sha(r5),'output_sha256':sha(final),
            'upstream_commit':'086df3b1e33dfa0206553ac2bb003535c58ddb80','recipe_sha256':sha(recipe_path.read_bytes()),
            'm4_source_sha256':sha(m4),'m4_author_reconstructed_sha256':sha(author),'author_recipe_exact_reproduction':True,
            'gamma_record_comparison':comparisons,'native_record_tail_evidence':native,'four_embedded_coefficient_rows_equal_author':True,
            'limits':['Static structure, exact bytes and recipe reproduction; no camera/ISP execution.',
                      'M4 only reads bytes +0x238/+0x239. R5 loads byte +0x238 and u32 +0x23c. Complete hardware meaning of u32 is not established.']}
    (out/'reference-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('passed','source_sha256','output_sha256','m4_author_reconstructed_sha256','author_recipe_exact_reproduction','four_embedded_coefficient_rows_equal_author')}))


if __name__ == '__main__':
    main()
