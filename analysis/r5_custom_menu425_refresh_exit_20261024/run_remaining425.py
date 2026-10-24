from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess,sys,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
commands=[['replay_title425.py',str(HERE/'ap/appFw.so')],['crosscore/replay_select425.py','--candidate',str(HERE),'--cp',str(ROOT/'analysis/r5_custom_filter423_20261023/cp/cp423.NONINSTALLABLE.bin'),'--output',str(HERE/'crosscore/ap_cp425.json')],['verify_inherited425.py']]
def run(args):
 p=HERE/args[0];log=HERE/(p.stem+'.log')
 with log.open('w') as f:r=subprocess.run([sys.executable,str(p),*args[1:]],stdout=f,stderr=subprocess.STDOUT,cwd=ROOT)
 if r.returncode:raise RuntimeError(str(log))
 return p.name
with ThreadPoolExecutor(max_workers=3) as pool:print(json.dumps(list(pool.map(run,commands))))
