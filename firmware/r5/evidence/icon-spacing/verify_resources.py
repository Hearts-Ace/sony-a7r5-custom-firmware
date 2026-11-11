from pathlib import Path
import sys,struct,json,hashlib,importlib.util
H=Path(__file__).resolve().parent;R=H.parents[1];P=R/'projects/firmware/development/aspect457-icon8-fix';S=R/'projects/firmware/development/aspect457-icon-spacing'
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
   if label=='1.618:1':
    shift=-2 if v=='23'else -3;g=glyphs[3]
    # Independent expectations: exact old glyph ink translated, original old
    # ink cells cleared; all other pixels outside the combined rectangles exact.
    allowed_pixels={ (top+y)*80+x+dx+shift for y,row in enumerate(g)for dx,c in enumerate(row)if c!=background}|{(top+y)*80+x+dx for y,row in enumerate(g)for dx,c in enumerate(row)}
    assert all(aa==zz for i,(aa,zz)in enumerate(zip(a,z))if i not in allowed_pixels)
    for y,row in enumerate(g):
     for dx,c in enumerate(row):
      if c!=background:assert z[(top+y)*80+x+dx+shift]==old.FN_PALETTE[c]
    optical.append(dict(variant=v,selected=state,label=label,middle_one_left_shift_px=-shift))
   elif v=='32':
    ref=old.FN_STYLES['23']['glyphs']['5'][state]
    for y,row in enumerate(ref):
     for dx,c in enumerate(row):assert z[(top+y+1)*80+x+dx]==old.FN_PALETTE[c]
    assert all(aa==zz for i,(aa,zz)in enumerate(zip(a,z))if not(top<=i//80<top+17 and x<=i%80<x+10))
    optical.append(dict(variant=v,selected=state,label=label,five_exact_23_pixels=True,vertical_center_px=1))
   else:assert before==after
 for label in new.LABELS:
  m=new.menu_pixels(label,v);f=new.icon_pixels(label,False,v)
  for y in range(40):assert m[(y*80+3)*2:(y*80+73)*2]==f[((y+10)*80)*2:((y+10)*80+70)*2]
runtime=[n for n in json.loads((P/'sources.lock.json').read_text())if n.startswith('source/')and Path(n).suffix in('.c','.h','.S','.s','.ld')];assert all(sha(P/n)==sha(S/n)for n in runtime)
png(H/'before-after.png',preview,4,5)
result=dict(passed=True,version='4.57',resource_only=True,banks=rows,optical_changes=optical,strings_exact=68,runtime_sources_exact=len(runtime),playback_payloads_exact=True,plate_dimensions_ids_exact=True,menu_is_fn_slice=True,host_pixel_preview_only=True,camera_io=False,device_tested=False)
(H/'resource-scope.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k not in('banks','optical_changes')}))
