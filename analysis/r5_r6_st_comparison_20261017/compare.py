"""Compare two supplied Sony Edit ST JPEGs, leaving originals unchanged."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageOps

OUT=Path(__file__).resolve().parent
LIB=OUT.parent/'r5_fl_edit_comparison_20261017/compare.py'
spec=importlib.util.spec_from_file_location('color_metrics',LIB)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
FILES=[m.SRC/'DSC00430_ST.JPG',m.SRC/'DSC00430_ST替换为R6.JPG']
ROI={
    'full_frame':[(0,0,1,1)],
    'subject':[(.32,.24,.70,.99)],
    'tall_toy_skin':[(.558,.373,.571,.392),(.595,.372,.607,.390),(.575,.400,.592,.410)],
    'small_toy_skin':[(.397,.603,.413,.624),(.445,.610,.458,.627),(.414,.629,.437,.641)],
    'cyan_skirt':[(.553,.58,.607,.665)],
    'red_shirt':[(.388,.662,.418,.70)],
    'brown_hair':[(.555,.268,.596,.307)],
    'gray_background':[(.05,.10,.25,.40)],
    'dark_table':[(.05,.93,.25,.98)]}


def mask_rects(rects,w,h):
    mask=np.zeros((h,w),dtype=bool)
    for x0,y0,x1,y1 in rects:mask[int(y0*h):int(y1*h),int(x0*w):int(x1*w)]=True
    return mask.ravel()


def chart(hist):
    im=Image.new('RGB',(1600,650),'white');d=ImageDraw.Draw(im)
    d.text((25,18),'R5 ST vs R6 ST parameters | same R5 RAW, both rendered by Sony Edit',font=m.font(25),fill='#202b3d')
    d.text((25,57),'Solid: R5 ST   Dashed: R6 ST   |   X: 8-bit value   Y: percent of pixels / bin',font=m.font(20),fill='#586477')
    for i,ch in enumerate(['R','G','B',"Y'"]):
        ox=60+i*390;oy=145;pw=330;ph=340
        p,q=[np.array(z[i],float) for z in hist];p*=100/p.sum();q*=100/q.sum();top=max(p.max(),q.max())*1.1
        for f in [0,.25,.5,.75,1]:
            y=oy+ph-ph*f;d.line((ox,y,ox+pw,y),fill='#e0e5ed')
            d.text((ox-46,y-8),f'{f*top:.2f}',font=m.font(14),fill='#677387')
        d.line((ox,oy,ox,oy+ph,ox+pw,oy+ph),fill='#465166',width=2)
        for x in [0,64,128,192,255]:d.text((ox+x*pw/255-8,oy+ph+10),str(x),font=m.font(15),fill='#586477')
        for v,dashed in [(p,False),(q,True)]:
            pts=[(ox+j*pw/255,oy+ph-v[j]*ph/top) for j in range(256)]
            color=['#df3636','#218e45','#326be0','#374354'][i]
            if dashed:
                for j in range(0,253,6):d.line(pts[j:j+4],fill=color,width=3)
            else:d.line(pts,fill=color,width=2)
        hm=m.hmetrics(hist[0][i],hist[1][i])
        d.text((ox,105),ch,font=m.font(24),fill='#1c2736')
        d.text((ox,535),f"Overlap {hm['intersection_percent']:.2f}%",font=m.font(19),fill='#27344b')
        d.text((ox,565),f"BC {hm['bhattacharyya_percent']:.3f}%",font=m.font(19),fill='#27344b')
    im.save(OUT/'histograms.png')


def main():
    assert abs(m.de2000(np.array([[50,2.6772,-79.7751]]),np.array([[50,0,-82.7485]]))[0]-2.0425)<.0001
    tags=['-ImageWidth','-ImageHeight','-Orientation','-ColorSpace','-Software','-Model','-CreativeStyle','-ColorMode',
          '-ExposureTime','-FNumber','-ISO','-WhiteBalance','-ColorTemperature','-ExposureCompensation','-Brightness',
          '-Contrast','-Saturation','-Sharpness','-DateTimeOriginal']
    meta=subprocess.run(['perl',str(m.EXIF),'-j','-G1','-s']+tags+[str(p) for p in FILES],capture_output=True,text=True,check=True)
    (OUT/'metadata.json').write_text(meta.stdout)
    images=[];identities=[]
    for p in FILES:
        with Image.open(p) as src:
            im,profile=m.profile_rgb(ImageOps.exif_transpose(src));im.load();images.append(im)
            identities.append({'file':str(p),'bytes':p.stat().st_size,'sha256':m.sha(p),'size':list(im.size),'profile':profile})
    a,b=images;assert a.size==b.size==(9504,6336)
    hist=[np.array(im.histogram()).reshape(3,256).tolist() for im in images]
    yh=[np.zeros(256,dtype=np.int64) for _ in images]
    absdiff=np.zeros(3);sqdiff=np.zeros(3);signed=np.zeros(3)
    for y in range(0,a.height,128):
        arrays=[np.array(im.crop((0,y,a.width,min(y+128,a.height))),dtype=np.int16) for im in images]
        for i,x in enumerate(arrays):
            Y=np.clip(np.rint(x@np.array([.2126,.7152,.0722])),0,255).astype(np.uint8)
            yh[i]+=np.bincount(Y.ravel(),minlength=256)
        diff=arrays[1]-arrays[0]
        absdiff+=np.abs(diff).sum(axis=(0,1),dtype=float)
        sqdiff+=(diff.astype(float)**2).sum(axis=(0,1))
        signed+=diff.sum(axis=(0,1),dtype=float)
    for i in range(2):hist[i].append(yh[i].tolist())
    small=[np.asarray(im.resize(m.SMALL,Image.Resampling.LANCZOS)) for im in images]
    labs=[m.to_lab(x).reshape(-1,3) for x in small];delta=labs[1]-labs[0];de=m.de2000(*labs)
    regions={}
    for name,rects in ROI.items():
        mask=mask_rects(rects,*m.SMALL)
        ca,cb=[np.hypot(x[mask,1],x[mask,2]) for x in labs]
        regions[name]={
            'normalized_rectangles_xyxy':rects,'pixels':int(mask.sum()),'delta_E00':m.stats(de[mask]),
            'R5_mean_Lab':labs[0][mask].mean(axis=0).tolist(),'R6_mean_Lab':labs[1][mask].mean(axis=0).tolist(),
            'mean_delta_Lab_R6_minus_R5':delta[mask].mean(axis=0).tolist(),
            'mean_chroma_R5':float(ca.mean()),'mean_chroma_R6':float(cb.mean()),
            'mean_delta_chroma':float((cb-ca).mean()),
            'fraction_brighter_percent':float((delta[mask,0]>0).mean()*100),
            'fraction_less_yellow_percent':float((delta[mask,2]<0).mean()*100)}
    colored=mask_rects(ROI['subject'],*m.SMALL)&(np.hypot(labs[0][:,1],labs[0][:,2])>15)&(labs[0][:,0]>5)&(labs[0][:,0]<95)
    regions['colored_subject']={'pixels':int(colored.sum()),'delta_E00':m.stats(de[colored]),
        'mean_delta_Lab_R6_minus_R5':delta[colored].mean(axis=0).tolist(),
        'definition':'R5 C*ab>15, 5<L*<95, inside subject; identical mask for pair'}
    # Edge registration diagnostic, no transform applied.
    edge=[]
    for im in images:
        z=np.asarray(im.resize((792,528),Image.Resampling.LANCZOS).convert('L'),float)
        edge.append(np.hypot(np.diff(z,axis=1,prepend=z[:,:1]),np.diff(z,axis=0,prepend=z[:1,:])))
    corrs=[]
    for dy in range(-3,4):
        for dx in range(-3,4):corrs.append((float(np.corrcoef(edge[0][6:522,6:786].ravel(),edge[1][6+dy:522+dy,6+dx:786+dx].ravel())[0,1]),dx,dy))
    best=max(corrs)
    n=a.width*a.height
    report={'files':identities,'script_sha256':m.sha(Path(__file__)),'metrics_library':str(LIB),'metrics_library_sha256':m.sha(LIB),
        'method':{'histograms':'Full resolution, normalized 256 bins per sRGB channel and gamma Y\u2032',
            'delta_E':'CIEDE2000, D65 Lab, same 1584x1056 LANCZOS sample as preceding FL comparison',
            'delta_direction':'R6 parameter render minus R5 parameter render',
            'ROI_selection':'Fixed geometric regions chosen on R5 source; no difference-driven selection',
            'no_color_or_exposure_matching':True,'no_geometric_warp':True,'camera_operations':False,
            'limitations':['Two Sony Edit exports on R5 RAW; not an R6 camera photograph.',
              'Original capture FL tags remain in both exports; labels do not prove current Edit choice.',
              'User identifies these as ST; original RAW experiment record corroborates intent, not complete Edit history.',
              'Toy face is painted plastic, not real human skin or a calibrated color target.',
              'JPEG comparison alone cannot attribute changes among five parameter blocks.',
              'Downsampled DeltaE suppresses fine-detail errors; original-resolution RGB errors retained.']},
        'registration':{'diagnostic_size':[792,528],'best_dx':best[1],'best_dy':best[2],'edge_pearson':best[0],'warp_applied':False},
        'histograms':{'R5_ST':hist[0],'R6_ST':hist[1]},
        'histogram_metrics':{ch:m.hmetrics(hist[0][i],hist[1][i]) for i,ch in enumerate(['R','G','B',"Y'"])},
        'rgb_MAE_full_resolution':(absdiff/n).tolist(),'rgb_signed_R6_minus_R5':(signed/n).tolist(),
        'rgb_PSNR_full_resolution_dB':float(10*np.log10(255**2/(sqdiff/n).mean())),
        'regions':regions}
    record=Path('local-ied-research/研究记录/20261016_R5替换R6_ST十项/替换与校验记录.json')
    rec=json.loads(record.read_text())
    report['prior_RAW_experiment']={'record':str(record),'record_sha256':m.sha(record),
        'source_sha256':rec['source_sha256'],'output_sha256':rec['output_sha256'],
        'actually_changed_tags':[r['tag'] for r in rec['ten_fields_assigned_from_r6_st'] if r['actually_changed']]}
    # Bind saved experiment record to actual current original and comparison RAW.
    report['prior_RAW_experiment']['current_RAW_hashes_match_record']={role:m.sha(Path(rec[role]))==rec[role+'_sha256'] for role in ['source','output']}
    report['prior_RAW_experiment']['limitation']='Original source matches record; current R6-parameter output has a different whole-file hash. See separate raw_provenance.json for current payload/pixel verification; neither record authenticates complete Edit export history.'
    (OUT/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    chart(hist)
    # Face crops for visual inspection, same position and scale, native JPEG decode.
    crops=[('Tall toy',(.54,.31,.62,.43)),('Small toy',(.37,.53,.48,.65))]
    sheet=Image.new('RGB',(1300,1250),'white');d=ImageDraw.Draw(sheet)
    d.text((20,12),'Fixed face crops | Left: R5 ST | Right: R6 ST parameters',font=m.font(26),fill='#202b3d')
    for row,(name,box) in enumerate(crops):
        y=65+row*585
        d.text((20,y),name,font=m.font(23),fill='#202b3d')
        for i,im in enumerate(images):
            c=im.crop(tuple(int(v*(im.width if k%2==0 else im.height)) for k,v in enumerate(box)))
            c.thumbnail((620,535),Image.Resampling.LANCZOS)
            sheet.paste(c,(20+i*650,y+35))
    sheet.save(OUT/'face_comparison.jpg',quality=95)
    roi=images[0].resize((1188,792),Image.Resampling.LANCZOS);d=ImageDraw.Draw(roi)
    for i,(name,rects) in enumerate(ROI.items()):
        if name in ['full_frame','subject']:continue
        for x0,y0,x1,y1 in rects:
            d.rectangle((int(x0*roi.width),int(y0*roi.height),int(x1*roi.width),int(y1*roi.height)),outline='#ffcc00',width=2)
        x,y=rects[0][:2];d.text((int(x*roi.width),max(0,int(y*roi.height)-17)),name,font=m.font(13),fill='#ffcc00')
    roi.save(OUT/'ROI_selection.jpg',quality=95)
    print(json.dumps({k:v for k,v in report.items() if k not in ['histograms','files','method']},indent=2,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
