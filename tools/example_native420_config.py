"""Generate a synthetic 4.20 grid format fixture; not a factory/fitted look."""
from pathlib import Path
import argparse, importlib.util, json

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--clear',action='store_true',help='Generate an empty v3 configuration that clears all custom looks in 4.20')
    a=p.parse_args();root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('native420',root/'analysis/r5_native_grid420_20261022/import/native_overwrite_config.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    grid=[[[[0 for _ in range(9)]for _ in range(9)]for _ in range(5)]for _ in range(3)]
    if not a.clear:grid[0][2][4][4]=1
    entries=[] if a.clear else [dict(number=2,name='FormatTest',cc1_delta=[[0,0,0,0,256,256,256,256],[0]*8,[0]*8],block13=[[[0]*6 for _ in range(16)]for _ in range(3)],gamma_native_129=[i*1023 for i in range(129)],grid_5x9x9=dict(enabled=True,coefficients=grid))]
    cfg=dict(schema=m.GRID_SCHEMA,model='ILCE-7RM5',baseline_ap_sha256=m.AP_SHA,baseline_cp_sha256=m.CP_SHA,additional_compensation_matrix_enabled=False,compensation_grid_enabled=not a.clear,entries=entries)
    m.pack(cfg)
    with a.output.open('x')as f:json.dump(cfg,f,indent=2);f.write('\n')

if __name__=='__main__':main()
