from pathlib import Path
import sys,struct,json,hashlib,importlib.util
H=Path(__file__).resolve().parent;R=H.parents[1];P=R/'projects/firmware/development/aspect457-fn-style';S=R/'projects/firmware/development/aspect457-icon8-fix'
sys.path.insert(0,str(S/'source/analysis/r5_aspect456_20261110/resources'))
import build_resources as b,reference_style as new
spec=importlib.util.spec_from_file_location('old',P/'source/analysis/r5_aspect456_20261110/resources/reference_style.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
sys.path.insert(0,str(H));from inspect_glyphs import png
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rows=[];preview=[]
expected=json.loads((P/'expected_outputs.json').read_text());manifest=json.loads((H/'resources/manifest.json').read_text())
for item in manifest['files']:
 name=item['name'];p=H/'resources'/name
 if name.startswith('string_'):assert sha(p)==expected['resources'][name];continue
 v=name.split('_')[2];src=R/'analysis/r5_ui_icons_20261110/generated-resources-e'/name
 prior=b.image_records(src.read_bytes())[3];actual=b.image_records(p.read_bytes())[3];assert set(actual)==set(prior)
 changes=[]
 for rid,a in actual.items():
  o=prior[rid];assert a['descriptor'][:12]==o['descriptor'][:12]
  if a['payload']==o['payload']:continue
  assert rid in ({0x02001e80,0x02001e83,0x02001e90,0x02001e93,0x02001e94,0x02001e97}|({0x02001e9c,0x02001e9e}if v=='32'else set()))
  w,h=struct.unpack_from('<HH',a['descriptor'],8);stride=80 if w>=70 else 48
  before,_=b.inflate(o['payload'],stride*h*2);after,blocks=b.inflate(a['payload'],stride*h*2)
  changes.append(dict(id=hex(rid),width=w,height=h,blocks=blocks,changed_pixels=sum(x!=y for x,y in zip(struct.unpack('<'+str(stride*h)+'H',before),struct.unpack('<'+str(stride*h)+'H',after)))))
 assert len(changes)==(6 if v=='23'else 8);rows.append(dict(bank=name,changed_images=changes,all_other_payloads_exact=True))
 for st in (False,True):
  for lab in ('1.618:1','1.85:1'):
   orig=old.icon_pixels(lab,st,v);fixed=new.icon_pixels(lab,st,v);preview.extend([orig,fixed])
   a=struct.unpack('<4800H',orig);z=struct.unpack('<4800H',fixed);top=23 if v=='23'else 22;hei=15 if v=='23'else 17
   assert all(x==y for i,(x,y)in enumerate(zip(a,z))if not(top<=i//80<top+hei))
   assert all(z[y*80+x]==a[y*80+x]for y in range(60)for x in list(range(70,80)))
   assert len(new.REPAIRED_EIGHT[v][st][0])==len(old.FN_STYLES[v]['glyphs']['6'][st][0])
   if v=='32':assert all(line[-1] in ('$','!')or len(line)==11 for line in new.REPAIRED_EIGHT[v][st])
 # MENU remains exact translated normal Fn slice.
 for lab in new.LABELS:
  m=new.menu_pixels(lab,v);f=new.icon_pixels(lab,False,v)
  for y in range(40):assert m[(y*80+3)*2:(y*80+73)*2]==f[((y+10)*80)*2:((y+10)*80+70)*2]
# Verify all209 firmware runtime sources, including Fn/filter/crop, remain exact.
runtime=[n for n in json.loads((P/'sources.lock.json').read_text())if n.startswith('source/')and Path(n).suffix in('.c','.h','.S','.s','.ld')];assert all(sha(P/n)==sha(S/n)for n in runtime)
png(H/'before-after.png',preview,4,5)
result=dict(passed=True,version='4.57',resource_only=True,banks=rows,strings_exact=68,runtime_sources_exact=len(runtime),image_ids_dimensions_and_fn_plate_exact=True,menu_is_fn_slice=True,host_pixel_preview_only=True,camera_io=False,device_tested=False)
(H/'resource-scope.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k!='banks'}))
