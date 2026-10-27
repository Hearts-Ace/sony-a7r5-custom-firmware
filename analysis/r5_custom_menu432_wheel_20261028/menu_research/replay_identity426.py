"""Actual425 vs426 controller guard, distinct native MID/ROW property addresses."""
from pathlib import Path
import importlib.util,json,hashlib
HERE=Path(__file__).resolve().parent;CAND=HERE.parent;ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('page426',HERE/'replay_page425.py');page=importlib.util.module_from_spec(spec);spec.loader.exec_module(page)
rows=[]
for label,source in [('frozen425',ROOT/'analysis/r5_custom_menu425_refresh_exit_20261024'),('candidate426',CAND)]:
 for bias in [0,0x40000000]:
  page.CAND=source
  for mid,row in [(0x635,0x1607),(0x14c,0x635)]:
   vm=page.PageVM(bias);vm.w32(vm.menu_pid,mid);vm.w32(vm.row_pid,row)
   result=vm.call(vm.sy['r5_filter_controller425'],0,vm.manager,0,0,0,0)
   private=result!=0x123456
   wanted=(row==0x635) if label=='frozen425' else (mid==0x635)
   assert private==wanted,(label,bias,mid,row,result)
   assert (0x28a87e8 if label=='frozen425' else 0x28a8720) in vm.trace
   rows.append(dict(version=label,bias=hex(bias),AP_sha256=hashlib.sha256((source/'ap/appFw.so').read_bytes()).hexdigest(),menu_mid=hex(mid),option_row=hex(row),private_factory=private,stock_delegate=not private,actual_accessor='0x28a87e8' if label=='frozen425' else '0x28a8720'))
report=dict(passed=True,AP_sha256=hashlib.sha256((CAND/'ap/appFw.so').read_bytes()).hexdigest(),cases=len(rows),rows=rows,limits=['Frozen425 and candidate426 compiled factory guards and real original native property accessors execute at two PIE bases.','Only allocator, native stock fallback and native controller ctor body are explicit fixtures. This proves routing identity, not LCD rendering or actual installed AP identity.'])
(HERE/'identity426_replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('passed',len(rows))
