"""Generate a synthetic sensor chart in a NEW Sony ARW container.

Original metadata is preserved except the explicit raw compression/strip
fields. Original files are never written. Photo sensor bytes are not samples.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, struct
import numpy as np

PARSER=Path('/Users/LOCAL_USER/Documents/ChatGPT/ied软件/RAW创意外观解锁/add_fl2_fl3.py')
SOURCE=Path('/Users/LOCAL_USER/Documents/fl对比/DSC00430.ARW')
PIN='8aebb1f4fa75ce7aa3e830186d838b41fd13ad9e54781cb28f553ca548b41603'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--bits',type=int,choices=[14,16],default=14)
    ap.add_argument('--tile',type=int,default=128)
    args=ap.parse_args();args.output.mkdir(exist_ok=False)
    spec=importlib.util.spec_from_file_location('sony_parser',PARSER)
    parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
    original=SOURCE.read_bytes()
    if hashlib.sha256(original).hexdigest()!=PIN:raise ValueError('Original identity changed')
    root=parser.ifd(original,parser.u32(original,4))
    sub=parser.ifd(original,parser.scalar(root,0x14a))
    scalar=lambda tag:int.from_bytes(parser.one(sub,tag)['data'],'little')
    width,height=scalar(0x100),scalar(0x101)
    if (width,height)!=(9728,6656) or args.tile%2 or args.tile<64:
        raise ValueError('Pinned Bayer geometry required')
    cols,rows=(width+args.tile-1)//args.tile,(height+args.tile-1)//args.tile
    rng=np.random.default_rng(20261020)
    rgb=rng.integers(512,15001,(rows,cols,3),dtype=np.uint16)
    anchors=np.array([[512]*3,[1024]*3,[2048]*3,[4096]*3,[8192]*3,[12000]*3,
        [16383]*3,[4096,2048,1024],[1024,4096,2048],[2048,1024,4096]],dtype=np.uint16)
    rgb.reshape(-1,3)[:len(anchors)]=anchors
    yy,xx=np.mgrid[:height,:width]
    channel=np.where((xx&1)==(yy&1),np.where((xx&1)==0,0,2),1)
    bayer=rgb[yy//args.tile,xx//args.tile,channel].astype('<u2')
    changed=bytearray(original);offset=(len(changed)+3)&~3
    changed.extend(bytes(offset-len(changed)))
    fields={0x103:1,0x102:args.bits,0x111:offset,0x117:bayer.nbytes}
    changes=[]
    for tag,value in fields.items():
        entry=parser.one(sub,tag);length=len(entry['data'])
        if entry['count']!=1 or length not in [2,4]:raise ValueError('Unexpected raw field')
        at=entry['entry']+8;before=bytes(changed[at:at+length])
        changed[at:at+length]=value.to_bytes(length,'little')
        changes.append(dict(tag=hex(tag),offset=at,before_hex=before.hex(),after=value))
    destination=args.output/'synthetic.ARW'
    with destination.open('xb') as f:f.write(changed);f.write(bayer.tobytes())
    np.savez_compressed(args.output/'chart.npz',rgb_codes=rgb,anchors=anchors)
    manifest=dict(schema='synthetic-Sony-RAW-chart/1',source_sha256=PIN,
        source_sensor_pixels_used=False,metadata_source=str(SOURCE),raw_width=width,raw_height=height,
        tile=args.tile,cols=cols,rows=rows,bits=args.bits,compression=1,fields=changes,
        output_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
        raw_bytes_sha256=hashlib.sha256(bayer.tobytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        parser_sha256=hashlib.sha256(PARSER.read_bytes()).hexdigest(),
        status='decoder and native Edit acceptance must be verified before fitting')
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
