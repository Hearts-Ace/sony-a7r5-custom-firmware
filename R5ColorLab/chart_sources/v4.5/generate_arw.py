"""Build an experimental 100 MP Sony ARW from the existing float chart design.

Uses Sony's four-component 14-bit lossless JPEG storage. All public and
encrypted geometry/WB fields are patched in place; original files are read-only.
"""
from pathlib import Path
import hashlib, importlib.util, inspect, io, json, struct, sys
import numpy as np
from PIL import Image, ImageCms
import tifffile

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
SCRIPTS=ROOT/'research/r5_custom_lut/scripts'
PROJECT=Path('/Users/LOCAL_USER/Documents/ChatGPT/ied软件/索尼RAW转GFX无黑边/源码')
sys.path[:0]=[str(SCRIPTS),str(PROJECT),'/Applications/RawAlchemy.app/Contents/Resources']
from build_synthetic_ljpeg_arw import jpeg
from arw import parse,one,ints,subifd,maker,ifd,crypt
import metadata
from rawpy import _rawpy as rawpy

SOURCE=Path('/Users/LOCAL_USER/Desktop/白平衡对比/DSC00569.ARW')
SOURCE_SHA='def6cb63c9687507c2fa1a532e86cfa2e1219fa066060b79259402c0bbc6198e'
WB_RGGB=[2606,1024,1024,1789]
W,H,TILE=11648,8736,32
X0,Y0=32,20
# Preserve the Sony margin convention, increasing every geometry coherently.
SENSOR_W,SENSOR_H=W+96,H+40
RAW_W,RAW_H=((SENSOR_W+511)//512)*512,((SENSOR_H+511)//512)*512
sha=lambda b:hashlib.sha256(b).hexdigest()

def load_design():
    # The verified floating design is self-contained. Deleted, incorrect RAW
    # containers and their training bundles are never a generation dependency.
    path=OUT/'chart.npz'
    with np.load(path,allow_pickle=False) as z:
        srgb,kinds=z['design_srgb'].copy(),z['kind'].copy()
    return srgb,kinds,path

def build():
    destination=OUT/'SONY-v4.5-100MP-5300K.ARW'
    if destination.exists():raise FileExistsError(destination)
    original=SOURCE.read_bytes();assert sha(original)==SOURCE_SHA
    parsed=parse(original);sub=subifd(parsed);ex,note,_,mk=maker(parsed)
    srgb,kinds,design_path=load_design()
    assert len(srgb)==(W//TILE)*(H//TILE)==99372
    linear=np.where(srgb<=.04045,srgb/12.92,((srgb+.055)/1.055)**2.4)
    with np.load(OUT/'chart.npz',allow_pickle=False) as z:codes=z['sensor_codes'].copy()
    grid=codes.reshape(H//TILE,W//TILE,3)
    assert codes.shape==(99372,3)
    # The donor's SR2 precedes its RAW tiles. Zero only each tile, keeping all
    # metadata offsets valid regardless of the donor's physical ordering.
    changed=bytearray(original)
    for at,n in zip(ints(one(sub,0x144)),ints(one(sub,0x145))):
        assert at+n<=parsed['offset'] or at>=parsed['offset']+parsed['length']
        changed[at:at+n]=bytes(n)
    edits=[]
    def put(entries,tag,values,buffer=changed,base=0):
        e=one(entries,tag);assert e['type'] in (3,4,8,9) and e['count']==len(values)
        fmt={3:'H',4:'I',8:'h',9:'i'}[e['type']]
        at=e['entry']-base+8 if len(e['data'])<=4 else struct.unpack_from('<I',buffer,e['entry']-base+8)[0]-base
        struct.pack_into('<'+fmt*len(values),buffer,at,*values)
        edits.append(dict(tag=hex(tag),entry=e['entry'],before=e['data'].hex(),after=list(values),encrypted=bool(base)))
    for tag,values in [(0x100,[RAW_W]),(0x101,[RAW_H]),(0x116,[RAW_H]),
        (0xc61f,[X0,Y0]),(0xc620,[W,H]),(0x74c7,[X0,Y0]),(0x74c8,[W,H]),
        (0x7038,[W+64,SENSOR_H]),(0x7313,WB_RGGB)]:put(sub,tag,values)
    for tag,value in [(0xa002,W),(0xa003,H)]:put(ex,tag,[value])
    put(mk,0xb02b,[H,W])
    dec=bytearray(parsed['decrypted'])
    put(parsed['sr'],0x74c3,[X0,Y0,X0+W,Y0+H],dec,parsed['offset'])
    put(parsed['sr'],0x7922,[W,H],dec,parsed['offset'])
    for tag in (0x7871,0x788d):put(parsed['sr'],tag,[SENSOR_W],dec,parsed['offset'])
    for group in [parsed['sr']]+parsed['styles']:
        if any(e['tag']==0x7313 for e in group):
            put(group,0x7313,WB_RGGB,dec,parsed['offset'])
    changed[parsed['offset']:parsed['offset']+parsed['length']]=crypt(dec,parsed['key'])
    # Remove stale original XMP dimensions without moving any MakerNote.
    xmp=one(parsed['root'],0x2bc)
    xmp_at=struct.unpack_from('<I',changed,xmp['entry']+8)[0]
    packet=(f'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description xmlns:tiff="http://ns.adobe.com/tiff/1.0/" tiff:ImageWidth="{W}" tiff:ImageLength="{H}"/></rdf:RDF></x:xmpmeta>').encode()
    changed[xmp_at:xmp_at+xmp['count']]=packet.ljust(xmp['count'],b' ')
    icc=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    patches=Image.fromarray(np.rint(srgb.reshape(H//TILE,W//TILE,3)*255).astype('uint8'))
    def add(data,alignment=16):
        changed.extend(bytes((-len(changed))%alignment));at=len(changed);changed.extend(data);return at
    chain=metadata.chain(parsed)
    for index,size in [(0,(1600,1200)),(1,(320,240)),(2,(W,H))]:
        preview=patches.resize(size,Image.Resampling.NEAREST)
        buf=io.BytesIO();preview.save(buf,'JPEG',quality=94,subsampling=0,icc_profile=icc)
        jpeg_bytes=buf.getvalue();at=add(jpeg_bytes)
        entries=chain[index][1]
        put(entries,0x201,[at]);put(entries,0x202,[len(jpeg_bytes)])
        if index==2:
            put(entries,0x100,[W]);put(entries,0x101,[H])
        if index==0:preview.save(OUT/'design-preview.png',icc_profile=icc)
        print('preview',index,size,len(jpeg_bytes),flush=True)
    # Update any thumbnail-size MakerNote to match the actual new preview.
    if any(e['tag']==0xb02c for e in mk):put(mk,0xb02c,[1200,1600])
    count=(RAW_W//512)*(RAW_H//512)
    arrays={tag:add(bytes(count*4),4) for tag in (0x144,0x145)}
    for tag,at in arrays.items():
        e=one(sub,tag);assert e['type']==4
        struct.pack_into('<II',changed,e['entry']+4,count,at)
    image=np.zeros((RAW_H,RAW_W),dtype='uint16')
    yy,xx=np.mgrid[:512,:512];bayer=np.array([[0,1],[1,2]])
    offsets=[];lengths=[]
    for ty in range(RAW_H//512):
        for tx in range(RAW_W//512):
            y=yy+ty*512;x=xx+tx*512
            gy=np.clip((y-Y0)//TILE,0,H//TILE-1)
            gx=np.clip((x-X0)//TILE,0,W//TILE-1)
            tile=grid[gy,gx,bayer[y%2,x%2]].copy()
            tile[(x>=SENSOR_W)|(y>=SENSOR_H)]=0
            image[ty*512:(ty+1)*512,tx*512:(tx+1)*512]=tile
            planes=np.stack([tile[0::2,0::2],tile[0::2,1::2],tile[1::2,0::2],tile[1::2,1::2]],axis=-1)
            payload=jpeg(planes);offsets.append(add(payload));lengths.append(len(payload))
        print('tile row',ty+1,'/',RAW_H//512,flush=True)
    for tag,values in [(0x144,offsets),(0x145,lengths)]:
        struct.pack_into('<'+'I'*count,changed,arrays[tag],*values)
    put(sub,0x111,[offsets[0]]);put(sub,0x117,[len(changed)-offsets[0]])
    with destination.open('xb') as f:f.write(changed)
    del changed
    # Independent LibRaw decoding must recover EVERY mosaic sample exactly.
    raw=rawpy.RawPy();raw.open_file(str(destination));raw.unpack()
    try:
        assert np.array_equal(raw.raw_image,image)
        assert raw.raw_pattern.tolist()==[[0,1],[3,2]]
        assert raw.camera_whitebalance==[2606,1024,1789,1024]
        assert raw.black_level_per_channel==[512]*4 and raw.white_level==16383
        s=raw.sizes
        assert (s.raw_width,s.raw_height)==(RAW_W,RAW_H)
        assert (s.crop_left_margin,s.crop_top_margin,s.crop_width,s.crop_height)==(X0,Y0,W,H),str(s)
        sizes=str(s)
        decoded=raw.postprocess(output_color=rawpy.ColorSpace.raw,user_wb=[1]*4,
            use_camera_wb=False,use_auto_wb=False,no_auto_bright=True,no_auto_scale=True,
            gamma=(1,1),output_bps=16,user_flip=0,demosaic_algorithm=rawpy.DemosaicAlgorithm.LINEAR)
        cy=Y0+np.arange(H//TILE)*TILE+16-s.top_margin
        cx=X0+np.arange(W//TILE)*TILE+16-s.left_margin
        recovered=decoded[cy[:,None],cx[None,:]].reshape(-1,3)
        assert np.array_equal(recovered,codes-512)
        assert recovered.shape==(99372,3)
        # Preview from the decoded sensor, not an unrelated embedded JPEG.
        crop=decoded[Y0-s.top_margin:Y0-s.top_margin+H:8,X0-s.left_margin:X0-s.left_margin+W:8].astype(float)/15871
        display=np.where(crop<=.0031308,crop*12.92,1.055*np.maximum(crop,0)**(1/2.4)-.055)
        Image.fromarray(np.rint(np.clip(display,0,1)*255).astype('uint8')).save(OUT/'decoded-raw-preview.png',icc_profile=icc)
        del decoded
    finally:raw.close()
    # Re-read both clear and encrypted WB/geometry without relying on LibRaw.
    output=destination.read_bytes();again=parse(output);sub2=subifd(again)
    assert one(sub2,0x7313)['data']==one(again['sr'],0x7313)['data']==struct.pack('<4h',*WB_RGGB)
    assert ints(one(again['sr'],0x74c3))==[X0,Y0,X0+W,Y0+H]
    assert ints(one(again['sr'],0x7922))==[W,H]
    # Full 16-bit design reference, distinct from the native 14-bit sensor RAW.
    reference=np.rint(srgb.reshape(H//TILE,W//TILE,3)*65535).astype('uint16')
    reference=np.repeat(np.repeat(reference,TILE,axis=0),TILE,axis=1)
    tifffile.imwrite(OUT/'reference-sRGB16.tiff',reference,photometric='rgb',compression='deflate',
        tile=(256,256),metadata=None,maxworkers=1,extratags=[(34675,'B',len(icc),icc,False)])
    del reference
    assert sha(SOURCE.read_bytes())==SOURCE_SHA
    manifest=dict(schema='synthetic-Sony-standard-chart/100mp-v4.5',file=destination.name,
        sha256=sha(output),bytes=len(output),source=str(SOURCE),source_sha256=SOURCE_SHA,
        source_unchanged=True,source_sensor_pixels_used=False,
        active_crop=[X0,Y0,W,H],active_pixels=W*H,raw_canvas=[RAW_W,RAW_H],
        sensor_extent=[SENSOR_W,SENSOR_H],sony_raw_image_size=[W+64,SENSOR_H],
        patch_size=[TILE,TILE],patch_grid=[W//TILE,H//TILE],samples=len(codes),
        sample_order='existing v4 row-major order, unchanged',WB_RGGB=WB_RGGB,
        raw_bits=14,black=512,white=16383,compression='Sony four-component 14-bit lossless JPEG, 512px Bayer tiles',
        source_color_design='v4 design -> calibrated 5300K WB inverse -> integer Sony PT color preserving mosaic',
        design_script=str(design_path),design_script_sha256=sha(design_path.read_bytes()),
        generator_sha256=sha(Path(__file__).read_bytes()),categories={str(k):int(np.sum(kinds==k)) for k in np.unique(kinds)},
        verification=dict(full_mosaic_pixel_identical=True,all_patch_center_linear_codes_identical=True,
            sensor_values_WB_compensated=True,public_and_encrypted_WB_equal=True,libraw_sizes=sizes),
        native_Edit_validation='pending; custom 100MP geometry, not a factory-supported R5 capture mode',
        limits=['Synthetic linear RGB basis; exact Sony PT sRGB color reproduction is not calibrated.',
                '5300K WB metadata preserved from DSC00569; PT context comparison is simulated.'],
        edits=edits)
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k!='edits'},ensure_ascii=False,indent=2))

if __name__=='__main__':build()
