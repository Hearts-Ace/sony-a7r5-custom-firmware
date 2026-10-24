"""Bind an actually replayed SD implementation to final AP by exact executable identity.

The replay is never relabeled as final-AP execution. Every importer module
section, native import address, compiler command and importer source is compared.
"""
from pathlib import Path
import hashlib,io,json,sys,struct
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
REFERENCE_TREE=ROOT/'analysis/r5_custom_menu425_20261024'
CURRENT_TREE=HERE.parent
def remap_reference_path(value):
 old_relative=str(REFERENCE_TREE.relative_to(ROOT));new_relative=str(CURRENT_TREE.relative_to(ROOT))
 if value==str(REFERENCE_TREE) or value.startswith(str(REFERENCE_TREE)+'/'):
  return str(CURRENT_TREE)+value[len(str(REFERENCE_TREE)):]
 if value==old_relative or value.startswith(old_relative+'/'):
  return new_relative+value[len(old_relative):]
 return value
sys.path.insert(0,str(ROOT/'vendor/audit-python'))
from elftools.elf.elffile import ELFFile
sha=lambda b:hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 reference=HERE/'reference_ap448.so'; final=HERE.parent/'ap/appFw.so'
 before=reference.read_bytes();after=final.read_bytes()
 assert sha(before)=='448c4416b20561cf84cf12ffcdfdb16925d0512b5f8acd534de76e8716e20299'
 previous=read(HERE/'reference_module448.json');current=read(HERE.parent/'import/module_audit.json')
 receipt_path=HERE/'sd425_replay.json'
 assert previous['rx']==current['rx'] and previous['rw']==current['rw']
 assert previous['headers_reserved']==current['headers_reserved']
 # No importer source/header or importer compilation option can change.
 source_rows=[]
 for name,digest in previous['sources'].items():
  if '/import/' not in name:continue
  mapped=remap_reference_path(name)
  assert mapped in current['sources'] and current['sources'][mapped]==digest,name
  assert sha((ROOT/name).read_bytes())==sha((ROOT/mapped).read_bytes())==digest,name
  source_rows.append(dict(path=mapped,reference_path=name,sha256=digest))
 def command_by_object(a):return {Path(c[-1]).name:c for c in a['commands']}
 a,b=command_by_object(previous),command_by_object(current)
 for obj,command in a.items():
  if obj in ('r5_filter_page425.o','r5_filter_menu423.o','r5_filter_renderer423.o','r5_filter_renderer423_asm.o'):continue
  normalized=[remap_reference_path(arg) for arg in command]
  assert b[obj]==normalized,(obj,command,b[obj])
 e0,e1=ELFFile(io.BytesIO(before)),ELFFile(io.BytesIO(after))
 def data_at(elf,data,va,n):
  for s in elf.iter_segments():
   if s['p_type']=='PT_LOAD' and s['p_vaddr']<=va and va+n<=s['p_vaddr']+s['p_filesz']:
    off=s['p_offset']+va-s['p_vaddr'];return data[off:off+n]
  raise AssertionError((hex(va),n))
 def key(s):return (Path(s['object']).name,s['index'],s['name'])
 sections={key(s):s for s in current['sections']};verified=[]
 # Only importer objects belong to this SD execution closure. This covers
 # their code, constants and BSS
 # coordinates referenced by the SD loader, session gate, codec, publication,
 # transport and renderer. New page changes cannot move their addresses.
 for s in previous['sections']:
  if Path(s['object']).name in ('r5_filter_page425.o','r5_filter_menu423.o','r5_filter_renderer423.o','r5_filter_renderer423_asm.o'):continue
  t=sections[key(s)]
  normalized={**s,'object':remap_reference_path(s['object'])}
  assert t==normalized,(key(s),s,t)
  if s['space']=='rx' and s['size']:
   va=int(s['va'],16);old=data_at(e0,before,va,s['size']);new=data_at(e1,after,va,s['size'])
   assert old==new,key(s)
   verified.append(dict(object=Path(s['object']).name,section=s['name'],va=s['va'],bytes=s['size'],sha256=sha(old)))
 # Every external native address used by linked importer keeps its identity.
 native={k:v for k,v in previous['symbols'].items() if not previous['rx']<=v<previous['rx']+65536 and not previous['rw']<=v<previous['rw']+previous['bss_bytes']}
 for k,v in native.items():assert current['symbols'][k]==v,k
 # The original text stays exact except the MID635 secondary resolver branch,
 # whose appended wrapper moves when the independent page grows.
 text0=e0.get_section_by_name('.text');text1=e1.get_section_by_name('.text')
 assert text0.header==text1.header
 old,new=text0.data(),text1.data();base=text0['sh_addr']
 diffs=[base+i for i,(x,y) in enumerate(zip(old,new)) if x!=y]
 assert all(0x1bd2020<=x<0x1bd2024 for x in diffs),[hex(x) for x in diffs[:20]]
 def resolver_target(elf,data):
  pc=0x1bd2020;word=struct.unpack('<I',data_at(elf,data,pc,4))[0]
  assert word>>26==5;delta=word&0x3ffffff
  if delta&(1<<25):delta-=1<<26
  target=pc+delta*4;code=data_at(elf,data,target,24)
  assert code[:16]==struct.pack('<4I',0x7100003f|(0x635<<10),0x54000061,0x2a0103e0,0xd65f03c0)
  # ADRP + terminal B are PC-dependent; their reconstructed destinations agree.
  adrp,last=struct.unpack('<II',code[16:])
  d=((adrp>>29)&3)|(((adrp>>5)&0x7ffff)<<2)
  if d&(1<<20):d-=1<<21
  assert ((target+16)&-4096)+(d<<12)==0x5959000
  d=last&0x3ffffff
  if d&(1<<25):d-=1<<26
  assert target+20+d*4==pc+4
  return target
 targets=[resolver_target(e0,before),resolver_target(e1,after)]
 page_symbols={s['name'].removeprefix('.text.') for s in current['sections'] if Path(s['object']).name=='r5_filter_page425.o' and s['name'].startswith('.text.')}
 rel0=e0.get_section_by_name('.rela.dyn');rel1=e1.get_section_by_name('.rela.dyn')
 assert rel0.header==rel1.header
 rela_changes=[]
 for old,new in zip(struct.iter_unpack('<QQq',rel0.data()),struct.iter_unpack('<QQq',rel1.data())):
  if old==new:continue
  assert old[:2]==new[:2] and old[1]==1027
  names=[k for k,v in previous['symbols'].items() if v==old[2] and current['symbols'].get(k)==new[2]]
  assert names,(old,new)
  assert any(n in page_symbols for n in names),names
  rela_changes.append(dict(target=hex(old[0]),symbol=names[0],before=hex(old[2]),after=hex(new[2])))
 receipt=read(receipt_path)
 assert receipt['passed'] and receipt['AP_sha256']==sha(before) and receipt['cases']==162
 assert receipt['manual_reload_production_wrapper_executed']
 report=dict(passed=True,AP_sha256=sha(after),actual_execution_AP_sha256=sha(before),
  receipt=str(receipt_path.relative_to(ROOT)),receipt_sha256=sha(receipt_path.read_bytes()),
  reference_AP=str(reference.relative_to(ROOT)),reference_AP_sha256=sha(before),
  reference_audit_sha256=sha((HERE/'reference_module448.json').read_bytes()),
  final_audit_sha256=sha((HERE.parent/'import/module_audit.json').read_bytes()),
  replay_cases=162,execution_inherited_by_exact_implementation_identity=True,
  final_AP_executed_by_this_SD_replay=False,
  all_importer_module_sections_exact=True,verified_sections=verified,source_inputs=source_rows,
  reference_tree=str(REFERENCE_TREE.relative_to(ROOT)),current_tree=str(CURRENT_TREE.relative_to(ROOT)),
  compiler_commands_equal_after_exact_tree_prefix_mapping=True,
  native_import_addresses_exact=True,native_text_exact_except_equivalent_secondary_resolver=True,
  secondary_resolver_targets=list(map(hex,targets)),page_relocation_changes=rela_changes,
  limitations=receipt['limitations']+['SD replay executed reference AP448; final AP differs only outside the verified SD execution closure. This receipt is an explicit identity inheritance, not a new final-AP execution.'])
 (HERE/'sd425_final_binding.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k not in ('verified_sections','source_inputs','limitations')}))
if __name__=='__main__':main()
