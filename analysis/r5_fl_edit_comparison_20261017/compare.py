"""Read-only source-photo comparison; all outputs beside this script.

Full-resolution 256-bin marginals and pixel RGB errors; reduced-resolution
D65 CIE Lab/CIEDE2000 and color-joint distributions. No exposure correction,
histogram matching, registration warp, or source-photo modification.
"""
from pathlib import Path
import hashlib
import io
import json
import math
import subprocess
import numpy as np
from PIL import Image, ImageCms, ImageDraw, ImageFont, ImageOps

OUT = Path(__file__).resolve().parent
SRC = Path('samples')
EXIF = Path('local-ied-research/tools/Image-ExifTool-13.59/exiftool')
PAIRS = [(430, 'FL'), (431, 'FL2'), (432, 'FL3')]
SMALL = (1584, 1056)  # exact 1/6 dimensions; suppress JPEG/sharpening differences


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(4*1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def to_lab(rgb):
    x = np.asarray(rgb, dtype=np.float64)/255
    x = np.where(x <= .04045, x/12.92, ((x+.055)/1.055)**2.4)
    xyz = x @ np.array([[.4124564,.3575761,.1804375],
                        [.2126729,.7151522,.0721750],
                        [.0193339,.1191920,.9503041]]).T
    xyz /= np.array([.95047,1,1.08883])
    f = np.where(xyz > (6/29)**3, np.cbrt(xyz), xyz/(3*(6/29)**2)+4/29)
    return np.stack([116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])],axis=-1)


def de2000(a, b):
    L1,a1,b1 = a.T; L2,a2,b2 = b.T
    C1=np.hypot(a1,b1); C2=np.hypot(a2,b2); Cm=(C1+C2)/2
    G=.5*(1-np.sqrt(Cm**7/(Cm**7+25**7)))
    ap1=(1+G)*a1; ap2=(1+G)*a2
    cp1=np.hypot(ap1,b1); cp2=np.hypot(ap2,b2)
    hp1=np.mod(np.degrees(np.arctan2(b1,ap1)),360)
    hp2=np.mod(np.degrees(np.arctan2(b2,ap2)),360)
    hp1=np.where(cp1==0,0,hp1); hp2=np.where(cp2==0,0,hp2)
    dl=L2-L1; dc=cp2-cp1
    dh=hp2-hp1
    dh=np.where(cp1*cp2==0,0,np.where(dh>180,dh-360,np.where(dh < -180,dh+360,dh)))
    dH=2*np.sqrt(cp1*cp2)*np.sin(np.radians(dh/2))
    lm=(L1+L2)/2; cm=(cp1+cp2)/2
    hm=np.where(cp1*cp2==0,hp1+hp2,np.where(np.abs(hp1-hp2)<=180,(hp1+hp2)/2,
        np.where(hp1+hp2<360,(hp1+hp2+360)/2,(hp1+hp2-360)/2)))
    T=1-.17*np.cos(np.radians(hm-30))+.24*np.cos(np.radians(2*hm))+.32*np.cos(np.radians(3*hm+6))-.20*np.cos(np.radians(4*hm-63))
    sl=1+.015*(lm-50)**2/np.sqrt(20+(lm-50)**2); sc=1+.045*cm; sh=1+.015*cm*T
    rt=-2*np.sqrt(cm**7/(cm**7+25**7))*np.sin(np.radians(60*np.exp(-((hm-275)/25)**2)))
    return np.sqrt((dl/sl)**2+(dc/sc)**2+(dH/sh)**2+rt*(dc/sc)*(dH/sh))


def hmetrics(a,b):
    p=np.asarray(a,dtype=float);q=np.asarray(b,dtype=float);p/=p.sum();q/=q.sum()
    return {'intersection_percent':float(100*np.minimum(p,q).sum()),
            'bhattacharyya_percent':float(100*np.sqrt(p*q).sum()),
            'pearson':float(np.corrcoef(p,q)[0,1]),
            'wasserstein_code_values':float(np.abs(np.cumsum(p-q)).sum())}


def stats(x):
    return {'mean':float(np.mean(x)),'median':float(np.median(x)),
            'p90':float(np.percentile(x,90)),'p95':float(np.percentile(x,95)),
            'p99':float(np.percentile(x,99))}


def profile_rgb(im):
    p=im.info.get('icc_profile')
    if p:
        profile=ImageCms.ImageCmsProfile(io.BytesIO(p))
        return ImageCms.profileToProfile(im,profile,ImageCms.createProfile('sRGB'),outputMode='RGB'), {
            'embedded_icc_sha256':hashlib.sha256(p).hexdigest(),'description':ImageCms.getProfileDescription(profile).strip()}
    return im.convert('RGB'), {'embedded_icc_sha256':None,'assumption':'sRGB per EXIF ColorSpace'}


