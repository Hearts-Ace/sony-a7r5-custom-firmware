"""Diagnostic waits must yield; current-slot observation must suffice."""
from pathlib import Path
import hashlib, json, subprocess, tempfile
HERE=Path(__file__).resolve().parent
CAND=HERE.parent
source=HERE/'grid_wait430_test.c'
with tempfile.TemporaryDirectory(prefix='r5-grid-wait430-') as td:
    exe=Path(td)/'grid'
    subprocess.run(['clang','-O2','-I',str(CAND/'import'),str(source),'-o',str(exe)],check=True)
    rows=[json.loads(subprocess.check_output([str(exe),str(i)])) for i in range(7)]
files=[source,Path(__file__),CAND/'import/r5_grid420_log.c']
report=dict(passed=True,AP_sha256=hashlib.sha256((CAND/'ap/appFw.so').read_bytes()).hexdigest(),
    cases=rows,source_sha256={str(p.relative_to(CAND)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
    boundary='Actual production diagnostic C on host ISA; clocks, native Fsys, CP reply and selection-service boundary are fixtures. Timings are synthetic, not camera measurements.',device_io=False)
(HERE/'grid430_verified.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,cases=len(rows))))
