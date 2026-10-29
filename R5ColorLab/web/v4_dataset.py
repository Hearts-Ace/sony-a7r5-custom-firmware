"""Unity-WB Sony 100MP chart with simulated, independently verified inputs."""
from pathlib import Path
from functools import lru_cache
import hashlib
import json
import numpy as np

LEGACY_ID = 'v4-repaired-linear-100mp-20261026'
SIMULATED_ID = 'v4-precision-linear-100mp-20261026'
OLD_PT_ID = 'v4-PT-measured-100mp-20261026'
RETIRED_IDS = (LEGACY_ID, SIMULATED_ID, OLD_PT_ID, 'v4-PT-NRoff-sharp0-center5-20261027')
DATASET_ID = 'v4-sony100mp-unity-sim-center5-20261027'
BASE = Path(__file__).parent/'data/chart'
FOLDER = BASE/'sony100mp_unity_center5'
WIDTH, HEIGHT, TILE = 11648, 8736, 32
COLUMNS, ROWS = WIDTH//TILE, HEIGHT//TILE

def identity(arrays):
    from v45_dataset import DATASET_ID as V45_ID
    return str(np.asarray(arrays.get('dataset_id','')).item()) in (DATASET_ID, V45_ID, *RETIRED_IDS)

@lru_cache(maxsize=1)
def metadata():
    return json.loads((FOLDER/'manifest.json').read_text())

@lru_cache(maxsize=1)
def _load():
    if hashlib.sha256((FOLDER/'pairs.npz').read_bytes()).hexdigest()!=metadata()['pairs_sha256']:
        raise ValueError('v4 色卡训练数据散列不符')
    with np.load(FOLDER/'pairs.npz',allow_pickle=False) as p:
        return {key:p[key].copy() for key in p.files}

def validate(arrays):
    dataset_id=str(np.asarray(arrays.get('dataset_id','')).item())
    from v45_dataset import DATASET_ID as V45_ID, validate as validate_v45
    if dataset_id==V45_ID:
        return validate_v45(arrays)
    if dataset_id!=DATASET_ID:
        raise ValueError('此色卡数据已废弃：旧白平衡/传感器码值错误，请使用新版 unity-WB 色卡重新训练')
    expected=_load()
    for key,value in expected.items():
        if key not in arrays or not np.array_equal(arrays[key],value):
            raise ValueError('v4 色卡输入、布局或分组不一致：'+key)
    return dict(passed=True,dataset_id=dataset_id,samples=COLUMNS*ROWS,
        sampling='center-horizontal-5-mean-x14..18-y16',frontend=metadata()['input_source'],
        frontend_approximate=False,edit_capture=False,edit_validated=True,photo_training=False,
        look='PT',context=metadata()['context'],spatial_postprocessing_modeled=False,
        width=WIDTH,height=HEIGHT,anchor_count=284,gray_steps=256,
        anchors_in_training=True,anchors_in_independent_test=False,
        manifest_sha256=hashlib.sha256((FOLDER/'manifest.json').read_bytes()).hexdigest())

def load():
    arrays={key:value.copy() for key,value in _load().items()}
    return arrays,validate(arrays)
