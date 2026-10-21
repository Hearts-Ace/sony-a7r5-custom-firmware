"""Generate a synthetic 4.18 format fixture, not a factory or fitted look."""
from pathlib import Path
import argparse,importlib.util,json

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('native418',root/'analysis/r5_native_overwrite418_20261021/import/native_overwrite_config.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    cfg=dict(schema=m.SCHEMA,model='ILCE-7RM5',baseline_ap_sha256=m.AP_SHA,baseline_cp_sha256=m.CP_SHA,additional_compensation_matrix_enabled=False,compensation_grid_enabled=False,entries=[dict(number=2,name='FormatTest',cc1_delta=[[0,0,0,0,256,256,256,256],[0]*8,[0]*8],block13=[[[0]*6 for _ in range(16)] for _ in range(3)],gamma_native_129=[i*1023 for i in range(129)])])
    m.pack(cfg)
    with a.output.open('x')as f:json.dump(cfg,f,indent=2);f.write('\n')
if __name__=='__main__':main()
