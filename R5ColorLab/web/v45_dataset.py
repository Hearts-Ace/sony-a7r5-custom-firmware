"""5300K Sony chart; simulated inputs independently verified against Edit."""
from pathlib import Path
from functools import lru_cache
import hashlib
import json
import numpy as np

DATASET_ID = 'v4.5-sony100mp-5300k-sim-center5-20261029'
FOLDER = Path(__file__).parent/'data/chart/sony100mp_5300k_v45'
WIDTH, HEIGHT, TILE = 11648, 8736, 32
COLUMNS, ROWS = WIDTH//TILE, HEIGHT//TILE

@lru_cache(maxsize=1)
def metadata():
    return json.loads((FOLDER/'manifest.json').read_text())

@lru_cache(maxsize=1)
def runtime_validation():
    identity=metadata()['edit_validation']
    report=FOLDER/identity['report_file']
    if hashlib.sha256(report.read_bytes()).hexdigest()!=identity['report_sha256']:
        raise ValueError('v4.5 Edit验证记录散列不符')
    result=json.loads(report.read_text())
    if (result['dataset_id']!=DATASET_ID or result['pairs_sha256']!=metadata()['pairs_sha256']
            or not result['capture_complete'] or not result['all_buffer_hashes_verified']
            or not result['comparisons']['simulated_front_vs_actual_all9']['exact']
            or not result['comparisons']['tiff_vs_actual_all9']['exact']):
        raise ValueError('v4.5 Edit验证记录与模拟输入不一致')
    return result

@lru_cache(maxsize=1)
def _load():
    if hashlib.sha256((FOLDER/'pairs.npz').read_bytes()).hexdigest() != metadata()['pairs_sha256']:
        raise ValueError('v4.5 色卡数据散列不符')
    with np.load(FOLDER/'pairs.npz',allow_pickle=False) as archive:
        return {key:archive[key].copy() for key in archive.files}

def validate(arrays):
    for key,value in _load().items():
        if key not in arrays or not np.array_equal(arrays[key],value):
            raise ValueError('v4.5 色卡输入、布局或分组不一致：'+key)
    verification=runtime_validation()
    return dict(passed=True,dataset_id=DATASET_ID,samples=COLUMNS*ROWS,
        sampling=metadata()['sampling'],frontend=metadata()['input_source'],
        frontend_approximate=False,edit_capture=False,edit_validated=True,
        edit_validation_scope='all flat-patch center inputs exact; final PT output has one known residual',
        edit_validation=metadata()['edit_validation'],
        final_color_residual=verification['comparisons']['existing_model_vs_output_center5'],
        context_origin='5300K WB derived; original verified PT downstream context',
        photo_training=False,look='PT',context=metadata()['context'],wb_kelvin=5300,
        raw_wb=metadata()['raw_wb'],spatial_postprocessing_modeled=False,
        width=WIDTH,height=HEIGHT,anchor_count=284,gray_steps=256,
        anchors_in_training=True,anchors_in_independent_test=False,
        manifest_sha256=hashlib.sha256((FOLDER/'manifest.json').read_bytes()).hexdigest())

def load():
    arrays={key:value.copy() for key,value in _load().items()}
    return arrays,validate(arrays)
