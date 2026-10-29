"""Version-bound charts: default affects new requests, never saved jobs."""
import v4_dataset
import v45_dataset

DEFAULT_ID = v45_dataset.DATASET_ID
MODULES = {m.DATASET_ID:m for m in (v45_dataset,v4_dataset)}

def get(dataset_id=None):
    try:
        return MODULES[DEFAULT_ID if dataset_id is None else dataset_id]
    except (KeyError,TypeError):
        raise ValueError('未知色卡版本，请重新选择') from None

def catalog():
    return [dict(id=v45_dataset.DATASET_ID,label='v4.5 · 5300K · 一亿像素'),
            dict(id=v4_dataset.DATASET_ID,label='v4 · unity-WB · 历史色卡')]

def upload_version(folder, requested=None):
    import json
    # Existing uploads predate version selection. Their identical geometry is
    # insufficient evidence to reinterpret them as the new physical RAW.
    path=folder/'audit.json'
    bound=json.loads(path.read_text())['schema'] if path.is_file() else v4_dataset.DATASET_ID
    if requested is not None and requested != bound:
        raise ValueError('目标图绑定的色卡版本不符，请切换版本并重新上传对应导出图')
    get(bound)
    return bound
