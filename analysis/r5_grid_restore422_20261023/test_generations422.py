"""Candidate CP receive, prepacking and retained generations. Offline only."""
from pathlib import Path
import sys,struct,zlib,json,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(OUT/'import')]
from cp_bridge import CPBridge,packet,STATE,ALLOCATION_BYTES,HEAP_BYTES
from replay_native12_transfer import values,wire
META=json.loads((OUT/'cp/build.json').read_text());CP=OUT/'cp/cp420-grid.NONINSTALLABLE.bin'
OFFSET=META['grid422_offset'];TABLE=META['grid422_table_offset']
MAGIC=0x422671ad;ROWS=[];RETAINED={};NEXT=100
CACHE=META['restore_cache_offset']
assert ALLOCATION_BYTES==META['heap_bytes'] and OFFSET==52352 and TABLE==52360
assert CACHE==207880 and ALLOCATION_BYTES>CACHE
cp=CPBridge(CP);cp.run(packet())
order=struct.unpack_from('<405H',cp.image,0xe8c1d8-0x108000)
assert sorted(order)==list(range(405))
def digest(params):
 return zlib.crc32(struct.pack('<I',sum(1<<(i-1)for i in params))+b''.join(struct.pack('<I',i)+v for i,v in sorted(params.items())))
def send(op,t,m,d,slot=0,payload=b'',status=0,bridge=None):
 bridge=bridge or cp
 replies,*_=bridge.run(wire(op,t,m,slot,d,13 if op==3 else slot,payload))
 assert len(replies)==1,(op,t,len(replies))
 ack=struct.unpack('<11I',replies[0]);assert ack[9]==status,(op,ack,status)
 return ack
def immutable(bridge,p):
 # Diagnostics and transaction owner fields remain mutable.
 return bytes(bridge.cpu.mem_read(p,52252))+bytes(bridge.cpu.mem_read(p+OFFSET,CACHE-OFFSET))
def check_retained():
 for p,raw in RETAINED.items():assert immutable(cp,p)==raw,hex(p)
def packed_model(value,k):
 raw=struct.unpack_from('<1215b',value,1176);words=[0]*405
 for i in range(405):
  v=[raw[c*405+i]for c in range(3)]
  if k<7:v=[(x*(k+1))>>3 for x in v]
  words[order[i]]=sum((x&127)<<(22-10*c)for c,x in enumerate(v))
 return struct.pack('<405I',*words)
def verify(bridge,p,params):
 m=sum(1<<(i-1)for i in params)
 bank=bytes(bridge.cpu.mem_read(p,28768));g=bytes(bridge.cpu.mem_read(p+28768,23484))
 assert struct.unpack_from('<II',bank,8)==(m,m)
 assert struct.unpack_from('<II',g,23012)==(0x4186a11,m)
 assert struct.unpack('<II',bytes(bridge.cpu.mem_read(p+OFFSET,8)))==(MAGIC,m)
 assert bytes(bridge.cpu.mem_read(p+CACHE,ALLOCATION_BYTES-CACHE))==bytes(ALLOCATION_BYTES-CACHE),'new generation restore cache must start empty'
 for i in range(1,13):
  assert bank[64+(i-1)*2392:64+i*2392]==params.get(i,bytes(2392))
  if i in params:
   for k in range(3):assert g[2276+((i-1)*3+k)*576:2276+((i-1)*3+k)*576+516]==params[i][656:1172]
  enabled=i in params and struct.unpack_from('<I',params[i],1172)[0]==1
  for k in range(8):
   actual=bytes(bridge.cpu.mem_read(p+TABLE+((i-1)*8+k)*1620,1620))
   assert actual==(packed_model(params[i],k)if enabled else bytes(1620)),(i,k)
def publish(params,label):
 global NEXT
 t=NEXT;NEXT+=1;m=sum(1<<(i-1)for i in params);d=digest(params)
 old=cp.r(STATE);n=cp.bank_attempts;ack=send(1,t,m,d)
 if ack[8]!=0x35424c53:
  assert cp.r(STATE)==old
  for i,v in sorted(params.items()):send(2,t,m,d,i,v);assert cp.r(STATE)==old
  send(3,t,m,d)
 active=cp.r(STATE);check_retained();verify(cp,active,params)
 RETAINED[active]=immutable(cp,active)
 ROWS.append(dict(label=label,mask=m,active=hex(active),new_allocations=cp.bank_attempts-n,retained=len(RETAINED)))
 return t,m,d,active
