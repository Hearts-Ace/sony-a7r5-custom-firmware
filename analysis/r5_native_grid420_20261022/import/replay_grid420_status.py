"""Actual CP task status replies after actual native parameter transactions."""
from pathlib import Path
import json,struct,zlib,hashlib
from cp_bridge import CPBridge,packet,STATE
from replay_native12_transfer import values,wire
H=Path(__file__).resolve().parent;P=H.parent/'cp/cp420-grid.NONINSTALLABLE.bin'
def query(token=9):
 p=struct.pack('<4B7I',0xe9,1,1,32,0x44353252,token,0,0,0,0,0);return p[:28]+struct.pack('<I',zlib.crc32(p))
def reply(bridge,p):
 a,e,_,dispatch,_=bridge.run(p);assert not dispatch and len(a)==1 and len(a[0])==128
 b=a[0];c=bytearray(b);c[28:32]=bytes(4);assert zlib.crc32(c)==struct.unpack_from('<I',b,28)[0];return b
b=CPBridge(P);q=reply(b,query());assert struct.unpack_from('<I',q,16)[0]==0
b.run(packet());v=values(2);mask=2;digest=zlib.crc32(struct.pack('<II',mask,2)+v)
for p in [wire(1,99,mask,0,digest,0),wire(2,99,mask,2,digest,2,v),wire(3,99,mask,0,digest,13)]:
 a,*_=b.run(p);assert struct.unpack_from('<I',a[0],36)[0]==0
q=reply(b,query());assert struct.unpack_from('<5I',q,12)==(0x420,28768,0x35424c53,2,struct.unpack_from('<I',q,28)[0]);assert struct.unpack_from('<4I',q,32)==(2,0,0,0)
# Counters themselves are covered by actual builder/uploader replay. Transport
# this explicit synthetic observation to verify status offset/CRC fidelity.
base=b.r(STATE);d=base+52252;b.cpu.mem_write(d,struct.pack('<8I',2,2,2,0,7,8,9,2));q=reply(b,query());assert struct.unpack_from('<8I',q,36)==(2,2,2,0,7,8,9,2)
for mutation in ('crc','version','reserved','zero_token','short','long'):
 p=bytearray(query());
 if mutation=='crc':p[-1]^=1
 elif mutation=='short':p=p[:-1]
 elif mutation=='long':p+=b'X'
 else:
  if mutation=='version':p[1]=2
  elif mutation=='reserved':p[12]=1
  else:p[8:12]=bytes(4)
  p[28:32]=bytes(4);struct.pack_into('<I',p,28,zlib.crc32(p))
 a,e,_,dispatch,_=b.run(bytes(p));assert not a and not dispatch
(H/'grid_status_replay.json').write_text(json.dumps(dict(passed=True,CP_sha256=hashlib.sha256(P.read_bytes()).hexdigest(),actual_CP_task=True,parameter_transaction=True,hostile_requests=6,limits=['Status snapshots use synthetic RTOS/OSAL. Observation counters are injected for transport checking; actual counter instrumentation tested by grid_replay.json.']),indent=2)+'\n');print('PASS actual CP status + accepted grid + six hostile requests')
