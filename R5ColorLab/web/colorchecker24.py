"""ColorChecker Classic / BabelColor Average D50 -> calibrated camera RGB.

Colour pinned source supplies xyY measured averages, not arbitrary sRGB swatches.
This is a mathematical chart under its reference illuminant, not a camera
spectral characterization or a photographed physical chart.
"""
from pathlib import Path
import hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
NAMES=['深肤色','浅肤色','蓝天','树叶','蓝花','蓝绿','橙色','紫蓝','中红','紫色','黄绿','橙黄','蓝色','绿色','红色','黄色','品红','青色','白色','中性灰八','中性灰六点五','中性灰五','中性灰三点五','黑色']
def data():
 chart=np.load(ROOT/'data/training/chart/chart.npz',allow_pickle=False)
 manifest=json.loads((ROOT/'data/training/chart/manifest.json').read_text())
 return chart['anchors'][260:284].copy(),manifest['colorchecker24']
