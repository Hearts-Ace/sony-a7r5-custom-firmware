"""Color-block measurement contract: mean of the five central horizontal probes."""
import numpy as np

POLICY='center-horizontal-5-mean-x14..18-y16'

def center_mean(values):
    values=np.asarray(values)
    if values.ndim!=3 or values.shape[1]!=9:
        raise ValueError('色块采样要求每块9个实采探针，取索引2..6的中心5点')
    return values[:,2:7].mean(axis=1,dtype=np.float64)
