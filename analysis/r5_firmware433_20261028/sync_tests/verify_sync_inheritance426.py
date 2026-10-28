"""Compare final425 and426 worker closure. No camera or IO execution."""
from pathlib import Path
import hashlib,io,json,sys,struct
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];NEW=HERE.parent;OLD=ROOT/'analysis/r5_custom_menu425_refresh_exit_20261024'
sys.path.insert(0,str(ROOT/'vendor/audit-python'))
from elftools.elf.elffile import ELFFile
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 old=json.loads((OLD/'import/module_audit.json').read_text());new=json.loads((NEW/'import/module_audit.json').read_text())
 b0=(OLD/'ap/appFw.so').read_bytes();b1=(NEW/'ap/appFw.so').read_bytes();e0=ELFFile(io.BytesIO(b0));e1=ELFFile(io.BytesIO(b1))
 sources=[]
 for p in (OLD/'import').iterdir():
  if p.suffix not in ('.c','.h','.S'):continue
  q=NEW/'import'/p.name;assert p.read_bytes()==q.read_bytes(),p.name
  sources.append({'name':p.name,'sha256':sha(q.read_bytes())})
 def key(s):return Path(s['object']).name,s['index'],s['name']
 ns={key(s):s for s in new['sections']};segments=[]
 def read(e,b,v,n):
  for s in e.iter_segments():
   if s['p_type']=='PT_LOAD'and s['p_vaddr']<=v and v+n<=s['p_vaddr']+s['p_filesz']:
    at=s['p_offset']+v-s['p_vaddr'];return b[at:at+n]
  raise AssertionError(hex(v))
 for s in old['sections']:
  if '/import/'not in s['object'] or Path(s['object']).name.startswith(('r5_filter_menu','r5_filter_renderer','r5_filter_page')):continue
  t=ns[key(s)];assert (s['va'],s['size'],s['space'])==(t['va'],t['size'],t['space']),key(s)
  if s['space']=='rx'and s['size']:
   v=int(s['va'],16);before=read(e0,b0,v,s['size']);after=read(e1,b1,v,t['size']);assert before==after,key(s)
   segments.append({'object':key(s)[0],'section':s['name'],'va':s['va'],'bytes':s['size'],'sha256':sha(after)})
 cp=ROOT/'analysis/r5_custom_filter423_20261023/cp/cp423.NONINSTALLABLE.bin';assert sha(cp.read_bytes())=='8b38e753f34b1667d79b69079d911b9e6595f1ce1b873cb8e014437c6b4c494d'
 report={'passed':True,'AP_sha256':sha(b1),'reference_AP_sha256':sha(b0),'CP_sha256':sha(cp.read_bytes()),'all_import_sources_unchanged_from_final425':True,'all_importer_code_constants_BSS_addresses_exact':True,'grid_lifecycle422_preserved_by_frozen_CP_identity':True,'sources':sources,'sections':segments,'limits':['Exact source/compiled closure identity evidence only. The new426 UI has separate current-AP page tests.','Physical LCD/ISP/JPEG and device SD timing are not executed.']}
 (HERE/'sync_inheritance426_verified.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k not in ('sources','sections')}))
if __name__=='__main__':main()