p={i:values(i)for i in range(1,13)}
a=publish(p,'all12_names_CC1_block13_Gamma_grid_8levels')
assert publish(p,'same_config_reuse')[3]==a[3]
q=dict(p);v=bytearray(q[2]);v[32]^=1;q[2]=bytes(v)
b=publish(q,'changed_CC1_only');assert a[3]!=b[3]
t=500;m=2;d=digest({2:values(2)});send(1,t,m,d)
send(3,a[0],a[1],a[2],status=2)
send(2,t,m,d,2,values(2));send(3,t,m,d);check_retained()
verify(cp,cp.r(STATE),{2:values(2)});RETAINED[cp.r(STATE)]=immutable(cp,cp.r(STATE))
t=501;other=bytearray(values(2));other[32]^=2;other=bytes(other);different=digest({2:other})
send(1,t,m,different);send(2,t,m,different,2,other);before=cp.r(STATE)
send(1,502,m,d);assert cp.r(0x1a39450)==0
send(3,t,m,different,status=2);assert cp.r(STATE)==before
publish({},'empty_configuration_clears_all')
publish({12:values(12)},'load_after_clear')
# Exact on-disk v3 compact records; codec/layout was independently audited.
bin_path=ROOT/'exports/fl2_fl3_grid_compare_20261023/R5NATIVE.BIN'
raw=bin_path.read_bytes();assert hashlib.sha256(raw).hexdigest()=='b97a8f36a50fb97ee513ed6dbf93f6dd4acdc7c51447c55ba88ee719f9a1512a'
assert struct.unpack_from('<8s6I',raw)==(b'R5NAT12\0',3,128,4928,2,0xc0,0)
assert zlib.crc32(raw[:112]+bytes(4)+raw[116:])==struct.unpack_from('<I',raw,112)[0]
user_params={struct.unpack_from('<I',raw,128+i*2400)[0]:raw[132+i*2400:2524+i*2400]for i in range(2)}
assert set(user_params)=={7,8}
publish(user_params,'exact_user_FL2on_FL3off_BIN')
for i in range(30):
 if cp.r(0x1a39454)>=16:break
 v=bytearray(values(1));v[32]=(v[32]+i)%256
 publish({1:bytes(v)},'bounded_generation_%d'%i)
old=cp.r(STATE);oldraw=immutable(cp,old);v=bytearray(values(1));v[34]^=2
send(1,900,1,digest({1:bytes(v)}),status=6)
assert cp.r(STATE)==old and immutable(cp,old)==oldraw
check_retained()
# Native allocator OOM: do not replace allocation result or generation cap.
small=CPBridge(CP,heap_bytes=4096);small.run(packet())
assert small.native_oom and small.r(STATE)==0 and small.r(STATE+4)==1
small.run(packet(token=2));assert small.bank_attempts==1
limited=CPBridge(CP,heap_bytes=ALLOCATION_BYTES*2+1024);limited.run(packet())
for token in (1000,1001):
 params={1:values(1)}if token==1000 else {2:values(2)}
 mask=sum(1<<(i-1)for i in params);dig=digest(params)
 send(1,token,mask,dig,bridge=limited)
 for slot,value in params.items():send(2,token,mask,dig,slot,value,bridge=limited)
 send(3,token,mask,dig,bridge=limited);verify(limited,limited.r(STATE),params)
old=limited.r(STATE);snap=immutable(limited,old)
send(1,1002,4,digest({3:values(3)}),status=6,bridge=limited)
assert limited.native_oom and limited.r(STATE)==old and immutable(limited,old)==snap
r=dict(schema='r5-grid422-generations/1',passed=True,camera_io=False,cp_sha256=hashlib.sha256(cp.image).hexdigest(),bin_sha256=hashlib.sha256(raw).hexdigest(),rows=ROWS,allocation_bytes=ALLOCATION_BYTES,restore_cache_offset=CACHE,restore_cache_initially_zero=True,synthetic_heap_bytes=HEAP_BYTES,allocation_count=cp.r(0x1a39454),packed_slots=12,packed_level_classes=8,packed_words_per_table=405,all_packed_words_checked=True,all_retired_packed_generations_immutable=True,stale_seal_rejected=True,pending_owner_cancelled_on_reuse=True,empty_Gamma_seal=True,native_initial_and_retained_allocation_OOM_checked=True,resource_failure_status=6,limits=['Native receive/shared allocator instructions execute on synthetic heap; scheduler/queues modeled.','Available device heap, cache coherency, whole-frame atomicity and real image output are unverified.'])
(OUT/'tests').mkdir(exist_ok=True)
(OUT/'tests/generations.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
