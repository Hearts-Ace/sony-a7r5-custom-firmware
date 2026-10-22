"""Portable project integrity, runtime and regression checks."""
from pathlib import Path
import hashlib,json,sys,unittest
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'web'),str(ROOT/'scripts')]
def main():
    manifest=json.loads((ROOT/'data_manifest.json').read_text())
    for name,digest in manifest.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('数据校验失败：'+name)
    import core,anchor_dataset,numpy as np
    from edit_parameter_context import ParameterContext,RuntimeColor
    entries,_=core.presets();assert len(entries)==12
    ParameterContext(RuntimeColor.from_capture(core.CAPTURE,4))
    with np.load(anchor_dataset.PAIRS,allow_pickle=False)as p:assert anchor_dataset.validate(dict(p))['samples']==3700
    import rawpy
    assert hasattr(rawpy,'RawPy')
    print('数据、12外观、原生颜色模型、3700点新色卡及 LibRaw 依赖检查通过。')
    if '--test'in sys.argv:
        suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
        return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful()else 1
    return 0
if __name__=='__main__':sys.exit(main())
