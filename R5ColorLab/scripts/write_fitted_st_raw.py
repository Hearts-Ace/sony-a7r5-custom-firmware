"""Write a native fit to Standard in a new ARW; preserve sensor data/other looks."""
from pathlib import Path
import argparse,importlib.util,json,struct,hashlib
from edit_parameter_context import RuntimeColor,np
from edit_native_model import decode_matrix16

def sha(b):return hashlib.sha256(b).hexdigest()

def reader():
    p=Path(__file__).with_name('sony_arw_metadata.py')
    s=importlib.util.spec_from_file_location('raw_reader',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    return m

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('raw',type=Path);ap.add_argument('recipe',type=Path)
    ap.add_argument('--capture',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.output.exists():raise ValueError('Refuse overwrite')
    recipe=json.loads(args.recipe.read_text())
    if recipe.get('pc_residual') is not None or recipe.get('additional_compensation_matrix_enabled') is not False:
        raise ValueError('Only native, uncompensated photo recipes accepted')
    m=reader();original=args.raw.read_bytes();a=m.parse(original)
    st=next(g for g in a['styles'] if m.look_name(g)=='Standard')
    model=RuntimeColor.from_capture(args.capture,recipe['source']['context'])
    p=recipe['parameters']
    if m.one(st,0x780f)['data']!=model.raw[0xae:0xae+276]:raise ValueError('Capture is not source ST')
    if m.one(st,0x7806)['data']!=model.raw[0x7d8:0x9d8]:raise ValueError('ST Gamma mismatch')
    base=np.array(struct.unpack('<8h',m.one(st,0x7842)['data']))
    if not np.array_equal(base,np.frombuffer(model.raw,dtype='<i2',offset=0xdec,count=8)):
        raise ValueError('ST CC1 base mismatch')
    if model.raw[0x1c]:raise ValueError('This writer requires measured ST indirect CC1 path')
    desired=np.array(p['cc1_direct_raw']);newbase=base+desired-model.coefficients()
    if np.any(newbase < -32768) or np.any(newbase >32767):raise ValueError('CC1 base overflow')
    payload=bytes.fromhex(p['matrix_780f_hex']);cfg=decode_matrix16(payload)
    q=np.rint(np.array(struct.unpack_from('<96f',cfg,0x28)).reshape(6,16)[:,0]*1024).astype(int)
    aa,b,c,d,e,f=q
    matrix=[1024+aa+b,-aa,-b,-c,1024+c+d,-d,-e,-f,1024+e+f]
    changes={0x780f:payload,0x7806:struct.pack('<128i',*p['gamma_7806_y']),
        0x7842:struct.pack('<8h',*newbase),0x7800:struct.pack('<9h',*matrix)}
    dec=bytearray(a['dec']);allowed=set()
    for tag,data in changes.items():
        entry=m.one(st,tag)
        if len(data)!=len(entry['data']):raise ValueError('Field size mismatch')
        at=entry['entry']+8 if len(data)<=4 else m.u32(dec,entry['entry']-a['offset']+8)
        local=at-a['offset'];dec[local:local+len(data)]=data;allowed.update(range(local,local+len(data)))
    if any(x!=y and i not in allowed for i,(x,y) in enumerate(zip(a['dec'],dec))):
        raise AssertionError('Unexpected plaintext modification')
    out=bytearray(original);off=a['offset'];out[off:off+a['length']]=m.crypt(dec,a['key'])
    parsed=m.parse(out)
    for before,after in zip(a['styles'],parsed['styles']):
        for old,new in zip(before,after):
            expected=changes.get(old['tag'],old['data']) if m.look_name(before)=='Standard' else old['data']
            if new['data']!=expected:raise AssertionError('RAW parameter readback mismatch')
    if out[:off]!=original[:off] or out[off+a['length']:]!=original[off+a['length']:]:
        raise AssertionError('Bytes outside encrypted metadata changed')
    with args.output.open('xb') as fh:fh.write(out)
    result=dict(schema='fitted-ST-raw-write/1',input_sha256=sha(original),output_sha256=sha(out),
        recipe_sha256=sha(args.recipe.read_bytes()),changed_tags=[hex(t) for t in changes],
        cc1_base_before=base.tolist(),cc1_base_after=newbase.tolist(),
        cc1_effective_target=desired.tolist(),other_looks_unchanged=True,
        all_bytes_outside_SR2_unchanged=True,sensor_data_unchanged=True,
        requires_explicit_Edit_ST_selection=True,compensation_enabled=False)
    args.output.with_suffix('.audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
