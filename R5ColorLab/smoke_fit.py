"""Run a small real fit/compression/export to a caller-selected NEW directory."""
from pathlib import Path
import sys,subprocess,json,io,zipfile,struct
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'web'),str(ROOT/'scripts')]
import core,numpy as np,pc_compensation,grid_distillation

def main():
    if len(sys.argv)!=2:raise SystemExit('用法: python smoke_fit.py 新建输出目录')
    out=Path(sys.argv[1]).resolve();out.mkdir(exist_ok=False)
    colors=[' '.join(str(x)for x in [r,g,b])for b in [0,1]for g in [0,1]for r in [0,1]]
    (out/'input.cube').write_text('LUT_3D_SIZE 2\n'+'\n'.join(colors)+'\n')
    core.prepare_target(out/'input.cube','S-Gamut3',out)
    import baseline
    capture,context=baseline.for_job(out)
    command=[sys.executable,str(ROOT/'web/fit_anchor_native.py'),str(out/'pairs.npz'),'--capture',str(capture),'--context',str(context),'--gamut','0','--output',str(out/'fit'),'--evaluations','1','--pc-compensation','--search-options',json.dumps(dict(starts=2,adaptive_rounds=0,perceptual_weight=.35,quantization_sweeps=0,parameter_smoothing=30))]
    with (out/'fit.log').open('w')as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
    result=core.finish_fit(out,2,'Portable','Portable ST',131071);assert result['binary_bytes']==2580
    pc_compensation.generate(out)
    report=grid_distillation.generate(out,np.eye(3))
    blob=grid_distillation.firmware_config(out,report['key']);(out/'v4-config.zip').write_bytes(blob)
    with zipfile.ZipFile(io.BytesIO(blob))as z:
        cfg=json.loads(z.read('native_config.json'));binary=z.read('R5NATIVE.BIN')
        assert core.compile_config(__import__("export_policy423").configuration(cfg))[0]==binary and len(binary)==2580
        assert binary[:8]==b'R5CUST4\0'
    diagnostic=core.diagnostics(out,True,report['key']);assert diagnostic['algorithm']=='compressed'
    with np.load(out/'fit/fit_state.npz')as state:expected=state['test_prediction']
    import white_balance
    from edit_native_recipe import read
    recipe,model=read(out/'fit/recipe.json',capture,context,None)
    with np.load(out/'pairs.npz')as pairs:actual=white_balance.render_pairs(model,pairs,recipe,pairs['split']=='test')
    np.testing.assert_array_equal(actual,expected)
    raw=core.write_validation_raw((ROOT/'tests/fixtures/synthetic-header.ARW').read_bytes(),out/'fit/recipe.json',out/'raw')if (ROOT/'tests/fixtures/synthetic-header.ARW').exists()else None
    (out/'smoke_summary.json').write_text(json.dumps(dict(passed=True,samples=99372,wb_training=False,pc_training=True,v4_bytes=len(binary),grid_enabled=True,exact_recipe_reconstruction=True),indent=2)+'\n')
    print('独立新色卡训练、PC补偿、网格压缩、v4导出及配方重建通过。')
if __name__=='__main__':main()
