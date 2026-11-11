#!/usr/bin/env python3
"""Read-only final AP/source/resource comparison; does not execute firmware."""
from pathlib import Path
import hashlib,json,struct,sys,re,argparse
H=Path(__file__).resolve().parent;R=H.parents[1];P=R/'projects/firmware/development/aspect456-pt'
a=argparse.ArgumentParser();a.add_argument('--build',type=Path,default=H/'full-build-a');a.add_argument('--output',type=Path,default=H/'scope-candidate-a.json');a.add_argument('--suffix',default='');args=a.parse_args();B=args.build.resolve();T=B/'runtime'
sys.path[:0]=[str(R/'vendor/audit-python'),str(R/'analysis/r5_aspect456_20261110/integration'),str(R/'analysis/r5_ui_icons_20261110/resources')]
from inspect_ap import Image
from build_resources import image_records,inflate
from reference_style import menu_pixels,LABELS
sha=lambda b:hashlib.sha256(b).hexdigest()
fs=lambda p:sha(p.read_bytes())
stage='candidate-build'+args.suffix;cp='analysis/r5_filter_pt456_20261110/'+stage+'/appFw-NONINSTALLABLE.so'
new=Image(T/cp);parent=Image(R/'projects/firmware/releases/4.56-aspect-pt-20261110/appFw.so');stock=Image(R/'unpacked/r5/usr_complete/lib/appFw.so')
final_manifest=json.loads((T/('analysis/r5_filter_pt456_20261110/'+stage+'/build.json')).read_text());assert final_manifest['passed'] and sha(new.raw)==final_manifest['sha256']
assert sha(parent.raw)=='470b36805d5c05f847e585100e63bd2517fe0a856e9b78b397826043ecdcde9e'
def bytesat(im,lo,hi):return im.raw[im.offset(lo):im.offset(lo)+hi-lo]
regions=[]
for name,lo,hi in [
 ('Fn select vertical style98',0x414ead8,0x414ead8+98*52),('Fn select horizontal style98',0x414fef8,0x414fef8+98*52),
 ('Fn original controller presenter constructor refresh lifecycle region',0x1db0000,0x1dc0000),
 ('Fn original model output and input region',0x21f0000,0x2200000),
 ('Fn image queries both',0x1bd18e8,0x1bd1ae8),('MENU original row icon query',0x1bd1ae8,0x1bd1b88),
 ('MENU and Fn wrappers',0x1bd5810,0x1bd58a0),('Fn original list producers',0x1bc36f8,0x1bc3a00),
 ('Native dimension category',0x1bc785c,0x1bc78a4),('MENU original producer',0x22df69c,0x22df800),
 ('Native aspect row table four128B',0x3f46600,0x3f46800)]:
 a=bytesat(new,lo,hi);b=bytesat(stock,lo,hi)
 exceptions=[0x1db602c,0x1db648c] if lo==0x1db0000 else []
 differences=[lo+i for i in range(0,hi-lo,4)if a[i:i+4]!=b[i:i+4]]
 assert differences==exceptions,(name,differences)
 if exceptions:
  # Existing crop-preview hooks relocate only; original BLR is preserved by their wrappers.
  ui=json.loads((T/'analysis/r5_aspect456_20261110/ui/contract-build/ui-contract.json').read_text());um=json.loads((T/'analysis/r5_aspect456_20261110/ui/module-build/module.json').read_text())
  for site in exceptions:
   row=next(x for x in ui['patches'] if int(x['va'],16)==site);word=struct.unpack('<I',bytesat(new,site,site+4))[0];imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm
   assert site+imm*4==um['symbols'][row['symbol']]

 regions.append(dict(name=name,lo=hex(lo),hi_exclusive=hex(hi),bytes=len(a),sha256=sha(a),exact_stock=not exceptions,relocated_existing_crop_preview_hooks=[hex(x)for x in exceptions],exact_parent=a==bytesat(parent,lo,hi)))
