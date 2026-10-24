"""Bind rollback425 and removal of menu reload; no device or historical writes."""
from pathlib import Path
import hashlib,io,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'vendor/audit-python'))
from elftools.elf.elffile import ELFFile
OLD=ROOT/'analysis/r5_custom_menu425_refresh_exit_20261024'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert sha(OLD/'ap/appFw.so')==sha(HERE/'baseline425/appFw.so')=='11cd80055a7781eee61663dbc9ef0a8fff74fdeeeb9a6c3a59b8a7de379ac95c'
 changed=[];inherited=[]
 for directory in ('import','menu_research'):
  for p in (OLD/directory).iterdir():
   if p.suffix not in ('.c','.h','.S'):continue
   q=HERE/directory/p.name
   if p.read_bytes()!=q.read_bytes():changed.append(str(q.relative_to(HERE)))
   else:inherited.append(dict(path=str(q.relative_to(ROOT)),sha256=sha(q)))
 assert changed==['menu_research/r5_filter_page425.c'],changed
 source=(HERE/changed[0]).read_text();old=(OLD/changed[0]).read_text()
 for part in ('static unsigned mid(void){return r32(((F0)A(0x28a87e8))());}',
              'g.pvt[8]=(uintptr_t)relayout;',
              '((F2)r64(vt+0x20))(view,1);return p;',
              'r5_osal_alloc(0x90030001u,(void **)&object,0x308,0)',
              'r5_osal_alloc(0x90030001u,(void **)&p,0x5a10,0)'):
  assert part in source and part in old
 assert 'reload' not in source.lower() and '更新滤镜' not in source
 obj=ELFFile(io.BytesIO((HERE/'import/objects/r5_filter_page425.o').read_bytes()))
 symbols={s.name for s in obj.get_section_by_name('.symtab').iter_symbols()}
 assert 'r5_filter_reload_request' not in symbols
 assert 'r5_filter_request' in symbols
 ap=(HERE/'ap/appFw.so').read_bytes()
 assert '更新滤镜'.encode() not in ap
 page=json.loads((HERE/'menu_research/page425_replay.json').read_text())
 assert page['passed'] and page['AP_sha256']==sha(HERE/'ap/appFw.so')
 for row in page['cases']:
  if row['mode'] in ('stock','oom'):continue
  assert row['update_widgets_not_constructed'] and row['update_text_and_touch_hidden'] and row['no_reload_requests']
 assert len([r for r in page['cases']if r['mode']=='removed_update'])==2
 report=dict(passed=True,AP_sha256=sha(HERE/'ap/appFw.so'),baseline425_sha256=sha(OLD/'ap/appFw.so'),
   exact425_reproduced_before_changes=True,production_source_changes=changed,
   no426_427_menu_changes=True,manual_update_text_touch_focus_and_submit_removed=True,
   page_object_has_no_reload_dependency=True,automatic_import_and_worker_unchanged=True,
   inherited_production_sources=inherited,
   limits=['Explicit user rollback preserves425 MID accessor, layout ABI and object allocation; this receipt does not claim fixes from426/427.',
           'PageVM retains425 fixtures; visible removal and input non-submission are offline proofs, not physical LCD or complete scheduler acceptance.'],camera_io=False)
 (HERE/'rollback428_verified.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items()if k not in ('inherited_production_sources','limits')}))
if __name__=='__main__':main()
