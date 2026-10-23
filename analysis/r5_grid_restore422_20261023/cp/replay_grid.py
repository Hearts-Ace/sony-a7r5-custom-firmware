"""Installed common wrapper -> native controller/packet/AA/upload, all12 looks.

Retired source/guard/validator/retry detours must be byte-exact strict404.
Constructor and unrelated services use the explicit handoff harness fixtures;
405-word packing is independently checked against the original format model.
"""
from pathlib import Path
import hashlib,json,random,struct,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(OUT.parent),str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
import replay_handoff422 as h

sha=lambda b:hashlib.sha256(b).hexdigest()
CP=OUT/'cp420-grid.NONINSTALLABLE.bin';raw=CP.read_bytes();meta=json.loads((OUT/'build.json').read_text())
assert sha(raw)==meta['candidate_sha256']
sy={k:int(v,16) for k,v in meta['symbols'].items()}
stock=(ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin').read_bytes()
config=(ROOT/'exports/fl2_fl3_grid_compare_20261023/R5NATIVE.BIN').read_bytes()
WIRES=[0,3,2,1,16,15,19,20,17,18,5,13]
retired=[(0x230ee0,6),(0x230f0a,2),(0x230f0c,4),(0x2312f0,4),(0x230f62,4)]
for at,n in retired:assert raw[at-0x108000:at-0x108000+n]==stock[at-0x108000:at-0x108000+n],hex(at)
assert raw[0x719f16-0x108000:0x719f1a-0x108000]!=stock[0x719f16-0x108000:0x719f1a-0x108000]

class AllLook(h.Harness):
 def __init__(self,slot,payload,fault=None):
  self.slot=slot;self.payload=payload;self.fault=fault
  super().__init__(raw,config,'candidate',sy)
 def publish_fixture(self,at,grid=None,mask=None):
  u=self.u;mask=(1<<self.slot) if mask is None else mask;self.grid=self.payload
  if self.fault=='missing-slot':mask=1<<((self.slot+1)%12)
  h.w(u,at,0x35424c53,7,mask,mask)
  value=at+64+2392*self.slot
  u.mem_write(value,self.raw[132:2524])
  h.w(u,value+1172,0 if self.fault=='disabled' else 1);u.mem_write(value+1176,self.payload)
  h.w(u,at+28768+23012,0x4186a11);h.w(u,0x1a39448,at,28768)
  u.mem_write(at-16,b'\x96'*16);u.mem_write(at+h.ALLOCATION,b'\x69'*16)
  self.call(sy['r5_grid422_prepare'],at)
  self.prepared_guards=[(at-16,b'\x96'*16),(at+h.ALLOCATION,b'\x69'*16)]
  if self.fault=='not-ready':h.w(u,at+28768+23012,0)
  if self.fault=='not-sealed':h.w(u,at,0)
  self.generation=at;self.grids[at]=self.payload
  self.preparation_checks.append(dict(slot=self.slot+1,mask=mask,production_prepare=True))
 def hook(self,c,pc,n,arg):
  super().hook(c,pc,n,arg)
  if pc==0x24273c:
   c.mem_write(self.context['root']+0x2e,bytes([WIRES[self.slot]]))
  if pc==(sy['r5_grid422_controller']&~1) and self.fault=='wrong-profile':
   c.mem_write(self.context['env']+0x25,b'\x07')

rng=random.Random(422);rows=[]
for slot in range(12):
 for pattern in ('zero','min','max','random'):
  payload=bytes(0 if pattern=='zero' else 192 if pattern=='min' else 63 if pattern=='max' else rng.randrange(-64,64)&255 for _ in range(1215))
  e=AllLook(slot,payload);case=dict(look='FL2',slot=slot+1,pattern=pattern,root1=1,direct=0)
  r=e.frame(case);desc=bytes.fromhex(r['descriptor_hex']);expected=h.model.model(payload,e.order,8)
  pointer=struct.unpack_from('<I',desc,20)[0]
  assert h.B+52360<=pointer<pointer+1620<=h.B+207880,(slot,pattern,hex(pointer))
  assert bytes(e.u.mem_read(pointer,1620))==expected
  assert desc[0]==1 and desc[24]==1 and desc[12]==128
  assert all(x['enable']==1 and x['table_sha256']==sha(expected) for x in r['lanes'])
  assert any(x['pc']=='0x719ef6' for x in r['trace']) and any(x['pc']=='0x230da8' for x in r['trace'])
  d=r['diagnostics'][hex(h.B)];assert d['selected_mask']==d['built_mask']==d['upload_mask']==1<<slot
  assert d['bank_pointer3']==pointer and d['bank_slot3']==slot+1 and d['upload_calls']==2
  assert bytes(e.u.mem_read(h.B+64+2392*slot+1176,1215))==payload
  rows.append(dict(slot=slot+1,pattern=pattern,domain=r['final']['domain'],direct=r['final']['direct'],index=r['final']['index'],packed_sha256=sha(expected),both_AA_lanes=True,raw_unchanged=True,diagnostics=d))

fallback=[]
for fault in ('disabled','not-ready','wrong-profile','foreign-mode','not-sealed','missing-slot','special-transform','invalid-direct-index3'):
 payload=bytes([63])*1215;e=AllLook(6,payload,fault);case=dict(look='FL2',fault=fault)
 if fault=='foreign-mode':case['root3']=2
 if fault=='special-transform':case['special']=1
 if fault=='invalid-direct-index3':case['direct']=2
 r=e.frame(case);desc=bytes.fromhex(r['descriptor_hex']);pointer=struct.unpack_from('<I',desc,20)[0]
 assert not(h.B+52360<=pointer<h.B+207880),(fault,hex(pointer))
 d=r['diagnostics'][hex(h.B)];assert not d['selected_mask'] and not d['built_mask'] and not d['upload_mask'],(fault,d)
 if fault in ('disabled','special-transform'):
  assert desc[0]==0 and pointer==0 and desc[24]==0,(fault,r['final'])
 fallback.append(dict(fault=fault,final=r['final'],diagnostics=d,custom_table_not_admitted=True))
report=dict(passed=True,CP_sha256=sha(raw),camera_io=False,cases=len(rows),fallback_cases=len(fallback),rows=rows,fallback_rows=fallback,
 installed_wrapper_callsite=True,native_controller_packet_AA_two_lanes=True,retired_detours_strict404_exact=True,independent405word_model=True,all12_raw_and_heap_guards=True,
 limits=['Constructor input and unrelated sibling stages/services are explicit synthetic fixtures from replay_handoff422.py; actual installed wrapper/controller/packet/descriptor and AA/uploader/config writer execute.',
 'All12/pattern cases use the evidenced domain6/direct0/index3 route; the complete original route matrix and clear/missing restoration are separate handoff/restore gates.',
 'MMIO is synthetic; no real shutter scheduling, cache coherence, heap headroom or final ISP/JPG pixel result is asserted.'])
(OUT/'grid_replay.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS',len(rows),'all12 installed wrapper/model/two-lane cases +',len(fallback),'admission fallbacks; retired5 detours exact404')