assert bytesat(new,0x1bc36f8,0x1bc36fc).hex()=='ffc320d1'
# Consumer-bound instructions: no replacement algorithm or emulated fields.
consumers={name:new.disasm(lo,hi) for name,lo,hi in [
 ('MENU row0c query',0x1bd1ae8,0x1bd1b88),('Fn row20 row24 queries',0x1bd18e8,0x1bd1ae8),
 ('MENU icon store',0x22df718,0x22df748),('Fn image text stores',0x1bc3778,0x1bc383c)]}
menu_rel='analysis/r5_aspect456_20261110/ap/r5_aspect_menu.c';menu=(T/menu_rel).read_text();old=(P/'source'/menu_rel).read_text()
expected=old.replace('extern void r5_aspect_original_list(void *,void *,const void *);\n','');expected=expected[:expected.index('void r5_aspect_list_hook(')]
expected=expected.replace('static const uint32_t display_order[8]={0,4,1,6,2,7,5,3};','static const uint32_t display_order[8]={0,4,1,6,2,7,5,3};\n/* MENU small badges use row+0x0c; Fn images stay at +0x20/+0x24. */\nstatic const uint32_t menu_badges[4]={0x02001e80,0x02001e81,0x02001e82,0x02001e83};')
expected=expected.replace('put32(p,8,R5_ASPECT_TEXT_FIRST+k);','put32(p,8,R5_ASPECT_TEXT_FIRST+k);\n        put32(p,0x0c,menu_badges[k]);')
assert menu==expected
assert menu.index('if (n<4) continue;')<menu.index('put32(p,0x0c,menu_badges[k]);')
assert 'put32(p,0x20,R5_ASPECT_ICON_FIRST+k);' in menu and 'put32(p,0x24,R5_ASPECT_ICON_FIRST+k+4);' in menu
header=(T/'analysis/r5_aspect456_20261110/ap/r5_aspect_state.h').read_text();assert '0x02001e90' in header.lower()
contract_proof=[]
for rel in ['ap/integration.json','cancel/candidate-f/contract.json']:
 rel='analysis/r5_aspect456_20261110/'+rel;before=json.loads((P/'source'/rel).read_text());after=json.loads((T/rel).read_text());removed=[x for x in before['patches'] if int(x['va'],16)==0x1bc36f8]
 before['patches']=[x for x in before['patches'] if int(x['va'],16)!=0x1bc36f8];assert after==before and len(removed)==1
 contract_proof.append(dict(path=rel,removed=removed,all_other_fields_exact=True))
# Final runtime resources must equal chosen E output and preserve every prior record.
resource=[];nr=T/'analysis/r5_aspect456_20261110/resources/output-build';pr=R/'analysis/r5_aspect456_20261110/resources/generated-reference-b';er=R/'analysis/r5_ui_icons_20261110/generated-resources-e'
strings=list(nr.glob('string_*.uxc'));assert len(strings)==68
assert all(fs(x)==fs(pr/x.name)==fs(er/x.name) for x in strings)
for ori in ('23','32'):
 name=f'image_00_{ori}_IPSX.uxc';a=(nr/name).read_bytes();old=(pr/name).read_bytes();assert a==(er/name).read_bytes()
 bc,bb,bd,br=image_records(old);ac,ab,ad,ar=image_records(a);assert (bc,bb,bd)==(ac,ab,ad)
 added=set(range(0x02001e80,0x02001e84));assert set(ar)==set(br)|added
 for key,row in br.items():
  q=ar[key];d=bytearray(q['descriptor']);at=q['relative_at']-q['at'];struct.pack_into('<I',d,at,struct.unpack_from('<I',d,at)[0]-80)
  assert bytes(d)==row['descriptor'] and q['payload']==row['payload']
 images=[]
 for key,label in zip(sorted(added),LABELS):
  q=ar[key];w,h=struct.unpack_from('<HH',q['descriptor'],8);assert (w,h)==(76,40)
  pixels,chunks=inflate(q['payload'],80*40*2);assert pixels==menu_pixels(label,ori)
  images.append(dict(id=hex(key),label=label,width=w,height=h,stride=80,pixels_sha256=sha(pixels)))
 resource.append(dict(bank=name,sha256=sha(a),prior_records=len(br),prior_payloads_exact=True,prior_descriptors_exact_except_offset_delta80=True,new_images=images))
