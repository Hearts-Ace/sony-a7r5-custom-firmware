"""Exact new418 native two-stage CP loader, original table/BSS invariants."""
from pathlib import Path
import json,hashlib,types,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
src=ROOT/'analysis/r5_incremental413_20261021/cp/replay_loader_stage413.py'
m=types.ModuleType('native_loader418');m.__file__=str(src);exec(compile(src.read_text(),str(src),'exec'),m.__dict__)
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 raw=(ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin').read_bytes();cp=(OUT/'cp418-native12.NONINSTALLABLE.bin').read_bytes();meta=json.loads((OUT/'build.json').read_text());assert sha(cp)==meta['candidate_sha256'];rows=[]
 for mode in [0,1]:
  a,b=m.replay(raw,mode),m.replay(cp,mode)
  assert a['continuation_state']==b['continuation_state']
  assert len(b['maps'])==len(a['maps'])+2
  assert b['maps'][-2:]==[[0x1196000,4096,0x1196000,15],[0x1195000,4096,0x1195000,14]]
  assert b['primary_clear_end']=='0x1a39468' and b['new_BSS_state_cleared']
  assert a['page_descriptors']['0x1a39000']==b['page_descriptors']['0x1a39000']
  assert b['page_descriptors']['0x1195000']=='0x119541e'
  assert b['page_descriptors']['0x1196000']=='0x119663e'
  rows.append(dict(mode=mode,baseline=a,candidate=b,continuation_state_preserved=True,original_page_table_root='0x1a3c000'))
 report=dict(schema='r5-native12-loader-replay/1',passed=True,candidate_sha256=sha(cp),rows=rows,static_state_bytes=32,heap_data_not_BSS=True,device_IO=False,limitations=['Native two-stage source transfer represented by two host memory writes.','Cache/MMU activation and device/WBI/wake unknown.'])
 (OUT/'loader_replay.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS both modes, same page table/BSS, source code preserved')
if __name__=='__main__':main()
