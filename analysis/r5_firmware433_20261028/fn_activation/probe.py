from pathlib import Path
import sys,json,struct
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'analysis/r5_firmware433_20261028')]
from replay_main_menu425 import VM,RAM,X
AP=ROOT/'analysis/r5_firmware433_20261028/ap/appFw.so'
vm=VM(AP,0)
vm.facade_use(0x582ca68)
for f in [0x1bd70d8,0x1bdc3d0,0x1bd5780,0x1bd5720,0x1bd54d8,0x1bd559c,0x1bd642c,0x1bd5d20,0x1bd59f0]:
 vm.events.clear();vm.trace.clear()
 try:
  v=vm.native(f,0x635);print(hex(f),hex(v),'trace',[hex(x)for x in sorted(vm.trace) if x in [0x1bd912c,0x1bd63b4,0x1bd62ac,0x1bd6384,0x1bcf0d0,0x1bceddc]],flush=True)
 except Exception as ex:
  print(hex(f),'FAILED',ex,flush=True);break
