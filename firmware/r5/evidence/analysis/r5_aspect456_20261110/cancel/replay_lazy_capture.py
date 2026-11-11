#!/usr/bin/env python3
from pathlib import Path
import sys,json,struct,hashlib
import replay_cancel as c
H=Path(__file__).resolve().parent
cases=[]
for bias in (0x4000000000,0x6000000000):
 for initial in (4,5,6,7):
  r=c.Cancel(bias)
  # Prior-boot persistence is fixture input; no menu getter or commit beforehand.
  r.files['custom_aspect_v2.dat']=bytearray(struct.pack('<4I',0x32505243,2,initial,~initial&0xffffffff))
  r.u.mem_write(r.call(bias+0x2170958),c.p32(c.alias(initial)))
  assert r.token()==0
  r.capture();side=r.u32(r.sy['r5_aspect_saved_selection'])
  r.call(bias+0x2175e7c,c.P);r.event()
  after=r.call('r5_aspect_menu_get');saved=struct.unpack('<4I',r.files['custom_aspect_v2.dat'])[2]
  cases.append(dict(bias=hex(bias),initial=initial,side_cache=side,after=after,saved=saved,correct=after==initial and saved==initial))
receipt=dict(passed=all(x['correct'] for x in cases),cases=cases,AP_sha256=hashlib.sha256(c.AP.read_bytes()).hexdigest())
out=H/sys.argv[1];assert not out.exists();out.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
