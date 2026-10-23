"""Freeze-bound local generation and dual-ISA transfer regressions. No devices."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import datetime, hashlib, json, os, subprocess, sys

HERE=Path(__file__).resolve().parent
WORK=HERE.parent
ROOT=WORK.parents[1]
CP=WORK/'cp/cp420-grid.NONINSTALLABLE.bin'
AP=ROOT/'analysis/r5_runtime_load421_20261022'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    build=WORK/'cp/build.json'
    csha=sha(CP)
    assert json.loads(build.read_text())['candidate_sha256']==csha
    paths=[Path(__file__),build,CP,WORK/'test_generations422.py',
        WORK/'import/cp_bridge.py',WORK/'import/replay_ap_transfer421.py',
        WORK/'import/replay_retained_transfer421.py',
        WORK/'import/replay_native12_transfer.py',
        ROOT/'tools/verify_r5_m4strict_cp_cpu.py',AP/'import/module_audit.json',
        AP/'ap/appFw.so',ROOT/'exports/fl2_fl3_grid_compare_20261023/R5NATIVE.BIN']
    before={str(p.relative_to(ROOT)):sha(p) for p in paths}
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    common=[sys.executable]
    rows=[('generations',common+[str(WORK/'test_generations422.py')],WORK/'tests/generations.json'),
        ('ap_transfer',common+[str(WORK/'import/replay_ap_transfer421.py'),'--candidate',str(AP),'--cp',str(CP),'--output',str(WORK/'tests/ap_transfer.json')],WORK/'tests/ap_transfer.json'),
        ('retained_transfer',common+[str(WORK/'import/replay_retained_transfer421.py'),'--candidate',str(AP),'--cp',str(CP),'--output',str(WORK/'tests/retained_transfer.json')],WORK/'tests/retained_transfer.json')]
    env=dict(os.environ,PYTHONPATH=str(ROOT/'vendor/audit-python'))
    def run(row):
        name,command,receipt=row
        assert all(sha(ROOT/p)==h for p,h in before.items()),'Input changed before '+name
        log=HERE/(name+'_'+stamp+'.log')
        with log.open('wb') as output:
            result=subprocess.run(command,cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT)
        assert result.returncode==0,(name,result.returncode,str(log))
        assert all(sha(ROOT/p)==h for p,h in before.items()),'Input changed during '+name
        q=json.loads(receipt.read_text())
        assert q['passed'] and q['cp_sha256']==csha
        return dict(name=name,passed=True,command=command,
            log=str(log.relative_to(ROOT)),log_sha256=sha(log),
            receipt=str(receipt.relative_to(ROOT)),receipt_sha256=sha(receipt))
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(run,rows))
    assert all(sha(ROOT/p)==h for p,h in before.items()),'Input changed after suites'
    report=dict(schema='r5-422-root-execution-binding/1',passed=True,camera_io=False,
        cp_sha256=csha,build_sha256=sha(build),sources=before,
        input_hashes_fixed_before_and_after_each_suite=True,rows=results)
    (WORK/'tests/root_execution_binding.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cp_sha256=csha,suites=len(results))))

if __name__=='__main__':main()
