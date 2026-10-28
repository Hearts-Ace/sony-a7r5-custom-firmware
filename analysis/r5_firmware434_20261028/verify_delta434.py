"""Verify the complete 4.33 -> 4.34 AP delta and preserved live code paths."""
from pathlib import Path
import hashlib,io,json,sys,re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=ROOT/'analysis/r5_firmware433_20261028'
STARTUP=ROOT/'analysis/r5_custom_menu430_startup_20261027'
sys.path.insert(0,str(HERE/'fn'))
from patch_fn434 import apply_fn_patch
sys.path.insert(0,str(ROOT/'vendor/audit-python'))
from elftools.elf.elffile import ELFFile

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())

def main():
    baseline=OLD/'ap/appFw.so';candidate=HERE/'ap/appFw.so'
    assert sha(baseline)=='65bd99095f626f990890156c0e536d56394c75313452caa451322e1148c1faec'
    build=read(HERE/'ap/ap_build.json');ledger=build['Fn_registration']
    raw=bytearray(candidate.read_bytes())
    for row in ledger['patches']:
        off=row['file_offset'];after=bytes.fromhex(row['after']);before=bytes.fromhex(row['before'])
        assert raw[off:off+len(after)]==after
        raw[off:off+len(before)]=before
    expected,recomputed_ledger=apply_fn_patch(raw)
    assert candidate.read_bytes()==expected and recomputed_ledger==ledger
    assert ledger['changed_bytes']==41 and ledger['added_rx_bytes']==ledger['added_bss_bytes']==0
    unchanged=[]
    for directory in ('import','menu_research'):
        old_files={p.name for p in (OLD/directory).iterdir() if p.suffix in ('.c','.h','.S')}
        new_files={p.name for p in (HERE/directory).iterdir() if p.suffix in ('.c','.h','.S')}
        added={'r5_filter_menu_icon434.S'} if directory=='menu_research' else set()
        assert new_files==old_files|added
        for name in sorted(old_files):
            before,after=OLD/directory/name,HERE/directory/name
            if directory=='menu_research' and name=='r5_filter_menu423.c':
                assert before.read_bytes()!=after.read_bytes()
                text=after.read_text()
                # Only remove the invalid image fallback; the same resource
                # remains valid as help text in +0x0c.
                strip=lambda s:re.sub(r'/\*.*?\*/','',s,flags=re.S)
                expected=before.read_text().replace('put32(d,0x60,0x021c6410u)','put32(d,0x60,~0u)')
                assert strip(text)==strip(expected)
                assert 'put32(d,0x0c,0x021c6410u)' in text
            else:
                assert before.read_bytes()==after.read_bytes(),str(after)
                unchanged.append(dict(path=str(after.relative_to(ROOT)),sha256=sha(after)))
    # The emitted compiler objects independently constrain the executable
    # change to initialize(); relinking may update addresses in callers.
    compiler_objects=[]
    before_objects={p.name:p for p in (OLD/'import/objects').glob('*.o')}
    after_objects={p.name:p for p in (HERE/'import/objects').glob('*.o')}
    icon_object='r5_filter_menu_icon434_asm.o'
    assert set(after_objects)==set(before_objects)|{icon_object} and len(after_objects)==24
    for name,after in sorted(after_objects.items()):
        if name==icon_object:
            elf=ELFFile(io.BytesIO(after.read_bytes()))
            section=elf.get_section_by_name('.text.r5_filter_menu_icon_query434')
            assert section.data().hex()=='3fd4187141000054c13c80523f90327100000014'
            rel=elf.get_section_by_name('.rela.text.r5_filter_menu_icon_query434')
            syms=elf.get_section(rel['sh_link'])
            assert [(r['r_offset'],r['r_info_type'],syms.get_symbol(r['r_info_sym']).name,r['r_addend'])for r in rel.iter_relocations()]==[(16,282,'r5_native_menu_icon_continue434',0)]
            compiler_objects.append(dict(path=str(after.relative_to(ROOT)),sha256=sha(after)))
            continue
        before=before_objects[name]
        if name!='r5_filter_menu423.o':assert before.read_bytes()==after.read_bytes(),name
        else:
            old_elf=ELFFile(io.BytesIO(before.read_bytes()));new_elf=ELFFile(io.BytesIO(after.read_bytes()))
            a={s.name:s.data()for s in old_elf.iter_sections()};b={s.name:s.data()for s in new_elf.iter_sections()}
            assert {key for key in b if key.startswith('.text.')}=={key for key in a if key.startswith('.text.')}
            # Existing code outside initialization must remain exact. Relocation
            # records are compared by target symbol, independent of symbol order.
            for key in a:
                if key.startswith('.text.') and key!='.text.initialize':
                    assert a[key]==b[key],key
            def relocation_targets(elf,section):
                rel=elf.get_section_by_name(section)
                if rel is None:return []
                syms=elf.get_section(rel['sh_link'])
                return [(r['r_offset'],r['r_info_type'],syms.get_symbol(r['r_info_sym']).name,r['r_addend'])for r in rel.iter_relocations()]
            for section in old_elf.iter_sections():
                key=section.name
                if key.startswith('.rela.text.') and key!='.rela.text.initialize':
                    assert relocation_targets(old_elf,key)==relocation_targets(new_elf,key),key
        for p in (before,after):compiler_objects.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(p)))
    startup_names=('import/r5_filter_runtime423.c','import/r5_grid420_log.c','import/r5_runtime_session.c','import/r5_stage413_thread.c')
    for name in startup_names:assert sha(HERE/name)==sha(STARTUP/name)
    audit=read(HERE/'import/module_audit.json');build=read(HERE/'ap/ap_build.json')
    assert audit['version']==build['version']=='4.34'
    for name,digest in audit['sources'].items():assert sha(ROOT/name)==digest,name
    ap=sha(candidate)
    assert build['AP_sha256']==ap and build['Fn_registration']['patched_sha256']==ap
    assert build['rx_bytes']==63480 and audit['bss_bytes']==136384
    assert build['reverse_to407_exact'] and build['only_AP_payload_changed']
    old_hooks=read(OLD/'menu_research/menu_hooks.json')
    new_hooks=read(HERE/'menu_research/menu_hooks.json')
    expected_hooks=json.loads(json.dumps(old_hooks))
    expected_hooks['native_symbols']['r5_native_menu_icon_continue434']=0x1bd63b8
    expected_hooks['calls'].append(dict(va='0x1bd63b4',before='3f903271',symbol='r5_filter_menu_icon_query434',link=False))
    assert new_hooks==expected_hooks
    sys.path.insert(0,str(ROOT/'research/r5_custom_lut/evidence/sd405_ap_native_directory_binding'))
    from strict_ap_link import branch
    wrapper=audit['symbols']['r5_filter_menu_icon_query434']
    actual=candidate.read_bytes();rxfile=build['rx_file']
    off=rxfile+wrapper-audit['rx']
    assert actual[0x1bd63b4:0x1bd63b8]==branch(0x1bd63b4,wrapper)
    assert actual[off:off+16].hex()=='3fd4187141000054c13c80523f903271'
    assert actual[off+16:off+20]==branch(wrapper+16,0x1bd63b8)
    original=(ROOT/'assets/firmware/a8d5cd444bf0-appFw.so').read_bytes()
    reverse=bytearray(actual[:len(original)])
    for row in reversed(build['patches']):
        at=row['offset'];before=bytes.fromhex(row['before']);after=bytes.fromhex(row['after'])
        if at>=len(original):continue
        assert reverse[at:at+len(after)]==after
        reverse[at:at+len(before)]=before
    assert reverse==original
    for row in read(HERE/'baseline433_sources.json')['rows']:
        assert sha(ROOT/row['source'])==row['source_sha256'],row['source']
    sd=read(HERE/'sync_tests/sd430_replay.json')
    worker=read(HERE/'sync_tests/worker425_verified.json')
    grid=read(HERE/'sync_tests/grid430_verified.json')
    cross=read(HERE/'crosscore/ap_cp425.json')
    for r in (sd,worker,grid,cross):assert r['passed'] and r['AP_sha256']==ap
    assert sd['cases']==180 and worker['cases']==15 and len(grid['cases'])==7
    assert cross['actual_selects']==30 and cross['actual_AP_sender_inbound_and_CP_receive_task_executed']
    assert cross['CP_sha256']=='8b38e753f34b1667d79b69079d911b9e6595f1ce1b873cb8e014437c6b4c494d'
    for bias in ('0x0','0x40000000'):
        by={r['scenario']:r for r in sd['results'] if r['bias']==bias}
        assert by['retry_bank_once']['same_boot_bank_attempts']==2
        assert by['retry_bank_never']['same_boot_bank_attempts']==3
        assert by['second_slot_pending']['poll_attempts']==1
        assert by['same_file']['internal_diagnostics'][7]==1
        for name in ('same_full_name_changed','same_grid_changed'):
            assert by[name]['internal_diagnostics'][7]==0
        assert by['no_card']['descriptor_free_selection_services']>=290
        assert any(q['phase']==1 and q['terminal']==0 for q in by['late_card']['selection_yields'])
    assert len(sd['warm_media_results'])==2 and all(r['same_boot_fresh_media_revalidated'] for r in sd['warm_media_results'])
    assert len(cross['same_boot_lost_seal_recovery'])==2
    assert all(r['completed_without_CP_restart'] for r in cross['same_boot_lost_seal_recovery'])
    out=dict(passed=True,version='4.34',AP_sha256=ap,CP_sha256=cross['CP_sha256'],
             baseline433_AP_sha256=sha(baseline),native_Fn_candidate_delta_verified=True,
             other_compiler_objects_exact433=True,only_dynamic_icon_source_changed=True,
             other_production_sources_exact433=True,menu_icon_queries_forward_to_creative_look=True,
             reverse_original_native_prefix_exact=True,compiler_objects=compiler_objects,
             unchanged_production_sources=unchanged,Fn_patch=ledger,
             startup_production_sources_exact430=True,actual_final_AP_SD_cases=180,
             worker_cases=15,grid_wait_cases=7,full_content_deduplication=True,
             same_boot_bank_retry=True,ready_slot_not_blocked_by_other_slot=True,
             CP_grid_lifecycle_exact423=True,camera_io=False,
             limitations=['The descriptor image fallback is removed and a20-byte image-query wrapper is added. Existing functions except initialization and other22 compiler objects match4.33. Relinking adjusts affected addresses.',
                          'New BK4 defaults and native migration are validated by separate feature receipts.',
                          'No physical Fn/LCD, camera event timing, actual upgrade, cold boot or JPG acceptance.'])
    (HERE/'delta434_verified.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=True,AP_sha256=ap,Fn_data_different_bytes=41,only_dynamic_icon_source_changed=True)))

if __name__=='__main__':main()
