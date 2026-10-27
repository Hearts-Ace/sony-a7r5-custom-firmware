"""Versioned 100MP chart, using the same approximate RAW front as photo_preview."""
from pathlib import Path
from functools import lru_cache
import hashlib
import json
import numpy as np

DATASET_ID = 'v3-100mp-approx-front-20261026'
FOLDER = Path(__file__).parent/'data/chart/v3_100mp'
WIDTH, HEIGHT, TILE = 11648, 8736, 32
COLUMNS, ROWS = WIDTH//TILE, HEIGHT//TILE

def identity(arrays):
    return str(np.asarray(arrays.get('dataset_id','')).item()) == DATASET_ID

@lru_cache(maxsize=1)
def metadata():
    return json.loads((FOLDER/'manifest.json').read_text())

def validate(arrays):
    m=metadata()
    with np.load(FOLDER/'pairs.npz',allow_pickle=False) as expected:
        for key in expected.files:
            if key not in arrays or not np.array_equal(arrays[key],expected[key]):
                raise ValueError('v3训练输入或布局来源不一致：'+key)
    return dict(dataset_id=DATASET_ID,samples=COLUMNS*ROWS,frontend='Web photo_preview.approximate_front; simulated RAW frontend',
                frontend_approximate=True,edit_capture=False,photo_training=False,
                width=WIDTH,height=HEIGHT,anchor_count=284,gray_steps=256,
                manifest_sha256=hashlib.sha256((FOLDER/'manifest.json').read_bytes()).hexdigest())

def load():
    if hashlib.sha256((FOLDER/'pairs.npz').read_bytes()).hexdigest()!=metadata()['pairs_sha256']:
        raise ValueError('v3数据散列不符')
    with np.load(FOLDER/'pairs.npz',allow_pickle=False) as p:
        arrays={k:p[k].copy() for k in p.files}
    return arrays,validate(arrays)
