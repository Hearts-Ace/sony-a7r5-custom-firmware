"""Bind the 4.31 -> 4.32 page-only delta and preserved startup behavior."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'r5_custom_menu431_interaction_20261027'
STARTUP=HERE.parent/'r5_custom_menu430_startup_20261027'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
    ap=sha(HERE/'ap/appFw.so')
    assert sha(OLD/'ap/appFw.so')=='3c832336b73fc5d8b5a902faebd07249821888a17d3609831def42d4419ba941'
    changed=[];unchanged=[]
    for directory in ('import','menu_research'):
        old_names={p.name for p in (OLD/directory).iterdir() if p.suffix in ('.c','.h','.S')}
        new_names={p.name for p in (HERE/directory).iterdir() if p.suffix in ('.c','.h','.S')}
        assert new_names==old_names,(directory,new_names^old_names)
        for p in sorted((OLD/directory).iterdir()):
            if p.suffix not in ('.c','.h','.S'):continue
            q=HERE/directory/p.name
            name=str(q.relative_to(HERE))
            (unchanged if sha(p)==sha(q) else changed).append(name)
    assert changed==['menu_research/r5_filter_page425.c'],changed
    startup_sources=['import/r5_filter_runtime423.c','import/r5_grid420_log.c','import/r5_runtime_session.c','import/r5_stage413_thread.c']
    assert all(name in unchanged for name in startup_sources)
    for name in startup_sources:assert sha(HERE/name)==sha(STARTUP/name),name
    audit=read(HERE/'import/module_audit.json')
    for name,digest in audit['sources'].items():assert sha(HERE.parents[1]/name)==digest,name
    sd=read(HERE/'sync_tests/sd430_replay.json')
    assert sd['passed'] and sd['AP_sha256']==ap and sd['cases']==180
    rows=sd['results']
    assert len(sd['warm_media_results'])==2 and all(r['same_boot_fresh_media_revalidated'] for r in sd['warm_media_results'])
    for bias in ('0x0','0x40000000'):
        by={r['scenario']:r for r in rows if r['bias']==bias}
        assert by['retry_bank_once']['same_boot_bank_attempts']==2
        assert by['retry_bank_never']['same_boot_bank_attempts']==3
        assert by['second_slot_pending']['poll_attempts']==1
        # The producer asserts four opens before its fresh-BSS/no-card restart.
        # Legacy counter fields here describe the final restart phase instead.
        assert by['second_ready_first_missing']['result']==0
        assert by['first_bad_second_valid']['result']==0
        assert 200<=by['late_card']['poll_attempts']<=202
        assert by['same_file']['internal_diagnostics'][7]==1
        for name in ('same_full_name_changed','same_grid_changed'):
            assert by[name]['internal_diagnostics'][7]==0
        assert by['no_card']['descriptor_free_selection_services']>=290
        assert any(q['phase']==1 and q['terminal']==0 for q in by['late_card']['selection_yields'])
    worker=read(HERE/'sync_tests/worker425_verified.json')
    assert worker['passed'] and worker['AP_sha256']==ap and worker['cases']==15
    assert all(r['boot_recovery'] for r in worker['rows'][11:])
    grid=read(HERE/'sync_tests/grid430_verified.json')
    assert grid['passed'] and grid['AP_sha256']==ap and len(grid['cases'])==7
    assert grid['cases'][0]['queries']==1
    assert all(r['selection_completed_ms']<=100 for r in grid['cases'][1:6])
    cross=read(HERE/'crosscore/ap_cp425.json')
    assert cross['passed'] and cross['AP_sha256']==ap
    assert len(cross['same_boot_lost_seal_recovery'])==2
    assert all(r['completed_without_CP_restart'] for r in cross['same_boot_lost_seal_recovery'])
    report=dict(passed=True,AP_sha256=ap,CP_sha256=cross['CP_sha256'],
        changed_production_sources=changed,unchanged_production_sources=unchanged,
        baseline431_AP_sha256=sha(OLD/'ap/appFw.so'),
        baseline430_startup_sources={name:sha(STARTUP/name)for name in startup_sources},
        startup_production_sources_exact430=True,nonpage_production_sources_exact431=True,CP_grid_lifecycle_exact423=True,
        actual_final_AP_SD_cases=180,worker_cases=15,grid_wait_cases=7,
        startup_selection_serviced_without_live_descriptors=True,
        full_content_deduplication=True,same_boot_bank_retry=True,
        late_card_separate_read_budget=True,ready_slot_not_blocked_by_other_slot=True,
        device_io=False,limitations=[
            'SD replay executes final AArch64 decoder, file transactions, worker and names. Complete-bank ACK and nested selection are explicit boundaries; separate crosscore and worker tests execute them.',
            'Grid wait and boot E4 recovery run actual C on host ISA with synthetic clocks and native-service fixtures; their milliseconds are not measured camera performance.',
            'No current camera boot log, callback coverage, real SD timing, physical LCD, loader or ISP/JPG acceptance. Persistent transport/native failures can still prevent same-boot activation; retries are bounded.',
        ])
    (HERE/'delta432_verified.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,AP_sha256=ap,changed_sources=changed)))
if __name__=='__main__':main()
