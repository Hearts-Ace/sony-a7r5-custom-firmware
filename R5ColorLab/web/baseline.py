"""Resolve immutable training baselines; old jobs keep their original model."""
from pathlib import Path
import hashlib,json

HERE=Path(__file__).resolve().parent
LEGACY_CAPTURE=HERE.parent/'data/model/capture'
OLD_PT_ID='v4-PT-measured-100mp-20261026'
PT_FOLDER=HERE/'data/chart/sony100mp_unity_center5'
PT_ID='v4-sony100mp-unity-sim-center5-20261027'
V45_ID='v4.5-sony100mp-5300k-sim-center5-20261029'
PT_IDS=(PT_ID,V45_ID)

def resolve(dataset_id=None):
    from v4_dataset import RETIRED_IDS
    if dataset_id in RETIRED_IDS:
        raise ValueError('旧版错误色卡与训练基线已删除，请用新版色卡重新训练')
    if dataset_id in PT_IDS:
        from chart_datasets import get
        folder=get(dataset_id).FOLDER
        m=json.loads((folder/'manifest.json').read_text())
        capture=folder/'capture'
        if hashlib.sha256((capture/'report.json').read_bytes()).hexdigest()!=m['capture_report_sha256']:
            raise ValueError('PT 采集来源散列不符')
        return capture,m['context']
    if dataset_id not in (None,'balanced-chart-20261022-manual-context2'):
        raise ValueError('未知训练基线，拒绝回退到 ST')
    return LEGACY_CAPTURE,4

def for_job(job):
    job=Path(job)
    recipe_path=job/'fit/recipe.json'
    if recipe_path.is_file():
        recipe=json.loads(recipe_path.read_text())
        expected=recipe['source']['capture_report_sha256']
        from v4_dataset import RETIRED_IDS
        if recipe['source'].get('dataset_id') in RETIRED_IDS:
            raise ValueError('此任务使用已删除的错误色卡，必须重新训练')
        if recipe['source'].get('dataset_id') in PT_IDS:
            capture,context=resolve(recipe['source']['dataset_id'])
            if hashlib.sha256((capture/'report.json').read_bytes()).hexdigest()!=expected or recipe['source']['context']!=context:
                raise ValueError('PT任务绑定的训练基线发生变化')
            return capture,context
        for dataset_id in (*PT_IDS,None):
            capture,context=resolve(dataset_id)
            if hashlib.sha256((capture/'report.json').read_bytes()).hexdigest()==expected:
                if recipe['source']['context']!=context:raise ValueError('模型上下文不匹配')
                return capture,context
        raise ValueError('任务绑定的训练基线未知，拒绝切换模型')
    audit=json.loads((job/'input_audit.json').read_text())
    return resolve(audit.get('dataset_id'))

def read_job(job):
    from edit_native_recipe import read
    capture,context=for_job(job)
    return read(Path(job)/'fit/recipe.json',capture,context,None)
