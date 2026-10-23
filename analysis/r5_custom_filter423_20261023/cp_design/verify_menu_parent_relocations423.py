"""Independent exhaustive RELA-table/parent insertion audit, two PIE biases.

This models ELF relocation effects; it does not execute the Sony loader.
"""
from pathlib import Path
import hashlib,importlib.util,io,json,struct,sys,collections
ROOT=Path(__file__).resolve().parents[3];WORK=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'.venv/lib/python3.9/site-packages')]
from elftools.elf.elffile import ELFFile
source=WORK/'menu_parent423.py';spec=importlib.util.spec_from_file_location('parent_under_test',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
path=WORK/'ap/appFw.so';raw=path.read_bytes();audit=json.loads((WORK/'import/module_audit.json').read_text());before=ELFFile(io.BytesIO(raw))
build=json.loads((WORK/'ap/ap_build.json').read_text());rxfile=build['rx_file'];runtime=(WORK/'import/runtime_rx.bin').read_bytes()
assert len(runtime)==audit['rx_bytes']
audit=dict(audit);audit['symbols']=dict(audit['symbols']);stub=audit['rw']+0x100;audit['symbols']['r5_filter_menu_descriptor']=stub
patched,changes,reported=m.patch_menu_parent(raw,rxfile,runtime,audit);after=ELFFile(io.BytesIO(patched))
def dynamic(e):return {t.entry.d_tag:t.entry.d_val for t in e.get_section_by_name('.dynamic').iter_tags()}
def mapped(e,va,n,file_backed=True):
 segs=[s for s in e.iter_segments()if s['p_type']=='PT_LOAD' and s['p_vaddr']<=va and va+n<=s['p_vaddr']+(s['p_filesz']if file_backed else s['p_memsz'])]
 assert len(segs)==1,(hex(va),n,file_backed)
 return segs[0]['p_offset']+va-segs[0]['p_vaddr']
def entries(e,name):return list(struct.iter_unpack('<QQq',e.get_section_by_name(name).data()))
bd,ad=dynamic(before),dynamic(after);old=entries(before,'.rela.dyn');new=entries(after,'.rela.dyn');oldplt=entries(before,'.rela.plt');newplt=entries(after,'.rela.plt')
assert oldplt==newplt and len(new)==len(old)+1
assert bd['DT_RELACOUNT']==ad['DT_RELACOUNT'] and ad['DT_RELASZ']==bd['DT_RELASZ']+24 and ad['DT_RELA']==bd['DT_RELA']
for tag,n in [('DT_RELA',ad['DT_RELASZ']),('DT_JMPREL',ad['DT_PLTRELSZ'])]:
 off=mapped(after,ad[tag],n);section=after.get_section_by_name('.rela.dyn'if tag=='DT_RELA'else'.rela.plt')
 assert off==section['sh_offset'] and ad[tag]==section['sh_addr'] and n==section['sh_size']
assert bd['DT_PLTRELSZ']==ad['DT_PLTRELSZ'] and bd['DT_PLTREL']==ad['DT_PLTREL']==7
assert len({a for a,_,_ in new})==len(new)
lo=m.GROUP+16+2*24;hi=m.GROUP+16+7*24;moved=[]
for i,(original,changed)in enumerate(zip(old,new)):
 target,info,addend=original
 expected=(target+24,info,addend)if lo<=target<hi else original
 assert changed==expected,(i,original,changed)
 if changed!=original:moved.append(i)
assert len(moved)==5 and new[-1]==(m.GROUP+16+2*24+8,1027,stub)
assert all(info==1027 for _,info,_ in new[:ad['DT_RELACOUNT']])
assert len(new)>ad['DT_RELACOUNT'] and new[-1][1]==1027
groupoff=mapped(before,m.GROUP,0x2e0);oldrows=[struct.unpack_from('<3Q',raw,groupoff+16+24*i)for i in range(7)]
newoff=mapped(after,m.GROUP,0x2e0);newrows=[struct.unpack_from('<3Q',patched,newoff+16+24*i)for i in range(8)]
assert struct.unpack_from('<I',patched,newoff+8)[0]==8 and newrows==oldrows[:2]+[(0x635,stub,0)]+oldrows[2:]
assert mapped(after,stub,0xc0,False)>=0
dynsym=before.get_section_by_name('.dynsym');symbols=list(dynsym.iter_symbols())
types=collections.Counter(info&0xffffffff for _,info,_ in new+newplt)
def resolve(entry,bias):
 target,info,addend=entry;kind=info&0xffffffff;sym=info>>32
 # Deterministic external bindings permit checking symbol-index preservation;
 # actual external symbol lookup and loader instructions are outside this test.
 if kind==1027:return bias+addend
 if kind==1031:
  assert sym<len(symbols)
  # A TLSDESC relocation writes a resolver/argument pair. Compare the
  # symbolic binding; actual thread-local allocation and resolver execution
  # belong to the loader and are intentionally outside this audit.
  return ('TLSDESC',sym,addend)
 assert kind in (257,1025,1026),(kind,sym)
 assert sym<len(symbols)
 return 0x6000000000+sym*0x10000+addend
rows=[]
for bias in (0,0x40000000):
 # Exhaustively compare every dynamic/PLT relocation semantic value. Only the
 # five moved destination addresses and one new relative pointer may differ.
 checks=0
 for x,y in zip(old,new):
  assert resolve(x,bias)==resolve(y,bias);checks+=1
 for x,y in zip(oldplt,newplt):
  assert x==y and resolve(x,bias)==resolve(y,bias);checks+=1
 oldrel={a:(info,addend)for a,info,addend in old if m.GROUP<=a<m.GROUP+0x2e0}
 newrel={a:(info,addend)for a,info,addend in new if m.GROUP<=a<m.GROUP+0x2e0}
 for n,row in enumerate(oldrows):
  nn=n if n<2 else n+1
  # The 0x1f6 row stores its descriptor in the third QWORD, unlike the
  # other rows. Compare every relocated and scalar field in all seven.
  for k,value in enumerate(row):
   dest=m.GROUP+16+24*n+8*k;ndest=m.GROUP+16+24*nn+8*k
   oldvalue=resolve((dest,*oldrel[dest]),bias)if dest in oldrel else value
   newvalue=resolve((ndest,*newrel[ndest]),bias)if ndest in newrel else newrows[nn][k]
   assert oldvalue==newvalue
 assert resolve(new[-1],bias)==bias+stub
 rows.append(dict(bias=hex(bias),all_relocations_compared=checks,parent8_rows_correct=True,new_BSS_descriptor=hex(bias+stub),PLT_Dynamic_range_mapped=True))
reverse=bytearray(patched)
for c in reversed(changes):reverse[c['offset']:c['offset']+len(bytes.fromhex(c['before']))]=bytes.fromhex(c['before'])
assert reverse==raw and path.read_bytes()==raw
report=dict(passed=True,input_AP_sha256=hashlib.sha256(raw).hexdigest(),patch_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),audit_file_sha256=hashlib.sha256((WORK/'import/module_audit.json').read_bytes()).hexdigest(),stub_descriptor=hex(stub),dynamic_relocations_before=len(old),dynamic_relocations_after=len(new),PLT_relocations=len(oldplt),types=dict(types),original_fast_relative_count=bd['DT_RELACOUNT'],moved_dyn_indices=moved,rows=rows,full_reverse_exact=True,limits=['ELF ABI relocation-effect simulation at two PIE offsets, with deterministic external symbol bindings; original Sony dynamic-loader instructions are not executed.','Stub BSS descriptor address tests pointer registration/layout only; descriptor initialization, real menu controller and screen rendering are outside this audit.'])
(WORK/'cp_design/menu_parent_relocations423.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
