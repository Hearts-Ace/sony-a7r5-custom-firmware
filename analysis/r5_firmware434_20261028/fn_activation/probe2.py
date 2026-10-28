from pathlib import Path
import sys,json,struct
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'analysis/r5_firmware434_20261028')]
from replay_main_menu425 import VM,RAM,X
AP=ROOT/'analysis/r5_firmware434_20261028/ap/appFw.so'
class PVM(VM):
 def hook(self,u,pc,size,arg):
  at=pc-self.bias;a=[u.reg_read(r)for r in X[:5]]
  if at==0x16d95f0:
   u.mem_write(a[0],bytes([a[1]&255])*a[2]);self.ret(a[0]);return
  if at in (0x2e7d208,0x2e7cee4):self.ret();return
  super().hook(u,pc,size,arg)
vm=PVM(AP,0);vm.facade_use(0x582ca68)
vm.map_at_got(0x5915b80,[(struct.unpack('<Q',vm.im.read(a,8))[0],vm.im.pointer(a+8))for a in range(0x5030590,0x5046300,16)]+[(0x1600+n,vm.sy['r5_filter_menu_rows']+n*128)for n in range(13)],'ptr')
for mid in [0x635,0x1f2]:
 for f in [0x1bd62ac,0x1bd642c,0x1bd54d8,0x1bd59f0]:
  vm.events.clear();vm.trace.clear()
  try:print(hex(mid),hex(f),hex(vm.native(f,mid)),flush=True)
  except Exception as ex:print(hex(mid),hex(f),'FAILED',ex,flush=True);break
# test menu fallback60 and row38 significance, only VM memory
vm.w32(vm.desc+0x60,0x021c6410)
print('PATCH fallback60',hex(vm.native(0x1bd642c,0x635)),flush=True)
vm.w32(vm.desc+0xc,0x021c6410)
print('PATCH menu0c',hex(vm.native(0x1bd642c,0x635)),flush=True)
