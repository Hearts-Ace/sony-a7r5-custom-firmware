from pathlib import Path
import json,sys,hashlib
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor/audit-python'))
from unicorn import *
from unicorn.arm_const import *
b=(ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin').read_bytes();u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.mem_map(0x100000,0x1200000);u.mem_write(0x108000,b)
rows=[]
for wire in [0,3,2,1,16,15,19,20,17,18,5,13]:
 names=[]
 for start,stop in [(0x24445e,0x2444ec),(0x245438,0x2454a8)]:
  u.reg_write(UC_ARM_REG_R2,wire);u.reg_write(UC_ARM_REG_R0,0x100000);u.emu_start(start|1,stop,count=100)
  assert u.reg_read(UC_ARM_REG_PC)==stop
  ptr=u.reg_read(UC_ARM_REG_R1);names.append(bytes(u.mem_read(ptr,32)).split(b'\0')[0].decode())
 rows.append(dict(ordinal=len(rows)+1,wire=wire,primary=names[0],secondary=names[1]))
assert [r['primary']for r in rows]==['Standard','Portrait','Neutral','Vivid','VV2','FL','FL2','FL3','IN','SH','BW','Sepia']
assert all(r['primary']==r['secondary']for r in rows)
q=dict(passed=True,camera_io=False,CP404_sha256=hashlib.sha256(b).hexdigest(),rows=rows,actual_primary_secondary_string_dispatch=True,not_AP_menu_display_proof=True)
(OUT/'cp_names.json').write_text(json.dumps(q,indent=2)+'\n');print(json.dumps(q))