def font(size):
    return ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',size)


def plot_hist(results):
    # Pillow generates a standalone raster plot; exact counts also retained in JSON.
    W,H=1800,1190
    im=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(im)
    d.text((35,15),'Camera JPEG vs Sony Edit export | full-resolution distributions',font=font(27),fill='#1c2533')
    d.text((35,55),'Solid: camera   Dashed: Edit   |   X: 8-bit value (0-255)   Y: percent of pixels / bin',font=font(20),fill='#4a5568')
    colors=['#dc3333','#228b43','#3269d1','#3e4654']
    for row,r in enumerate(results):
        for col,ch in enumerate(['R','G','B',"Y'"]):
            ox=70+col*440;oy=150+row*345;pw=385;ph=245
            ha=np.array(r['histograms']['camera'][col],float);hb=np.array(r['histograms']['edit'][col],float)
            ha*=100/ha.sum();hb*=100/hb.sum();ymax=max(ha.max(),hb.max())*1.08
            for frac in [0,.25,.5,.75,1]:
                y=oy+ph-int(frac*ph);d.line((ox,y,ox+pw,y),fill='#e4e9f0',width=1)
                d.text((ox-48,y-9),f'{frac*ymax:.2f}',font=font(13),fill='#697386')
            d.line((ox,oy,ox,oy+ph,ox+pw,oy+ph),fill='#4a5568',width=2)
            for x in [0,64,128,192,255]:
                xx=ox+pw*x/255;d.text((xx-10,oy+ph+9),str(x),font=font(14),fill='#4a5568')
            for h,dashed in [(ha,False),(hb,True)]:
                pts=[(ox+i*pw/255,oy+ph-h[i]*ph/ymax) for i in range(256)]
                if dashed:
                    for k in range(0,254,6):d.line(pts[k:k+4],fill=colors[col],width=3)
                else:d.line(pts,fill=colors[col],width=2)
            m=r['histogram_metrics'][ch]
            d.text((ox,oy-42),f"{r['look']} ({r['number']})  {ch}",font=font(22),fill='#182233')
            d.text((ox,oy+ph+33),f"Overlap {m['intersection_percent']:.2f}% | BC {m['bhattacharyya_percent']:.2f}%",font=font(17),fill='#3b4657')
    im.save(OUT/'histograms.png')


