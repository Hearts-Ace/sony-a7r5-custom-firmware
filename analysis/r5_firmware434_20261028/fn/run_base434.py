"""Run the three fixed local Fn probes; no camera or network access."""
from pathlib import Path
import os,subprocess,sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT/'vendor/audit-python'))
for name in ('replay_fn434.py','replay_fn_save434.py','replay_fn_labels434.py'):
    subprocess.run([sys.executable,'-B',str(HERE/name)],cwd=ROOT,env=env,check=True)