# Source transaction blocks: extract braces without importing firmware runtime tests.
def function(source,name):
 m=re.search(r'\b'+re.escape(name)+r'\([^;]*?\)\s*\{',source);assert m,name
 d=1;i=m.end()
 while d:d+=(source[i]=='{')-(source[i]=='}');i+=1
 return source[m.start():i]
fr='analysis/r5_filter_native_style_20261110/r5_filter_page_style.c';fnew=(T/fr).read_text();fbase=(R/'projects/firmware/development/shutter-sound-recovery455/src/menu_research/r5_filter_page425.c').read_text()
fnames=['owned','valid','close_page','r5_filter_parent_refresh425','wait_command','return_parent','finish_command','submit','next','private_input','dispatch','exit_page','destroy','controller_destroy','sound_parent_presenter','sound_menu_event','r5sound_menu_event2d6_443','r5sound_menu_event425']
assert all(function(fbase,n)==function(fnew,n) for n in fnames)
assert 'const struct style *fn=(void *)A(j?0x414fef8:0x414ead8);' in fnew
# Small-pool fallback uses the exact native kind13 typography writes.
small_fields=['w32((uintptr_t)v+0x44,0x0207a00eu);','w32((uintptr_t)v+0x48,row==g.focus?0x0207a001u:0x0207a000u);','w32((uintptr_t)v+0x4c,0x02066026u);w32((uintptr_t)v+0x50,1);']
if args.suffix:
 assert all(q in fnew for q in small_fields)
 style_build=json.loads((T/('analysis/r5_filter_native_style_20261110/'+stage+'/build.json')).read_text())
 assert style_build['sources']['r5_filter_page_style.c']==sha(fnew.encode())
 project_section=next(x for x in style_build['layout']if x['name']=='.text.project')
 plo=int(project_section['va'],16);phi=plo+project_section['size'];project_asm=new.disasm(plo,phi)
 # Thumb-independent AArch64 instructions show the four uint32 stores on private String.
 assert all(x in project_asm for x in ('mov      w25, #0xa000','movk     w25, #0x207, lsl #16','add      w9, w25, #0xe','str      w9, [x8, #0x44]','cinc     w9, w25, eq','str      w9, [x8, #0x48]','mov      x28, #0x6026','movk     x28, #0x206, lsl #16','movk     x28, #1, lsl #32','stur     x28, [x8, #0x4c]'))
 (H/'small-string-final-b.asm').write_text(project_asm+'\n')
# Parent production sources provide the input set; generated runtime files are not conflated.
changed=[];same=[]
for q in sorted((P/'source').rglob('*')):
 if not q.is_file():continue
 rel=q.relative_to(P/'source');n=T/rel;assert n.is_file(),str(rel)
 (same if fs(q)==fs(n) else changed).append(str(rel))
allowed=set(['analysis/r5_aspect456_20261110/'+x for x in ['ap/r5_aspect_menu.c','ap/r5_aspect_wire.S','ap/compile_module.py','ap/integration.json','cancel/candidate-f/contract.json','resources/build_resources.py','resources/reference_style.py','resources/inputs.json']]+[fr,'analysis/r5_filter_native_style_20261110/build_style.py','analysis/r5_aspect456_20261110/full/build_partitions.py','analysis/r5_aspect456_20261110/full/package_candidate.py'])
assert set(changed)<=allowed,sorted(set(changed)-allowed)
# PT source and bound addresses are unchanged; only four PC-relative branches relocate.
ptnew=json.loads((T/('analysis/r5_filter_pt456_20261110/'+stage+'/build.json')).read_text());ptold=json.loads((R/'analysis/r5_filter_pt456_20261110/source-rebuild/runtime/analysis/r5_filter_pt456_20261110/candidate-build/build.json').read_text())
assert ptnew['rx_bytes']==ptold['rx_bytes']==112 and ptnew['bss_bytes']==ptold['bss_bytes']==0
assert ptnew['private_refresh_call']==ptold['private_refresh_call'] and ptnew['native_bindings']==ptold['native_bindings']
def normalized(im,rep):
 start=rep['rx'];end=start+rep['rx_bytes'];text=im.disasm(start,end)
 out=[]
 for line in text.splitlines():
  address,body=line.split(': ',1)
  body=re.sub(r'0x[0-9a-f]+',lambda m:('LOCAL+'+hex(int(m[0],16)-start)) if start<=int(m[0],16)<end else m[0],body)
  out.append(body)
 return out
