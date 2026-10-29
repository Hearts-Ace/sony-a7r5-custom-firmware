"""Encode reference chart colors for the model's as-shot WB, once only."""
import struct
import numpy as np

def encode_reference(reference_codes, model):
    from edit_raw_front import itp_flatfield
    codes=np.asarray(reference_codes,dtype='<u2')
    reference_raw=bytearray(model.raw)
    struct.pack_into('<4h',reference_raw,0x4a,1024,1024,1024,1024)
    if bytes(reference_raw)==model.raw:
        return codes.copy()
    target=itp_flatfield(codes,reference_raw,model.settings)
    axis=np.arange(512,16384,dtype='<u2')
    lookup=itp_flatfield(np.repeat(axis[:,None],3,axis=1),model.raw,model.settings)
    result=np.empty_like(codes)
    for channel in range(3):
        column=lookup[:,channel].astype(int)
        if np.any(np.diff(column)<0):
            raise ValueError('RAW 白平衡编码必须单调')
        high=np.clip(np.searchsorted(column,target[:,channel]),0,len(axis)-1)
        low=np.maximum(high-1,0)
        choose_low=np.abs(column[low]-target[:,channel])<=np.abs(column[high]-target[:,channel])
        result[:,channel]=axis[np.where(choose_low,low,high)]
    return result
