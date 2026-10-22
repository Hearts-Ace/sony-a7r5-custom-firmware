"""Strict PC reader for the measured-context native color fit research format."""
from pathlib import Path
import hashlib
import json
import struct
from edit_parameter_context import ParameterContext,RuntimeColor,np


def unique(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError('Duplicate JSON field: '+key)
        result[key]=value
    return result


def read(path,capture,context,matrix_builder):
    def nonfinite(value): raise ValueError('Nonfinite JSON value')
    recipe=json.loads(Path(path).read_text(),object_pairs_hook=unique,parse_constant=nonfinite)
    if (recipe.get('schema')!='r5-edit-native-color-fit/1'
            or recipe.get('camera_apply_allowed') is not False
            or recipe.get('complete_edit_fitter') is not False
            or recipe.get('renderer')!='measured-Edit-color-subchain-with-native-matrix-builder'
            or recipe.get('input_domain')!='Edit post-SSCS/pre-matrix integer RGB'):
        raise ValueError('Unknown recipe/model scope')
    model=RuntimeColor.from_capture(capture,context)
    source=recipe['source']
    if context!=source['context']: raise ValueError('Recipe context mismatch')
    data={'capture_report':(Path(capture)/'report.json').read_bytes(),
        'runtime':model.runtime,'raw':model.raw,'settings':model.settings}
    for name,value in data.items():
        if hashlib.sha256(value).hexdigest()!=source[name+'_sha256']:
            raise ValueError('Recipe source mismatch: '+name)
    params=recipe['parameters']
    actual_axis=np.frombuffer(model.raw,dtype='<i4',count=128,offset=0x5d8)
    if not np.array_equal(params['gamma_7805_x'],actual_axis): raise ValueError('Axis changed')
    payload=bytes.fromhex(params['matrix_780f_hex'])
    if len(payload)!=276: raise ValueError('Invalid block13 length')
    # Fits may alter coefficient bytes only; flags/sectors/scales/thresholds
    # remain those of the identity-calibration context that was verified.
    if payload[:24]!=model.raw[0xae:0xae+24] or payload[216:]!=model.raw[0xae+216:0xae+276]:
        raise ValueError('Recipe changed unsupported common matrix fields')
    result=ParameterContext(model,matrix_builder).build(matrix_payload=payload,
        cc1=params['cc1_direct_raw'],gamma_y=params['gamma_7806_y'])
    if 'pc_residual' in recipe:
        from residual_grid import unpack,response_matrix
        grid=recipe['pc_residual']
        if (grid.get('coordinate_model')!='provisional-bt601-limited'
                or grid.get('stage')!='after-color-subchain-PC-only'
                or grid.get('camera_semantics_verified') is not False):
            raise ValueError('Unknown residual model')
        result.pc_residual=(unpack(bytes.fromhex(grid['payload_hex'])),response_matrix(grid['response']))
    return recipe,result


def render(model,image):
    base=model.color_only(image)
    if hasattr(model,'pc_residual'):
        from residual_grid import evaluate
        grid,response=model.pc_residual
        return (evaluate(base.reshape(-1,3)/16383,grid,response)*16383).reshape(base.shape)
    return base
