"""Copy ARW's active Bayer, levels and WB into a standard Sony DNG."""
from pathlib import Path
import numpy as np
import sys,json,hashlib,io
import tifffile
from rawpy import _rawpy as rawpy
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'research/r5_custom_lut/web'))
SOURCE=HERE/'SONY-v4.5-100MP-5300K.ARW';OUT=HERE/'SONY-v4.5-100MP-5300K.DNG'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 assert not OUT.exists();before=sha(SOURCE)
 r=rawpy.RawPy();r.open_file(str(SOURCE));r.unpack()
 try:
  s=r.sizes;x,y,w,h=s.crop_left_margin,s.crop_top_margin,s.crop_width,s.crop_height
  mosaic=r.raw_image[y:y+h,x:x+w].copy();matrix=np.rint(r.rgb_xyz_matrix[:3]*10000).astype(int)
  wb=np.asarray(r.camera_whitebalance[:3],int)
  assert wb.tolist()==[2606,1024,1789] and r.black_level_per_channel==[512]*4 and r.white_level==16383
 finally:r.close()
 rational=tuple(v for n in matrix.ravel() for v in (int(n),10000))
 neutral=tuple(v for gain in wb for v in (int(wb[1]),int(gain)))
 tags=[(254,'I',1,0,False),(271,'s',0,'SONY',False),(272,'s',0,'ILCE-7RM5',False),(274,'H',1,1,False),
 (33421,'H',2,(2,2),False),(33422,'B',4,(0,1,1,2),False),
 (50706,'B',4,(1,4,0,0),False),(50707,'B',4,(1,1,0,0),False),(50708,'s',0,'Sony ILCE-7RM5',False),
 (50710,'B',3,(0,1,2),False),(50711,'H',1,1,False),(50713,'H',2,(1,1),False),(50714,'H',1,512,False),(50717,'I',1,16383,False),
 (50718,'2I',2,(1,1,1,1),False),(50719,'I',2,(0,0),False),(50720,'I',2,(w,h),False),
 (50721,'2i',9,rational,False),(50728,'2I',3,neutral,False),(50730,'2i',1,(0,1),False),(50778,'H',1,21,False),(50829,'I',4,(0,0,h,w),False)]
 tifffile.imwrite(OUT,mosaic,photometric=32803,metadata=None,byteorder='<',compression=None,rowsperstrip=256,software='R5ColorLab v4.5 standard Bayer DNG',extratags=tags)
 with tifffile.TiffFile(OUT) as f:assert np.array_equal(f.pages[0].asarray(),mosaic)
 r=rawpy.RawPy();r.open_file(str(OUT));r.unpack()
 try:
  assert np.array_equal(r.raw_image,mosaic)
  assert r.black_level_per_channel==[512]*4 and r.white_level==16383
  assert np.allclose(np.asarray(r.camera_whitebalance[:3])/r.camera_whitebalance[1],wb/wb[1],rtol=1e-6)
 finally:r.close()
 assert sha(SOURCE)==before
 report=dict(source=str(SOURCE),source_sha256=before,output=str(OUT),sha256=sha(OUT),bytes=OUT.stat().st_size,width=w,height=h,make='SONY',model='ILCE-7RM5',as_shot_neutral=(wb[1]/wb).tolist(),wb_RGB=wb.tolist(),black=512,white=16383,all_raw_pixels_equal=True,no_pixel_gain_or_scaling=True,adobe_open_verified=False)
 (HERE/'dng-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
