"""New synthetic Bayer ARW using original Sony lossless JPEG tile format.

Retains metadata; no original photograph sensor bytes are used as samples.
Every generated integer pixel must be independently decoded and checked.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, struct
import numpy as np
from build_synthetic_arw import PARSER, SOURCE, PIN

def jpeg(a):
    # Four lossless sequential components; predictor 1, no point transform.
    h,w,c=a.shape
    if c!=4 or np.any(a<0) or np.any(a>16383):raise ValueError('14-bit four component tile')
    d=np.empty_like(a,dtype=np.int32);d[:,1:]=a[:,1:].astype(np.int32)-a[:,:-1]
    d[1:,0]=a[1:,0].astype(np.int32)-a[:-1,0];d[0,0]=a[0,0].astype(np.int32)-8192
    d=d.reshape(-1);m=np.abs(d)
    category=np.zeros(len(d),dtype=np.int32)
    nonzero=m>0;category[nonzero]=np.floor(np.log2(m[nonzero])).astype(int)+1
    value=np.where(d<0,d+(1<<category)-1,d)
    code=(category<<category)|value
    nbits=category+4
    positions=np.arange(18)[None,:]
    shifts=nbits[:,None]-1-positions
    packed=((code[:,None]>>np.maximum(shifts,0))&1)[positions<nbits[:,None]]
    packed=np.r_[packed,np.ones((-len(packed))%8,dtype=np.int32)]
    entropy=np.packbits(packed.astype(np.uint8)).tobytes().replace(b'\xff',b'\xff\x00')
    sof=bytes([14])+struct.pack('>HHB',h,w,4)+b''.join(bytes([i,0x11,0]) for i in range(1,5))
    dht=bytes([0])+bytes([0,0,0,15]+[0]*12)+bytes(range(15))
    sos=bytes([4])+b''.join(bytes([i,0]) for i in range(1,5))+bytes([1,0,0])
    segment=lambda m,p:bytes([255,m])+struct.pack('>H',len(p)+2)+p
    return b'\xff\xd8'+segment(0xc3,sof)+segment(0xc4,dht)+segment(0xda,sos)+entropy+b'\xff\xd9'

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--tile',type=int,default=128);ap.add_argument('--seed',type=int,default=20261020)
    args=ap.parse_args();args.output.mkdir(exist_ok=False)
    spec=importlib.util.spec_from_file_location('sony_parser',PARSER);p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
    original=SOURCE.read_bytes()
    if hashlib.sha256(original).hexdigest()!=PIN:raise ValueError('Source changed')
    sub=p.ifd(original,p.scalar(p.ifd(original,p.u32(original,4)),0x14a))
    scalar=lambda tag:int.from_bytes(p.one(sub,tag)['data'],'little')
    w,h=scalar(256),scalar(257);tw,th=scalar(322),scalar(323)
    if (tw,th)!=(512,512) or args.tile%2:raise ValueError('Pinned format')
    cols,rows=(w+args.tile-1)//args.tile,(h+args.tile-1)//args.tile
    # Log-distributed exposures plus broad chromatic coverage; independent seed.
    rng=np.random.default_rng(args.seed)
    exposure=2**rng.uniform(-10,0,(rows,cols,1));chroma=rng.uniform(.02,1,(rows,cols,3))
    rgb=np.rint(512+15871*exposure*chroma).astype(np.uint16)
    anchors=np.array([[512]*3,[1024]*3,[2048]*3,[4096]*3,[8192]*3,[12000]*3,[16383]*3,
        [4096,2048,1024],[1024,4096,2048],[2048,1024,4096]],dtype=np.uint16)
    rgb.reshape(-1,3)[:len(anchors)]=anchors
    changed=bytearray(original);offsets=[];lengths=[]
    yy,xx=np.mgrid[:th,:tw];channel=np.where((xx&1)==(yy&1),np.where((xx&1)==0,0,2),1)
    for ty in range(h//th):
      for tx in range(w//tw):
        bayer=rgb[(yy+ty*th)//args.tile,(xx+tx*tw)//args.tile,channel]
        a=np.stack([bayer[0::2,0::2],bayer[0::2,1::2],bayer[1::2,0::2],bayer[1::2,1::2]],axis=-1)
        data=jpeg(a)
        changed.extend(bytes((-len(changed))%16));offsets.append(len(changed));lengths.append(len(data))
        changed.extend(data)
      print(json.dumps(dict(tile_row=ty+1,rows=h//th)),flush=True)
    changes=[]
    for tag,values in [(324,offsets),(325,lengths)]:
      e=p.one(sub,tag);at=p.u32(original,e['entry']+8)
      if len(values)!=e['count']:raise ValueError('Tile count changed')
      changed[at:at+4*len(values)]=struct.pack('<%dI'%len(values),*values)
      changes.append(dict(tag=tag,offset=at,count=len(values)))
    for tag,value in [(273,offsets[0]),(279,len(changed)-offsets[0])]:
      e=p.one(sub,tag);struct.pack_into('<I',changed,e['entry']+8,value)
    target=args.output/'synthetic.ARW';target.write_bytes(changed)
    np.savez_compressed(args.output/'chart.npz',rgb_codes=rgb,anchors=anchors)
    m=dict(schema='synthetic-Sony-lossless-RAW-chart/1',source_sha256=PIN,source_sensor_pixels_used=False,
        width=w,height=h,tile=args.tile,seed=args.seed,compression=7,raw_tile=[tw,th],changes=changes,
        output_sha256=hashlib.sha256(changed).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        status='Requires independent full sensor decode and native Edit export before admission')
    (args.output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(m))
if __name__=='__main__':main()
