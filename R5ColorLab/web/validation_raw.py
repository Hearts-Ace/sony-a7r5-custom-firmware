"""Source-bound ST/PT validation ARW; preserve all sensor bytes and other looks."""
import hashlib,json,struct
import numpy as np
import baseline,white_balance
from edit_native_recipe import read
from write_fitted_st_raw import reader
from edit_native_model import decode_matrix16

def write(original,recipe_path,destination):
    import shutil
    if shutil.disk_usage(recipe_path.parent).free < len(original)+512*1024*1024:
        raise ValueError('磁盘空间不足：验证 ARW 写入后需保留至少512 MiB')
    capture,context=baseline.for_job(recipe_path.parent.parent)
    recipe,model=read(recipe_path,capture,context,None)
    if white_balance.active(white_balance.from_recipe(recipe)):
        raise ValueError('实验白平衡不能写入验证 ARW')
    if recipe.get('compensation_grid_enabled') is not False or recipe.get('pc_residual'):
        raise ValueError('验证 ARW 仅支持原生颜色参数')
    from edit_color_pipeline import RuntimeColor
    source=RuntimeColor.from_capture(capture,context)
    is_pt=recipe['source'].get('dataset_id') in (*baseline.PT_IDS,baseline.OLD_PT_ID)
    look='Portrait' if is_pt else 'Standard';short='PT' if is_pt else 'ST'
    m=reader();a=m.parse(original)
    if a['model']!='ILCE-7RM5':raise ValueError('需要 R5 ARW')
    style=next(g for g in a['styles'] if m.look_name(g)==look)
    for tag,expected in ((0x780f,source.raw[0xae:0xae+276]),(0x7806,source.raw[0x7d8:0x9d8]),(0x7842,source.raw[0xdec:0xdfc])):
        if m.one(style,tag)['data']!=expected:raise ValueError(short+' RAW 参数基线不符')
    if source.raw[0x1c]:raise ValueError('验证导出只支持已测间接CC1路径')
    p=recipe['parameters'];base=np.frombuffer(m.one(style,0x7842)['data'],'<i2').astype(int)
    desired=np.asarray(p['cc1_direct_raw']);newbase=base+desired-source.coefficients()
    if np.any((newbase < -32768)|(newbase>32767)):raise ValueError('CC1 溢出')
    payload=bytes.fromhex(p['matrix_780f_hex']);cfg=decode_matrix16(payload)
    aa,b,c,d,e,f=np.rint(np.array(struct.unpack_from('<96f',cfg,0x28)).reshape(6,16)[:,0]*1024).astype(int)
    matrix=[1024+aa+b,-aa,-b,-c,1024+c+d,-d,-e,-f,1024+e+f]
    changes={0x780f:payload,0x7806:struct.pack('<128i',*p['gamma_7806_y']),
             0x7842:struct.pack('<8h',*newbase),0x7800:struct.pack('<9h',*matrix)}
    dec=bytearray(a['dec']);allowed=set()
    for tag,data in changes.items():
        entry=m.one(style,tag)
        if len(data)!=len(entry['data']):raise ValueError('RAW 字段大小不符')
        at=entry['entry']+8 if len(data)<=4 else m.u32(dec,entry['entry']-a['offset']+8)
        at-=a['offset'];dec[at:at+len(data)]=data;allowed.update(range(at,at+len(data)))
    assert all(x==y or i in allowed for i,(x,y) in enumerate(zip(a['dec'],dec)))
    result=bytearray(original);off=a['offset'];result[off:off+a['length']]=m.crypt(dec,a['key'])
    after=m.parse(result)
    for old_group,new_group in zip(a['styles'],after['styles']):
        for old,new in zip(old_group,new_group):
            expected=changes.get(old['tag'],old['data']) if m.look_name(old_group)==look else old['data']
            assert new['data']==expected
    assert result[:off]==original[:off] and result[off+a['length']:]==original[off+a['length']:]
    destination.mkdir(parents=True,exist_ok=False)
    filename='fitted-'+short+'.ARW';(destination/filename).write_bytes(result)
    sha=lambda b:hashlib.sha256(b).hexdigest()
    audit=dict(schema='source-bound-validation-raw/1',look=short,file=filename,
      input_sha256=sha(original),output_sha256=sha(result),recipe_sha256=sha(recipe_path.read_bytes()),
      sensor_data_unchanged=True,other_looks_unchanged=True,all_bytes_outside_SR2_unchanged=True,
      compensation_enabled=False,requires_explicit_Edit_selection=short)
    (destination/('fitted-'+short+'.audit.json')).write_text(json.dumps(audit,indent=2)+'\n')
    return audit