def main():
    # Independent published CIEDE2000 reference pairs (Sharma et al.), not self-comparisons.
    tests=[([50,2.6772,-79.7751],[50,0,-82.7485],2.0425),
           ([50,3.1571,-77.2803],[50,0,-82.7485],2.8615),
           ([50,2.8361,-74.0200],[50,0,-82.7485],3.4412),
           ([50,-1.3802,-84.2814],[50,0,-82.7485],1.0000)]
    for a,b,expected in tests:
        actual=de2000(np.array([a]),np.array([b]))[0]
        assert abs(actual-expected)<.0001,(actual,expected)
    files=[SRC/f'DSC00{n}{suffix}.JPG' for n,_ in PAIRS for suffix in ('','后期导出')]
    args=['perl',str(EXIF),'-j','-G1','-s','-ImageWidth','-ImageHeight','-Orientation','-ColorSpace','-Software','-Model',
          '-CreativeStyle','-ColorMode','-ExposureTime','-FNumber','-ISO','-WhiteBalance','-ColorTemperature',
          '-ExposureCompensation','-Brightness','-Contrast','-Saturation','-Sharpness','-DateTimeOriginal']
    raw=subprocess.run(args+[str(p) for p in files],check=True,capture_output=True,text=True).stdout
    (OUT/'metadata.json').write_text(raw)
    results=[];thumbnails=[];samples=[]
    for n,look in PAIRS:
        ps=[SRC/f'DSC00{n}{suffix}.JPG' for suffix in ('','后期导出')]
        images=[];infos=[]
        for p in ps:
            with Image.open(p) as original:
                im,prof=profile_rgb(ImageOps.exif_transpose(original))
                im.load();images.append(im)
                infos.append({'file':str(p),'bytes':p.stat().st_size,'sha256':sha(p),'size':list(im.size),'profile':prof})
        a,b=images; assert a.size==b.size==(9504,6336)
        hist=[np.array(im.histogram()).reshape(3,256) for im in images]
        yh=[np.zeros(256,dtype=np.int64),np.zeros(256,dtype=np.int64)]
        difsum=np.zeros(3);sqsum=np.zeros(3);signedsum=np.zeros(3);pixels=a.width*a.height
        rgb_sums=[np.zeros(3),np.zeros(3)]
        for y in range(0,a.height,128):
            arrays=[np.asarray(im.crop((0,y,a.width,min(y+128,a.height))),dtype=np.int16) for im in images]
            for i,x in enumerate(arrays):
                Y=np.clip(np.rint(x@np.array([.2126,.7152,.0722])),0,255).astype(np.uint8)
                yh[i]+=np.bincount(Y.ravel(),minlength=256)
                rgb_sums[i]+=x.sum(axis=(0,1),dtype=np.float64)
            diff=arrays[1]-arrays[0]
            difsum+=np.abs(diff).sum(axis=(0,1),dtype=np.float64)
            signedsum+=diff.sum(axis=(0,1),dtype=np.float64)
            sqsum+=(diff.astype(np.float64)**2).sum(axis=(0,1))
        small=[np.asarray(im.resize(SMALL,Image.Resampling.LANCZOS)) for im in images]
        labs=[to_lab(x).reshape(-1,3) for x in small]
        de=de2000(*labs);dl=labs[1]-labs[0]
        yy,xx=np.indices((SMALL[1],SMALL[0]))
        subject=(xx>=SMALL[0]*.32)&(xx<SMALL[0]*.70)&(yy>=SMALL[1]*.24)&(yy<SMALL[1]*.99)
        # Select by camera image alone; no selection by agreement or Edit output.
        colored=subject.ravel() & (np.hypot(labs[0][:,1],labs[0][:,2])>15) & (labs[0][:,0]>5) & (labs[0][:,0]<95)
        regions={}
        for name,mask in [('subject_rectangle',subject.ravel()),('colored_subject',colored)]:
            h=[np.array([np.bincount(x.reshape(-1,3)[mask,k],minlength=256) for k in range(3)]) for x in small]
            regions[name]={'pixels':int(mask.sum()),'fraction_of_frame_percent':float(mask.mean()*100),
                'delta_E00':stats(de[mask]),'fraction_delta_E00_under_2_percent':float((de[mask]<2).mean()*100),
                'Lab_signed_edit_minus_camera':dl[mask].mean(axis=0).tolist(),
                'rgb_histogram_overlap_mean_percent':float(np.mean([hmetrics(h[0][k],h[1][k])['intersection_percent'] for k in range(3)])),
                'rgb_histogram_BC_mean_percent':float(np.mean([hmetrics(h[0][k],h[1][k])['bhattacharyya_percent'] for k in range(3)]))}
        joint=[]
        for x in small:
            z=x.astype(np.int32)//16
            joint.append(np.bincount((z[...,0]*256+z[...,1]*16+z[...,2]).ravel(),minlength=4096))
        # Registration diagnostic: gradient maps remove global color/tone offsets.
        edge=[]
        for im in images:
            g=np.asarray(im.resize((792,528),Image.Resampling.LANCZOS).convert('L'),float)
            edge.append(np.hypot(np.diff(g,axis=1,prepend=g[:,:1]),np.diff(g,axis=0,prepend=g[:1,:])))
        corrs=[]
        for dy in range(-3,4):
            for dx in range(-3,4):
                aa=edge[0][6:522,6:786].ravel()
                bb=edge[1][6+dy:522+dy,6+dx:786+dx].ravel()
                corrs.append((float(np.corrcoef(aa,bb)[0,1]),dx,dy))
        best=max(corrs)
        r={'number':n,'look':look,'files':infos,
           'histogram_metrics':{ch:hmetrics(hist[0][i],hist[1][i]) for i,ch in enumerate(['R','G','B'])},
           'histograms':{'camera':[v.tolist() for v in hist[0]]+[yh[0].tolist()],
                         'edit':[v.tolist() for v in hist[1]]+[yh[1].tolist()]},
           'mean_rgb_camera':(rgb_sums[0]/pixels).tolist(),'mean_rgb_edit':(rgb_sums[1]/pixels).tolist(),
           'rgb_signed_edit_minus_camera':(signedsum/pixels).tolist(),
           'rgb_MAE_full_resolution':(difsum/pixels).tolist(),
           'rgb_PSNR_full_resolution_dB':float(10*np.log10(255**2/np.mean(sqsum/pixels))),
           'joint_RGB_16bins_each':{k:v for k,v in hmetrics(joint[0],joint[1]).items() if k in ('intersection_percent','bhattacharyya_percent')},
           'regions':regions,
           'Lab_sample_size':list(SMALL),'delta_E00':stats(de),
           'fraction_delta_E00_under_1_percent':float((de<1).mean()*100),
           'fraction_delta_E00_under_2_percent':float((de<2).mean()*100),
           'fraction_delta_E00_under_3_percent':float((de<3).mean()*100),
           'Lab_signed_edit_minus_camera':dl.mean(axis=0).tolist(),
           'Lab_mean_absolute_L_difference':float(np.abs(dl[:,0]).mean()),
           'Lab_chroma_plane_distance':stats(np.hypot(dl[:,1],dl[:,2])),
           'registration':{'diagnostic_size':[792,528],'search_offsets_pixels':[-3,3],
                           'best_dx':best[1],'best_dy':best[2],'best_edge_pearson':best[0],
                           'zero_offset_edge_pearson':next(c[0] for c in corrs if c[1:]==(0,0)),
                           'warp_applied':False}}
        r['histogram_metrics']["Y'"]=hmetrics(yh[0],yh[1])
        r['RGB_histogram_overlap_mean_percent']=float(np.mean([r['histogram_metrics'][ch]['intersection_percent'] for ch in ['R','G','B']]))
        r['RGB_histogram_BC_mean_percent']=float(np.mean([r['histogram_metrics'][ch]['bhattacharyya_percent'] for ch in ['R','G','B']]))
        results.append(r);samples.append(small)
        thumbnails.append([im.resize((690,460),Image.Resampling.LANCZOS) for im in images])
        heat=np.clip(de.reshape(SMALL[1],SMALL[0])/5,0,1)
        # Blue->yellow->red heatmap, fixed 0..5 across all three rows.
        heatrgb=np.stack([np.clip(2*heat,0,1),1-np.abs(2*heat-1),np.clip(1-2*heat,0,1)],axis=-1)
        Image.fromarray((heatrgb*255).astype(np.uint8)).save(OUT/f'{n}_deltaE00.png')
        print(json.dumps({k:r[k] for k in ['number','look','RGB_histogram_overlap_mean_percent','RGB_histogram_BC_mean_percent','delta_E00','registration']},ensure_ascii=False),flush=True)
        for im in images:im.close()
    # Cross-look values are context only: three exposures were taken at different times.
    cross=[]
    for i in range(3):
        for j in range(i+1,3):
            ca=to_lab(samples[i][0]).reshape(-1,3);cb=to_lab(samples[j][0]).reshape(-1,3)
            cross.append({'looks':[results[i]['look'],results[j]['look']],
                          'RGB_histogram_BC_mean_percent':float(np.mean([hmetrics(results[i]['histograms']['camera'][k],results[j]['histograms']['camera'][k])['bhattacharyya_percent'] for k in range(3)])),
                          'delta_E00':stats(de2000(ca,cb)),
                          'limitation':'Different exposures/times; no geometric registration, not an isolated look effect.'})
    report={'method':{'sources_untouched':True,'camera_operations':False,
            'full_resolution_histogram_bins':256,'rgb_histograms':'sRGB encoded values, normalized by pixel count',
            'Y_histogram':"Rounded gamma-encoded Y'=0.2126R+0.7152G+0.0722B; not linear luminance",
            'histogram_overlap':'sum(min(p,q))*100; bin-sensitive, not percent identical colors',
            'bhattacharyya':'sum(sqrt(p*q))*100; distribution affinity, not accuracy or percent identical pixels',
            'Lab':'sRGB IEC transfer function -> XYZ D65 -> CIE Lab D65; no embedded ICC found expected',
            'delta_E00':'CIEDE2000 kL=kC=kH=1; checked against 4 published Sharma reference pairs',
            'pixel_color_sample':'1584x1056, same LANCZOS resize; no matching/normalization/warp',
            'subject_rectangle_normalized_xyxy':[.32,.24,.70,.99],
            'colored_subject_mask':'Inside subject rectangle; camera Lab chroma >15 and 5<L*<95; same mask on both members of pair',
            'limitations':['One scene per look, not all scenes or video.',
                'Metadata is evidence of saved tags, not a complete Edit adjustment history.',
                'Different JPEG quantization, demosaic, denoise and sharpening can cause residual differences.',
                'Downsampled DeltaE suppresses fine detail differences; full-resolution RGB errors reported separately.',
                'Histogram similarity ignores positions; paired spatial metrics are included.']},
            'pairs':results,'cross_look_context':cross,'script_sha256':sha(Path(__file__))}
    (OUT/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    sheet=Image.new('RGB',(1430,1550),'white');d=ImageDraw.Draw(sheet)
    for i,((n,look),thumbs) in enumerate(zip(PAIRS,thumbnails)):
        y=15+i*510
        for j,t in enumerate(thumbs):
            x=15+j*710
            d.text((x,y),f'{n}  {look}  |  '+('Camera JPEG' if j==0 else 'Sony Edit export'),font=font(23),fill='#1d2532')
            sheet.paste(t,(x,y+36))
    sheet.save(OUT/'contact_sheet.jpg',quality=93)
    roi=thumbnails[0][0].copy();rd=ImageDraw.Draw(roi)
    rd.rectangle((int(.32*690),int(.24*460),int(.70*690),int(.99*460)),outline='#ffcf00',width=3)
    roi.save(OUT/'subject_region.jpg',quality=93)
    plot_hist(results)


if __name__=='__main__':
    main()
