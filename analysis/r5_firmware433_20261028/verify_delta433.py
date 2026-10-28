"""Verify the complete 4.32 -> 4.33 AP delta and preserved live code paths."""
from pathlib import Path
import hashlib,io,json,sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=ROOT/'analysis/r5_custom_menu432_wheel_20261028'
STARTUP=ROOT/'analysis/r5_custom_menu430_startup_20261027'
sys.path.insert(0,str(HERE/'fn'))
from patch_fn433 import apply_fn_patch
sys.path.insert(0,str(ROOT/'vendor/audit-python'))
from elftools.elf.elffile import ELFFile

ICON_OLD=' put32(d,4,~0u);put32(d,8,~0u);put32(d,0x0c,~0u);put32(d,0x10,~0u);'
ICON_NEW=''' /* Reuse stock Creative Look descriptor 0x5858b08 +0x0c. The menu
  * glyph and Fn fallback glyph share the existing native image resource. */
 put32(d,4,~0u);put32(d,8,~0u);put32(d,0x0c,0x021c6410u);put32(d,0x10,~0u);'''

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())

def main():
    baseline=OLD/'ap/appFw.so';candidate=HERE/'ap/appFw.so'
    assert sha(baseline)=='a68bdc37ad95c1254e0d70bbab9531f686ed9436fbb303fe5541dcaa6ee1d89a'
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
        assert old_files==new_files
        for name in sorted(old_files):
            before,after=OLD/directory/name,HERE/directory/name
            if directory=='menu_research' and name=='r5_filter_menu423.c':
                old=before.read_text()
                assert old.count(ICON_OLD)==1
                expected=old.replace(ICON_OLD,ICON_NEW).replace('put32(d,0x60,~0u);','put32(d,0x60,0x021c6410u);')
                assert after.read_text()==expected,str(after)
            else:
                assert before.read_bytes()==after.read_bytes(),str(after)
                unchanged.append(dict(path=str(after.relative_to(ROOT)),sha256=sha(after)))
    # The emitted compiler objects independently constrain the executable
    # change to initialize(); relinking may update addresses in callers.
    compiler_objects=[]
    before_objects={p.name:p for p in (OLD/'import/objects').glob('*.o')}
    after_objects={p.name:p for p in (HERE/'import/objects').glob('*.o')}
    assert set(before_objects)==set(after_objects) and len(after_objects)==23
    for name,after in sorted(after_objects.items()):
        before=before_objects[name]
        if name!='r5_filter_menu423.o':assert before.read_bytes()==after.read_bytes(),name
        else:
            old_elf=ELFFile(io.BytesIO(before.read_bytes()));new_elf=ELFFile(io.BytesIO(after.read_bytes()))
            a={s.name:s.data()for s in old_elf.iter_sections()};b={s.name:s.data()for s in new_elf.iter_sections()}
            assert set(a)==set(b)
            changed={key for key in a if a[key]!=b[key]}
            assert changed=={'.text.initialize','.rela.text.initialize','.symtab'}
            def relocation_targets(elf):
                rel=elf.get_section_by_name('.rela.text.initialize')
                syms=elf.get_section(rel['sh_link'])
                return [(r['r_info_type'],syms.get_symbol(r['r_info_sym']).name,r['r_addend'])for r in rel.iter_relocations()]
            assert relocation_targets(old_elf)==relocation_targets(new_elf)
        for p in (before,after):compiler_objects.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(p)))
    startup_names=('import/r5_filter_runtime423.c','import/r5_grid420_log.c','import/r5_runtime_session.c','import/r5_stage413_thread.c')
    for name in startup_names:assert sha(HERE/name)==sha(STARTUP/name)
    audit=read(HERE/'import/module_audit.json');build=read(HERE/'ap/ap_build.json')
    assert audit['version']==build['version']=='4.33'
    for name,digest in audit['sources'].items():assert sha(ROOT/name)==digest,name
    ap=sha(candidate)
    assert build['AP_sha256']==ap and build['Fn_registration']['patched_sha256']==ap
    assert build['rx_bytes']==63464 and audit['bss_bytes']==136384
    assert build['reverse_to407_exact'] and build['only_AP_payload_changed']
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
    out=dict(passed=True,version='4.33',AP_sha256=ap,CP_sha256=cross['CP_sha256'],
             baseline432_AP_sha256=sha(baseline),native_Fn_candidate_delta_verified=True,
             other_compiler_objects_exact432=True,only_initializer_object_changed=True,
             other_production_sources_exact432=True,menu_source_only_two_icon_constants=True,
             reverse_original_native_prefix_exact=True,compiler_objects=compiler_objects,
             unchanged_production_sources=unchanged,Fn_patch=ledger,
             startup_production_sources_exact430=True,actual_final_AP_SD_cases=180,
             worker_cases=15,grid_wait_cases=7,full_content_deduplication=True,
             same_boot_bank_retry=True,ready_slot_not_blocked_by_other_slot=True,
             CP_grid_lifecycle_exact423=True,camera_io=False,
             limitations=['The only source change is two menu descriptor icon constants; all other compiler objects match4.32. Relinking adjusts affected addresses.',
                          'New BK4 defaults and native migration are validated by separate feature receipts.',
                          'No physical Fn/LCD, camera event timing, actual upgrade, cold boot or JPG acceptance.'])
    (HERE/'delta433_verified.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=True,AP_sha256=ap,Fn_data_different_bytes=41,only_initializer_object_changed=True)))

if __name__=='__main__':main()
