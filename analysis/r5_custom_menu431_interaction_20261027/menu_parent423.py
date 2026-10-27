"""Insert one native menu peer and relocate the PLT RELA table without growth.

No original evidence is edited. The caller passes its new AP image, after
adding the module PT_LOAD. Every original parent record and PLT relocation is
preserved; the strict reverse patch list restores the original prefix.
"""
import hashlib
import io
import struct
from elftools.elf.elffile import ELFFile

GROUP = 0x5053628
MENU_ID = 0x635
DESCRIPTOR = 'r5_filter_menu_descriptor'


def patch_menu_parent(image, rx_file, runtime_code, module_audit):
    image = bytearray(image)
    elf = ELFFile(io.BytesIO(image))
    rx = module_audit['rx']
    descriptor = module_audit['symbols'][DESCRIPTOR]
    rela = elf.get_section_by_name('.rela.dyn')
    plt = elf.get_section_by_name('.rela.plt')
    assert rela['sh_entsize'] == plt['sh_entsize'] == 24
    assert rela['sh_offset']+rela['sh_size'] == plt['sh_offset']
    old_plt = plt.data()
    old_relas = list(struct.iter_unpack('<QQq', rela.data()))
    assert len({a for a, _, _ in old_relas}) == len(old_relas)
    assert not any(a in (GROUP+0x40, GROUP+0x48) for a, _, _ in old_relas if a != GROUP+0x48)
    code_at = (len(runtime_code)+7) & ~7
    appended = bytes(code_at-len(runtime_code))+old_plt
    new_rx_size = len(runtime_code)+len(appended)
    assert new_rx_size <= 65536, 'Menu/RELA copy exceeds mapped RX page'
    plt_va, plt_file = rx+code_at, rx_file+code_at
    assert plt_file+len(old_plt) <= len(image), 'Caller must reserve RX alignment file space'
    changes = []
    def patch(at, after):
        before = bytes(image[at:at+len(after)])
        if before == after: return
        assert len(before) == len(after)
        image[at:at+len(after)] = after
        changes.append(dict(offset=at, before=before.hex(), after=after.hex()))
    def file_at(va):
        for segment in elf.iter_segments():
            if segment['p_type'] == 'PT_LOAD' and segment['p_vaddr'] <= va < segment['p_vaddr']+segment['p_filesz']:
                return segment['p_offset']+va-segment['p_vaddr']
        raise ValueError(hex(va))
    group_file = file_at(GROUP)
    assert struct.unpack_from('<I', image, group_file+8)[0] == 7
    parent = bytes(image[group_file:group_file+0x2e0])
    old_records = [parent[16+i*24:16+(i+1)*24] for i in range(7)]
    assert [struct.unpack_from('<Q', r)[0] for r in old_records] == [0x1f1,0x1f2,0x1f3,0x1f4,0x1f5,0x1f6,0x1f9]
    assert parent[16+7*24:16+8*24] == bytes(24)
    new_records = old_records[:2]+[struct.pack('<3Q', MENU_ID, descriptor, 0)]+old_records[2:]
    patch(group_file+8, struct.pack('<I',8))
    patch(group_file+16, b''.join(new_records))
    moved = []
    move_lo, move_hi = GROUP+16+2*24, GROUP+16+7*24
    for i, (address, info, addend) in enumerate(old_relas):
        if move_lo <= address < move_hi:
            assert info == 1027
            patch(rela['sh_offset']+i*24, struct.pack('<QQq', address+24, info, addend))
            moved.append(dict(before=hex(address), after=hex(address+24), addend=hex(addend)))
    assert len(moved) == 5
    new_target = GROUP+16+2*24+8
    assert new_target == 0x5053670
    # All PLT entries move intact; old location supplies one extra dyn entry.
    patch(plt_file, old_plt)
    patch(plt['sh_offset'], struct.pack('<QQq', new_target, 1027, descriptor))
    dynamic = elf.get_section_by_name('.dynamic')
    dynamic_changed = []
    for i, (tag, value) in enumerate(struct.iter_unpack('<qQ', dynamic.data())):
        after = rela['sh_size']+24 if tag == 8 else plt_va if tag == 23 else None
        if after is not None:
            patch(dynamic['sh_offset']+i*16+8, struct.pack('<Q',after))
            dynamic_changed.append(dict(tag=tag,before=hex(value),after=hex(after)))
    assert {r['tag'] for r in dynamic_changed} == {8,23}
    shoff, shentsize = elf['e_shoff'], elf['e_shentsize']
    for i, section in enumerate(elf.iter_sections()):
        if section.name == '.rela.dyn': patch(shoff+i*shentsize+32,struct.pack('<Q',rela['sh_size']+24))
        if section.name == '.rela.plt':
            patch(shoff+i*shentsize+16,struct.pack('<2Q',plt_va,plt_file))
    # Update the actual new executable PT_LOAD range; module audit stays source-only.
    phoff, phentsize = elf['e_phoff'], elf['e_phentsize']
    for i, segment in enumerate(elf.iter_segments()):
        if segment['p_type']=='PT_LOAD' and segment['p_vaddr']==rx:
            assert segment['p_offset']==rx_file and segment['p_flags']==5
            patch(phoff+i*phentsize+32, struct.pack('<2Q',new_rx_size,new_rx_size))
            break
    else: raise AssertionError('No new RX segment')
    final = ELFFile(io.BytesIO(image))
    new_relas = list(struct.iter_unpack('<QQq', final.get_section_by_name('.rela.dyn').data()))
    assert len(new_relas)==len(old_relas)+1
    assert final.get_section_by_name('.rela.plt').data()==old_plt
    assert len({a for a,_,_ in new_relas})==len(new_relas)
    report = dict(passed=True, menu_id=hex(MENU_ID), group=hex(GROUP),
        descriptor_symbol=DESCRIPTOR, descriptor=hex(descriptor),
        count_before=7,count_after=8,new_index=2,moved_relocations=moved,
        new_relative_target=hex(new_target),new_relative_addend=hex(descriptor),
        plt_bytes=len(old_plt),plt_sha256=hashlib.sha256(old_plt).hexdigest(),
        plt_old_va=hex(plt['sh_addr']),plt_va=hex(plt_va),plt_file=plt_file,
        original_relative_fast_count_unchanged=True,dynamic_changes=dynamic_changed,
        runtime_source_bytes=len(runtime_code),final_rx_bytes=new_rx_size,
        all_old_parent_entries_in_order=True,all_PLT_relocations_exact=True,
        original_prefix_reverse_via_changes=True)
    return image, changes, report
