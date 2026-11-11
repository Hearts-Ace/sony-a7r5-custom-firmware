from pathlib import Path
import sys,struct,json,hashlib,importlib.util
H=Path(__file__).resolve().parent;R=H.parents[1];P=R/'projects/firmware/development/aspect457-icon8-fix';S=R/'projects/firmware/development/aspect457-icon-subpixel'
sys.path.insert(0,str(S/'source/analysis/r5_aspect456_20261110/resources'));import build_resources as b,reference_style as new
spec=importlib.util.spec_from_file_location('parent_style',P/'source/analysis/r5_aspect456_20261110/resources/reference_style.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
sys.path.insert(0,str(H));from inspect_glyphs import png
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rows=[];preview=[];optical=[]
exp=json.loads((P/'expected_outputs.json').read_text());manifest=json.loads((H/'resources/manifest.json').read_text())
for item in manifest['files']:
 name=item['name'];p=H/'resources'/name
 if name.startswith('string_'):assert sha(p)==exp['resources'][name];continue
 v=name.split('_')[2];prior=b.image_records((R/'analysis/r5_icon8_fix457_20261111/resources'/name).read_bytes())[3];actual=b.image_records(p.read_bytes())[3];assert set(actual)==set(prior)
 allowed={0x2001e80,0x2001e90,0x2001e94}|({0x2001e83,0x2001e93,0x2001e97}if v=='32'else set());changes=[]
 for rid,a in actual.items():
  o=prior[rid];assert a['descriptor'][:12]==o['descriptor'][:12]
  if a['payload']==o['payload']:continue
  assert rid in allowed;w,h=struct.unpack_from('<HH',a['descriptor'],8);stride=80 if w>=70 else 48
  bef,_=b.inflate(o['payload'],stride*h*2);aft,blocks=b.inflate(a['payload'],stride*h*2)
  changes.append(dict(id=hex(rid),changed_pixels=sum(x!=y for x,y in zip(struct.unpack('<'+str(stride*h)+'H',bef),struct.unpack('<'+str(stride*h)+'H',aft))),blocks=blocks))
 assert {int(x['id'],16)for x in changes}==allowed;rows.append(dict(bank=name,changed_images=changes,all_other_payloads_exact=True))
 for state in (False,True):
  for label in ('1.618:1','1.85:1'):
   before=old.icon_pixels(label,state,v);after=new.icon_pixels(label,state,v);preview.extend([before,after]);a=struct.unpack('<4800H',before);z=struct.unpack('<4800H',after)
   top=23 if v=='23'else 22;hei=15 if v=='23'else 17
   assert all(x==y for i,(x,y)in enumerate(zip(a,z))if not(top<=i//80<top+hei))
   glyphs=[old.REPAIRED_EIGHT[v][state]if c=='8'else old.FN_STYLES[v]['glyphs'][c][state]for c in label];gap=1;text_width=sum(len(g[0])for g in glyphs)+len(glyphs)-1;x=(70-text_width)//2+sum(len(g[0])+gap for g in glyphs[:3])
   background='!'if state else '$';bg=old.FN_PALETTE[background]
   def mix(a,b,wa,total):
    aa=[(a>>sh)&15 for sh in (0,4,8,12)];bb=[(b>>sh)&15 for sh in (0,4,8,12)]
    out=[int((u*(total-wa)+v*wa+total/2)//total)for u,v in zip(aa,bb)]
    return sum(n<<sh for n,sh in zip(out,(0,4,8,12)))
   if label=='1.618:1':
    shift=-1.5 if v=='23'else -3;g=glyphs[3];expected_pixels={}
    for y,row in enumerate(g):
     if v=='23':
      for dx in range(len(row)+1):
       q=old.FN_PALETTE[row[dx]]if dx<len(row)else bg
       t=old.FN_PALETTE[row[dx-1]]if dx else bg
       if q!=bg or t!=bg:expected_pixels[(top+y)*80+x+dx-2]=mix(q,t,1,2)
     else:
      for dx,c in enumerate(row):
       if c!=background:expected_pixels[(top+y)*80+x+dx-3]=old.FN_PALETTE[c]
    allowed_pixels=set(expected_pixels)|{(top+y)*80+x+dx for y,row in enumerate(g)for dx,c in enumerate(row)}
    assert all(aa==zz for i,(aa,zz)in enumerate(zip(a,z))if i not in allowed_pixels)
    assert all(z[i]==q for i,q in expected_pixels.items())
    six=glyphs[2];sx=x-len(six[0])-1
    assert all(z[(top+y)*80+sx+dx]==old.FN_PALETTE[c]for y,row in enumerate(six)for dx,c in enumerate(row)if c!=background)
    optical.append(dict(variant=v,selected=state,label=label,middle_one_left_shift_px=-shift,original_six_ink_exact=True))
   elif v=='32':
    ref=old.FN_STYLES['23']['glyphs']['5'][state]
    for y in range(17):
     fy=y*14/16;lo=int(fy);weight=int(round((fy-lo)*8));hi=min(lo+1,14)
     for dx in range(10):assert z[(top+y)*80+x+dx]==mix(old.FN_PALETTE[ref[lo][dx]],old.FN_PALETTE[ref[hi][dx]],weight,8)
    assert all(aa==zz for i,(aa,zz)in enumerate(zip(a,z))if not(top<=i//80<top+17 and x<=i%80<x+10))
    optical.append(dict(variant=v,selected=state,label=label,five_source_23=True,target_height17=True,endpoint_rows_exact=True,width10=True))
   else:assert before==after
 for label in new.LABELS:
  m=new.menu_pixels(label,v);f=new.icon_pixels(label,False,v)
  for y in range(40):assert m[(y*80+3)*2:(y*80+73)*2]==f[((y+10)*80)*2:((y+10)*80+70)*2]
runtime=[n for n in json.loads((P/'sources.lock.json').read_text())if n.startswith('source/')and Path(n).suffix in('.c','.h','.S','.s','.ld')];assert all(sha(P/n)==sha(S/n)for n in runtime)
png(H/'before-after.png',preview,4,5)
result=dict(passed=True,version='4.57',resource_only=True,banks=rows,optical_changes=optical,strings_exact=68,runtime_sources_exact=len(runtime),playback_payloads_exact=True,plate_dimensions_ids_exact=True,menu_is_fn_slice=True,host_pixel_preview_only=True,camera_io=False,device_tested=False)
(H/'resource-scope.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k not in('banks','optical_changes')}))
