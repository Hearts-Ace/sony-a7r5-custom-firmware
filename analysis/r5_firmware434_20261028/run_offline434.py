"""Run bounded local firmware checks, two independent processes at a time.

This runner never opens a camera, removable medium or network connection.
An optional name selects one check after a failure instead of repeating all.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib, json, os, subprocess, sys, time
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
tests = {
    'page': ['menu_research/replay_page425.py'],
    'delta': ['verify_delta434.py'],
    'wheel': ['menu_research/replay_wheel432.py'],
    'wheel_contract': ['wheel_evidence/probe_native_wheel432.py'],
    'native_list_contract': ['style_evidence/probe_native_list431.py'],
    'parent': ['parent_evidence/replay_parent431.py'],
    'native_list': ['style_evidence/replay_candidate_list431.py'],
    'names_inputs': ['menu_research/replay_name_input429.py'],
    'native_widgets': ['menu_research/replay_native_view426.py'],
    'native_allocator': ['menu_research/replay_allocator429.py'],
    'native_lifecycle': ['menu_research/replay_lifecycle429.py'],
    'native_manager': ['menu_research/replay_review429.py'],
    'identity': ['menu_research/replay_identity426.py'],
    'main_enter': ['menu_research/replay_main_open426.py'],
    'main_list': ['replay_main_menu425.py', '--candidate', str(HERE/'ap/appFw.so'), '--output', str(HERE/'main_menu425_replay.json')],
    'titles': ['replay_title425.py', str(HERE/'ap/appFw.so')],
    'grid_waits': ['sync_tests/run_grid430.py'],
    'worker': ['sync_tests/run_worker425.py'],
    'requests0': ['sync_tests/replay_exact_request425.py', '--bias', '0', '--output', str(HERE/'sync_tests/exact_request_bias0.json')],
    'requests_pie': ['sync_tests/replay_exact_request425.py', '--bias', '0x40000000', '--output', str(HERE/'sync_tests/exact_request_bias40000000.json')],
    'refresh': ['sync_tests/replay_refresh_wrapper425.py'],
    'threads': ['sync_tests/collect_thread_ownership425.py'],
    'inheritance': ['verify_inherited425.py'],
    
    'warm_media': ['sync_tests/replay_sd430.py','--candidate',str(HERE),'--output',str(HERE/'sync_tests/warm430_targeted.json'),'--verify-probe-boundary','--scenarios','same_file'],
    'sd_new': ['sync_tests/replay_sd430.py', '--candidate', str(HERE), '--output', str(HERE/'sync_tests/sd430_targeted.json'), '--verify-probe-boundary', '--scenarios', 'same_file', 'retry_bank_once', 'retry_bank_never', 'second_slot_pending', 'late_card', 'same_full_name_changed', 'same_grid_changed', 'second_ready_first_missing', 'first_bad_second_valid'],
    'sd': ['sync_tests/replay_sd430.py', '--candidate', str(HERE), '--output', str(HERE/'sync_tests/sd430_replay.json'), '--verify-probe-boundary'],
    'crosscore': ['crosscore/replay_select425.py', '--candidate', str(HERE), '--cp', str(ROOT/'analysis/r5_custom_filter423_20261023/cp/cp423.NONINSTALLABLE.bin'), '--output', str(HERE/'crosscore/ap_cp425.json')],
}

def run(name):
    args = tests[name]
    command = [sys.executable, '-X', 'faulthandler', str(HERE/args[0]), *args[1:]]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT/'vendor/audit-python'))
    start = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    (HERE/'test_logs').mkdir(exist_ok=True)
    (HERE/'test_logs'/f'{name}.log').write_text(result.stdout+result.stderr)
    row = dict(name=name, passed=result.returncode == 0, returncode=result.returncode,
               seconds=round(time.monotonic()-start, 2), command=command)
    print(json.dumps(row), flush=True)
    if result.returncode: print(result.stderr[-3000:], flush=True)
    return row

if __name__ == '__main__':
    if sys.argv[1:]==['--retry-failed']:
        path=HERE/'offline_checks434.json'
        prior=json.loads(path.read_text())
        ap=hashlib.sha256((HERE/'ap/appFw.so').read_bytes()).hexdigest()
        assert prior['AP_sha256']==ap
        expected=set(tests)-{'sd_new','warm_media'}
        assert len(prior['checks'])==len(expected) and {row['name'] for row in prior['checks']}==expected
        failed=[row for row in prior['checks'] if not row['passed']]
        assert failed,'No failed checks need rerunning'
        replacements={row['name']:run(row['name']) for row in failed}
        prior.setdefault('previous_failed_attempts',[]).extend(failed)
        prior['checks']=[replacements.get(row['name'],row) for row in prior['checks']]
        prior['passed']=all(row['passed'] for row in prior['checks'])
        path.write_text(json.dumps(prior,indent=2)+'\n')
        sys.exit(0 if prior['passed'] else 1)
    selected = sys.argv[1:] or [name for name in tests if name not in ('sd_new','warm_media','delta')]
    assert all(name in tests for name in selected)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = [future.result() for future in as_completed([pool.submit(run, name) for name in selected])]
    if all(row['passed'] for row in rows) and {'sd','worker','crosscore'}.issubset(selected):
        rows.append(run('delta'))
    report = dict(passed=all(row['passed'] for row in rows), checks=rows,
                  AP_sha256=hashlib.sha256((HERE/'ap/appFw.so').read_bytes()).hexdigest(),
                  device_io=False)
    (HERE/('offline_checks434.json' if not sys.argv[1:] else 'offline_retry434.json')).write_text(json.dumps(report, indent=2)+'\n')
    sys.exit(0 if report['passed'] else 1)
