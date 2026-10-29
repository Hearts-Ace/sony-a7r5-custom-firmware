"""WB-aware RAW synthesis, preserving the previous Sony PT color reference."""
from pathlib import Path
import numpy as np
import sys,struct,json,hashlib,copy
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
WEB=ROOT/'research/r5_custom_lut/web';sys.path[:0]=[str(WEB),str(WEB.parent/'scripts')]
import baseline
from edit_color_pipeline import RuntimeColor
from edit_raw_front import itp_flatfield,as_shot_wb
from perceptual import to_lab,de2000
from rawpy import _rawpy as rawpy
SOURCE=Path('/Users/LOCAL_USER/Desktop/白平衡对比/DSC00569.ARW')
WB_RGGB=(2606,1024,1024,1789)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
 oldpath=ROOT/'analysis/sony_chart_100mp_20261027/chart.npz'
 with np.load(oldpath,allow_pickle=False) as p:design={k:p[k].copy() for k in p.files}
 original=RuntimeColor.from_capture(*baseline.resolve(baseline.PT_ID))
 raw=bytearray(original.raw);struct.pack_into('<4h',raw,0x4a,*WB_RGGB)
 model=RuntimeColor(original.runtime,raw,original.settings,original.area_controls)
 oldcodes=design['sensor_codes'];ref=itp_flatfield(oldcodes,original.raw,original.settings)
 codespace=np.arange(512,16384,dtype=np.uint16)
 lut=itp_flatfield(np.repeat(codespace[:,None],3,axis=1),raw,model.settings).astype(int)
 def inverse(target):
  ans=np.empty_like(target,dtype=np.uint16)
  for ch in range(3):
   idx=np.clip(np.searchsorted(lut[:,ch],target[:,ch]),1,len(lut)-1)
   idx-=np.abs(lut[idx-1,ch]-target[:,ch])<=np.abs(lut[idx,ch]-target[:,ch])
   ans[:,ch]=idx+512
  return ans
 best=inverse(ref)
 reference=original.color_only(np.repeat(original.sscs(ref)[:,None,:],9,axis=1))[:,0]
 reference_lab=to_lab(reference/16383*255)
 def evaluate(c):
  front=model.sscs(itp_flatfield(c,raw,model.settings))
  native=model.color_only(np.repeat(front[:,None,:],9,axis=1))[:,0]
  de=de2000(reference_lab,to_lab(native/16383*255))
  drift=np.mean((itp_flatfield(c,raw,model.settings).astype(float)-ref)**2,axis=1)
  return de+drift*.0005,de,front,native
 scores,_,_,_=evaluate(best)
 # Search only unavoidable local quantization choices; no target LUT or photo
 # is involved. Exact native PT output, not an embedded preview, is scored.
 for dr in (-1,0,1):
  for dg in (-1,0,1):
   for db in (-1,0,1):
    if not (dr or dg or db):continue
    c=inverse(np.clip(ref.astype(int)+[dr,dg,db],0,16383))
    score,_,_,_=evaluate(c);choose=score<scores
    best[choose]=c[choose];scores[choose]=score[choose]
 # Neutral chart steps must remain exactly neutral before the PT subchain.
 gray=design['kind']=='gray'
 common=np.intersect1d(np.intersect1d(lut[:,0],lut[:,1]),lut[:,2])
 values=ref[gray,0].astype(int);at=np.clip(np.searchsorted(common,values),1,len(common)-1)
 at-=np.abs(common[at-1]-values)<=np.abs(common[at]-values)
 best[gray]=inverse(np.repeat(common[at,None],3,axis=1))
 _,delta,front,native=evaluate(best)
 assert not np.any(np.ptp(front[gray],axis=1))
 assert not np.any(np.ptp(native[gray],axis=1))
 assert np.percentile(delta,95)<.05 and delta.max()<1
 design.update(sensor_codes=best,reference_sensor_codes=oldcodes,reference_pt=reference,
               simulated_input=np.repeat(front[:,None,:],9,axis=1),simulated_pt=native,
               raw_wb=np.array(WB_RGGB),version=np.array('4.5'))
 np.savez_compressed(HERE/'chart.npz',**design)
 report=dict(version='4.5',source=str(SOURCE),source_sha256=sha(SOURCE),color_reference=str(oldpath),
  color_reference_sha256=sha(oldpath),wb_kelvin=5300,wb_RGGB=list(WB_RGGB),
  gain_ratio_rgb=[WB_RGGB[i]/WB_RGGB[1] for i in (0,1,3)],
  edit_effective_wb=as_shot_wb(raw,model.settings).tolist(),
  native_reference='previous unity-WB chart, same PT integer color subchain',
  delta_e00=dict(mean=float(delta.mean()),p95=float(np.percentile(delta,95)),maximum=float(delta.max())),
  delta_e00_by_category={str(k):dict(mean=float(delta[design['kind']==k].mean()),maximum=float(delta[design['kind']==k].max())) for k in np.unique(design['kind'])},
  raw_codes_min=best.min(0).tolist(),raw_codes_max=best.max(0).tolist(),
  pt_rgb_max_abs_14bit=np.abs(native.astype(int)-reference.astype(int)).max(0).tolist(),
  gray_all_256_exactly_neutral=True,calibration='WB inverse + exact integer lookup + local PT quantization selection',
  edit_v45_capture_validated=False,limits=['Full Edit v4.5 context not captured; PT downstream context held fixed.', '14-bit RAW quantization prevents universally bit-identical colors.'])
 (HERE/'design-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
