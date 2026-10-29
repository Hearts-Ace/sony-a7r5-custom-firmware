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
    import baseline,v4_dataset
    capture,context=baseline.resolve(v4_dataset.DATASET_ID)
    ParameterContext(RuntimeColor.from_capture(capture,context))
    arrays,audit=v4_dataset.load();assert audit['samples']==99372
    import v45_dataset
    capture,context=baseline.resolve(v45_dataset.DATASET_ID)
    ParameterContext(RuntimeColor.from_capture(capture,context))
    arrays,audit=v45_dataset.load();assert audit['samples']==99372 and audit['edit_validated']
    import rawpy
    assert hasattr(rawpy,'RawPy')
    print('数据、12外观、原生颜色模型、v4/v4.5各99372点已验证色卡及 LibRaw 依赖检查通过。')
    if '--test'in sys.argv:
        suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
        return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful()else 1
    return 0
if __name__=='__main__':sys.exit(main())