assert normalized(new,ptnew)==normalized(parent,ptold)
site=ptnew['private_refresh_call'];word=struct.unpack('<I',bytesat(new,site,site+4))[0];imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm
assert word>>26==0b100101 and site+imm*4==ptnew['rx']
parts=json.loads((B/('partitions-build'+args.suffix+'/build.json')).read_text());parent_expected=json.loads((P/'expected_outputs.json').read_text());component=[]
for key in ('CP','AVCAM','MPR'):
 q=parts['components'][key];assert q==parent_expected['components'][key];component.append(dict(name=key,**q,exact_parent=True))
for key in ('nflasha3','nflasha8','nflasha5'):assert parts['partitions'][key]==parent_expected['partitions'][key]
# Reversing every published stage patch binds unchanged parent playback/ui bytes.
chain=[];working=bytearray(new.raw)
for rel in ['analysis/r5_filter_pt456_20261110/'+stage+'/build.json','analysis/r5_filter_native_style_20261110/'+stage+'/build.json']:
 rep=json.loads((T/rel).read_text());assert sha(working)==rep['sha256']
 for p in reversed(rep['patches']):
  off=p['offset'];after=bytes.fromhex(p['after']);before=bytes.fromhex(p['before']);assert working[off:off+len(after)]==after;working[off:off+len(after)]=before
 assert sha(working)==rep['base_sha256'];chain.append(dict(report=rel,reverse_exact=True,base_sha256=rep['base_sha256']))
# Crop/UI object generation identity is source-bound; relocated layout has changed.
oldobj=R/'analysis/r5_filter_pt456_20261110/source-rebuild/runtime/analysis/r5_aspect456_20261110/ui/module-build'
newobj=T/'analysis/r5_aspect456_20261110/ui/module-build'
kept_objects=[x.name for x in oldobj.glob('*.o')if x.name not in ('r5_aspect_menu.o','r5_aspect_wire.o')]
assert all(fs(oldobj/n)==fs(newobj/n)for n in kept_objects)
result=dict(passed=True,kind='STATIC_FINAL_AP_SOURCE_RESOURCE_SCOPE',AP_sha256=sha(new.raw),parent_AP_sha256=sha(parent.raw),stock_AP_sha256=sha(stock.raw),regions=regions,consumers=consumers,removed_Fn_list_detour=contract_proof,native_ratio_copy_source_exact=True,new_MENU_row_icons=['02001e80','02001e81','02001e82','02001e83'],Fn_row_icons_unchanged=['02001e90..02001e93','02001e94..02001e97'],resources=resource,original_68_strings_exact=True,preserved455_filter_functions=fnames,private_style_copies_original_fn=True,parent_production_sources=dict(exact_files=len(same),changed_files=changed),PT=dict(rx_bytes=112,bss_bytes=0,source_exact=True,bindings_exact=True,normalized_instructions_exact=True,private_refresh_site=hex(site),unique_existing_call_target_verified=True,new_rx=hex(ptnew['rx']),parent_rx=hex(ptold['rx'])),unchanged_components=component,unchanged_partitions=['nflasha3','nflasha8','nflasha5'],reverse_chain=chain,unchanged_crop_ui_object_files=kept_objects,small_pool_kind13_parameter_fields_exact=bool(args.suffix),instruction_replay=False,camera_io=False,device_tested=False,limitations=['Static comparisons and host resource decoding do not execute the native Fn producer or observe a physical LCD.','PT helper relocates because preceding modules shrink/grow; normalized instruction semantics and target bindings are equal, raw112 bytes are not all byte-identical.','Existing crop and playback behavior is inherited; full crop/runtime batch and icon/runtime tests previously rejected were not run or bypassed.','Filter dynamic scroll and final native output acceptance are separately owned by root; this report does not assert them passed.'])
args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(passed=True,regions=len(regions),changed_files=changed,AP=result['AP_sha256'])))
