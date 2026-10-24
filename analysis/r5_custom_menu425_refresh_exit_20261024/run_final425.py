from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess,sys,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
commands=[['run_remaining425.py'],['replay_main_menu425.py','--candidate',str(HERE/'ap/appFw.so')],['sync_tests/run_worker425.py'],['sync_tests/replay_refresh_wrapper425.py'],['sync_tests/collect_thread_ownership425.py'],['sync_tests/replay_exact_request425.py','--bias','0','--output',str(HERE/'sync_tests/exact_request_bias0.json')],['sync_tests/replay_exact_request425.py','--bias','0x40000000','--output',str(HERE/'sync_tests/exact_request_bias40000000.json')]]
def run(args):
 p=HERE/args[0];log=HERE/(p.stem+('-'+args[2] if '--bias' in args else '')+'.log')
 with log.open('w') as f:r=subprocess.run([sys.executable,str(p),*args[1:]],stdout=f,stderr=subprocess.STDOUT,cwd=ROOT)
 if r.returncode:raise RuntimeError(str(log))
 return p.name
with ThreadPoolExecutor(max_workers=4) as pool:print(json.dumps(list(pool.map(run,commands))))
