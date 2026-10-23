"""Execute candidate CP receive task across parameter generations. Offline only."""
from pathlib import Path
import sys,struct,zlib,json,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path[:0]=['/private/tmp/r5-grid419-deps',str(OUT/'import')]
import numpy,unicorn,capstone
from cp_bridge import CPBridge,packet,STATE
from replay_native12_transfer import values,wire
cp=CPBridge(OUT/'cp/cp420-grid.NONINSTALLABLE.bin');cp.run(packet())
rows=[];retained={};next_token=100

def digest(params):return zlib.crc32(struct.pack('<I',sum(1<<(i-1)for i in params))+b''.join(struct.pack('<I',i)+v for i,v in sorted(params.items())))
def send(op,t,m,d,slot=0,payload=b'',status=0):
 replies,*_=cp.run(wire(op,t,m,slot,d,13 if op==3 else slot,payload))
 assert len(replies)==1,(op,t,len(replies))
 ack=struct.unpack('<11I',replies[0]);assert ack[9]==status,(op,ack,status)
 return ack

def check_retained():
 for p,raw in retained.items():assert bytes(cp.cpu.mem_read(p,52252))==raw,hex(p)

def publish(params,label):
 global next_token
 t=next_token;next_token+=1;m=sum(1<<(i-1)for i in params);d=digest(params)
 old=cp.r(STATE);n=cp.bank_attempts;ack=send(1,t,m,d)
 if ack[8]!=0x35424c53:
  assert cp.r(STATE)==old
  for i,v in sorted(params.items()):send(2,t,m,d,i,v);assert cp.r(STATE)==old
  send(3,t,m,d)
 active=cp.r(STATE);check_retained();bank=bytes(cp.cpu.mem_read(active,28768));g=bytes(cp.cpu.mem_read(active+28768,23484))
 assert struct.unpack_from('<II',bank,8)==(m,m)
 assert struct.unpack_from('<II',g,23012)==(0x4186a11,m)
 for i in range(1,13):
  assert bank[64+(i-1)*2392:64+i*2392]==params.get(i,bytes(2392))
  if i in params:
   for k in range(3):assert g[2276+((i-1)*3+k)*576:2276+((i-1)*3+k)*576+516]==params[i][656:1172]
 retained[active]=bytes(cp.cpu.mem_read(active,52252))
 rows.append(dict(label=label,mask=m,active=hex(active),new_allocations=cp.bank_attempts-n,retained=len(retained)))
 return t,m,d,active
p={i:values(i)for i in range(1,13)}
a=publish(p,'all_12_names_CC1_block13_Gamma_grid')
assert publish(p,'same_config_reuse')[3]==a[3]
q=dict(p);v=bytearray(q[2]);v[32]^=1;q[2]=bytes(v)
b=publish(q,'changed_CC1_only');assert a[3]!=b[3]
# Late old traffic cannot poison the new pending owner.
t=500;m=2;d=digest({2:values(2)});send(1,t,m,d)
send(3,a[0],a[1],a[2],status=2)
send(2,t,m,d,2,values(2));send(3,t,m,d);check_retained()
# A valid reuse BEGIN invalidates an unfinished different transaction.
t=501;other=bytearray(values(2));other[32]^=2;other=bytes(other);different=digest({2:other})
send(1,t,m,different);send(2,t,m,different,2,other);before=cp.r(STATE)
send(1,502,m,d);assert cp.r(0x1a39450)==0
send(3,t,m,different,status=2);assert cp.r(STATE)==before
publish({},'empty_configuration_clears_all')
publish({12:values(12)},'load_after_clear')
# Exhaustion is explicit and preserves active generation.
for i in range(30):
 if cp.r(0x1a39454)>=16:break
 v=bytearray(values(1));v[32]=(v[32]+i)%256
 publish({1:bytes(v)},'bounded_generation_%d'%i)
old=cp.r(STATE);oldraw=bytes(cp.cpu.mem_read(old,52252));v=bytearray(values(1));v[34]^=2
send(1,900,1,digest({1:bytes(v)}),status=6)
assert cp.r(STATE)==old and bytes(cp.cpu.mem_read(old,52252))==oldraw
check_retained()
r=dict(passed=True,camera_io=False,CP_sha256=hashlib.sha256(cp.image).hexdigest(),rows=rows,allocation_count=cp.r(0x1a39454),stale_seal_rejected=True,pending_owner_cancelled_on_reuse=True,empty_Gamma_seal=True,resource_failure_status=6,limits=['Synthetic 1MiB heap, native receive/shared allocator instructions; scheduler/queues modeled.','Retained lifetime is checked, not whole-frame atomicity or hardware cache refresh.'])
(OUT/'generation_replay.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
