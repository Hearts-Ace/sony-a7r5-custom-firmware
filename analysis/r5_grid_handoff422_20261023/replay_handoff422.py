"""Independent source-bound wrapper -> controller -> packet -> AA replay.

Only synthetic CPU RAM/MMIO. Explicit constructor/unrelated-stage fixtures.
CLI takes a CP path; historical images and reports are never overwritten.
"""
from pathlib import Path
import argparse,sys,struct,json,hashlib,itertools
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools'),str(ROOT/'research/r5_custom_lut/scripts')]
from unicorn import *
from unicorn.arm_const import *
from verify_r5_m4strict_cp_cpu import new_cpu
import replay_correction_builder as model
A=0x30000000;B=0x32000000;STOP=A+0x7f000;SP=A+0x7e000
P=A;AA=P+0x20;OUTPUT=P+0x2dec;INPUT=A+0x20000;EXTRA=A+0x28000
DEV0=A+0x30000;DEV1=A+0x31000;COPY=A+0x34000;OWNER=A+0x38000
MMIO0=0xf3830000;MMIO1=0xf3850000;NATIVE_BANK=A+0x40000
w=lambda u,a,*x:u.mem_write(a,struct.pack('<'+'I'*len(x),*x))
r32=lambda u,a:struct.unpack('<I',u.mem_read(a,4))[0]
sha=lambda x:hashlib.sha256(x).hexdigest()
CP421=ROOT/'analysis/r5_runtime_load421_20261022/cp/cp420-grid.NONINSTALLABLE.bin'

class Harness:
 def __init__(self,cp,raw,mode,symbols=None):
  self.cp=cp;self.raw=raw;self.mode=mode;self.symbols=symbols or {};self.u=u=new_cpu(cp)
  u.mem_map(A,0x80000);u.mem_map(B-0x1000,0x401000);u.mem_map(MMIO0,0x10000);u.mem_map(MMIO1,0x10000)
  self.order=struct.unpack_from('<405H',cp,0xe8c1d8-0x108000)
  self.grid=raw[1308:2523];self.frames=[];self.context={};self.case={};self.traces=[];self.fixtures=[];self.transfers=[]
  self.grids={};self.preparation_checks=[]
  self.sibling_stubs={0x72676a,0x73e2ec,0x723022,0x730ad0,0x7370ce,0x73c7d4,0x231eb8,0x71d37c,0x73a034,0x728328,0x7282ec,0x728350,0x7284ce,0x728540,0x72857c,0x729404,0x728c56,0x72867e,0x2443a4,0x7291ac,0x736f90,0x72cfae,0x72ab86,0x72aba4,0x72acc2,0x72ac80,0x72ac96,0x72acd6,0x72ad92,0x72af96,0x72b0a2}
  u.hook_add(UC_HOOK_CODE,self.hook);u.hook_add(UC_HOOK_MEM_INVALID,self.invalid)
  for dev,mmio in ((DEV0,MMIO0),(DEV1,MMIO1)):w(u,dev+0x184,mmio)
  w(u,AA+0xb90,DEV0,DEV0,DEV1,DEV1)
  self.publish_fixture(B)
 def publish_fixture(self,at,grid=None,mask=0xc0):
  u=self.u;grid=self.grid if grid is None else grid
  w(u,at,0x35424c53,7,mask,mask)
  # Exact compact FL2/FL3 records from the user's BIN, including all1140 native bytes.
  for i,record in ((6,self.raw[128:2528]),(7,self.raw[2528:4928])):
   u.mem_write(at+64+2392*i,record[4:2396])
  u.mem_write(at+64+2392*6+1176,grid)
  w(u,at+28768+23012,0x4186a11);w(u,0x1a39448,at,28768)
  if self.symbols:
   # CPU executes candidate prepare; tables are never manufactured by the harness.
   u.mem_write(at-16,b'\x96'*16);u.mem_write(at+207880,b'\x69'*16)
   self.call(self.symbols['r5_grid422_prepare'],at)
   assert u.mem_read(at-16,16)==b'\x96'*16 and u.mem_read(at+207880,16)==b'\x69'*16
   self.prepared_guards=getattr(self,'prepared_guards',[])+[(at-16,b'\x96'*16),(at+207880,b'\x69'*16)]
  self.generation=at
  self.grids[at]=grid
  if self.symbols:
   for k in range(8):
    expected=model.model(grid,self.order,k+1)
    got=bytes(u.mem_read(at+52360+(6*8+k)*1620,1620))
    if mask&(1<<6):assert got==expected,(k,sha(got),sha(expected))
   self.preparation_checks.append(dict(generation=hex(at),classes=8,packed1620_matches_native_model=True,source1215_unchanged=bytes(u.mem_read(at+64+2392*6+1176,1215))==grid))
 def ret(self,c,value=None):
  if value is not None:c.reg_write(UC_ARM_REG_R0,value)
  c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
 def snap(self):
  u=self.u;x=self.context;s=x.get('state',0);packet=x.get('packet',0)
  if not s:return {}
  return dict(root1=u.mem_read(x['root']+1,1)[0],root3=u.mem_read(x['root']+3,1)[0],domain=u.mem_read(x['env']+12,1)[0],direct=u.mem_read(x['env']+6,1)[0],index=u.mem_read(x['meta']+11,1)[0],state_enable=u.mem_read(s+24,1)[0],state_strength=u.mem_read(s+25,1)[0],state_bank=hex(r32(u,s+32)),state_submit=u.mem_read(s+36,1)[0],state_raw_source=hex(r32(u,s+0x184)),state_kind=u.mem_read(s+0x188,1)[0],state_transform=u.mem_read(s+0x189,1)[0],packet_enable=u.mem_read(packet+0x33c,1)[0],packet_bank=hex(r32(u,packet+0x350)),packet_submit=u.mem_read(packet+0x354,1)[0])
 def hook(self,c,pc,n,_):
  q=self.case
  if pc==0x24273c:
   ctx=c.reg_read(UC_ARM_REG_R1);out=c.reg_read(UC_ARM_REG_R2);root=r32(c,ctx);env=r32(c,ctx+4);color=out+0x50
   state=r32(c,color+8);work=r32(c,color+12);meta=r32(c,color+16);packet=c.reg_read(UC_ARM_REG_R5)
   self.context=dict(ctx=ctx,out=out,root=root,env=env,color=color,state=state,work=work,meta=meta,packet=packet)
   holder=r32(c,out+0xf0+0x2c);w(c,holder,packet);w(c,holder+28,A+0x39000)
   assert state==env+0x24
   w(c,work+0x6b0,NATIVE_BANK);w(c,color,OWNER,A+0x3a000,state,work,meta,A+0x3b000);w(c,OWNER,DEV0)
   w(c,ctx+16,A+0x3c000);w(c,color+28,A+0x3d000)
   for off,value in ((1,q.get('root1',1)),(2,q.get('direct',0)),(3,q.get('root3',0)),(0x18,2),(0x2e,19 if q['look']=='FL2' else 20),(0x2f,q.get('level',8)),(0x36,q.get('special',0)),(0x2c4,q.get('gate',0))):c.mem_write(root+off,bytes([value]))
   c.mem_write(state+4,b'\xff');c.mem_write(env+6,bytes([q.get('direct',0)]));c.mem_write(0x16bacb1,bytes([q.get('packet_gate',0)]));c.mem_write(0x16bacb2,struct.pack('<H',q.get('packet_gate16',0)))
   self.fixtures.append(dict(at=hex(pc),meaning='constructor context fields and valid unrelated owner/packet pointers supplied; native wrapper object wiring retained'))
   self.ret(c);return
  if pc==0x230da8 and self.context:
   if self.symbols:self.controller_return=c.reg_read(UC_ARM_REG_LR)&~1
   # Stage6 normally writes domain6. Alternative domain/direct combinations are explicit fixtures.
   if 'domain' in q and not self.symbols:c.mem_write(self.context['env']+12,bytes([q['domain']]))
   if q.get('switch_at_controller'):
    w(c,0x1a39448,q['switch_at_controller'])
  if self.symbols and pc==getattr(self,'controller_return',0) and self.context:
   # Mark the native snapshot's three bytes beside submit. A word store at
   # +0x58 would clobber them; the wrapper must update only submit's byte.
   if c.mem_read(self.context['root']+3,1)[0]==1:
    saved=r32(c,self.context['color']+4);c.mem_write(saved+0x59,b'\x97\xa6\xb5')
    self.snapshot_before=bytes(c.mem_read(saved+0x4c,26))
  if self.symbols and pc==(self.symbols.get('r5_grid422_controller',0)&~1):
   if 'domain' in q:c.mem_write(self.context['env']+12,bytes([q['domain']]))
   if q.get('switch_before_capture'):w(c,0x1a39448,q['switch_before_capture'])
  if pc in (0x73e25a,0x73e6b6,0x719ef6,0x230da8,0x72869a,0x72b020,0x414f44,0x756fd4,0x757068):
   snap=self.snap()
   # The native wrapper's packet was stack-local; AA reuses that stack.
   # Preserve the final descriptor separately, never label reused bytes packet.
   if pc in (0x414f44,0x756fd4,0x757068):snap={k:v for k,v in snap.items() if not k.startswith('packet_')}
   self.traces.append(dict(pc=hex(pc),**snap))
  if pc in self.sibling_stubs:self.ret(c);return
  if pc in (0x71b1ba,0x23454c,0x71f69a):
   count={0x71b1ba:56,0x23454c:8,0x71f69a:36}[pc];c.mem_write(c.reg_read(UC_ARM_REG_R0),bytes(count));self.fixtures.append(dict(at=hex(pc),meaning='unrelated extractor zero-filled',bytes=count));self.ret(c);return
  if pc==0x723252:c.mem_write(c.reg_read(UC_ARM_REG_R0),struct.pack('<2H',1920,1080));self.ret(c);return
  if pc in (0x738896,0x722272,0x736fd2,0x734792):self.ret(c,0);return
  if pc==0x5f51bc:
   dst,src,count=[c.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];assert count<0x40000
   c.mem_write(dst,bytes(c.mem_read(src,count)));self.transfers.append(dict(dst=hex(dst),src=hex(src),bytes=count));self.ret(c);return
  if pc==0x5f58b0:c.mem_write(c.reg_read(UC_ARM_REG_R0),bytes(c.reg_read(UC_ARM_REG_R1)));self.ret(c);return
  if pc in (0xb0de92,0x5dde14,0x5ddf74):self.ret(c);return
 def invalid(self,c,access,address,size,value,_):
  print(json.dumps(dict(case=self.case,pc=hex(c.reg_read(UC_ARM_REG_PC)),address=hex(address),size=size)),flush=True);return False
 def call(self,entry,*args):
  u=self.u
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
  u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,STOP|1);u.emu_start(entry|1,STOP,count=3000000)
  assert u.reg_read(UC_ARM_REG_PC)==STOP,hex(u.reg_read(UC_ARM_REG_PC))
 def frame(self,case,consume=True):
  self.case=case;self.traces=[];self.transfers=[];self.fixtures=[];self.snapshot_before=None
  u=self.u;u.mem_write(NATIVE_BANK-16,b'\xa5'*16);u.mem_write(NATIVE_BANK+4860,b'\x5a'*16)
  self.call(0x717c4c,OUTPUT,INPUT,EXTRA,0)
  desc=bytes(u.mem_read(OUTPUT+0x4e0,28));snap=self.snap();ptr=struct.unpack_from('<I',desc,20)[0];bank=bytes(u.mem_read(ptr,1620)) if ptr else None
  saved=r32(u,self.context['color']+4)
  saved_snapshot=dict(enable=u.mem_read(saved+0x4c,1)[0],strength=u.mem_read(saved+0x4d,1)[0],bank=hex(r32(u,saved+0x54)),submit=u.mem_read(saved+0x58,1)[0],raw_source=hex(r32(u,saved+0x60)),kind=u.mem_read(saved+0x64,1)[0],transform=u.mem_read(saved+0x65,1)[0])
  if self.snapshot_before is not None:
   after=bytes(u.mem_read(saved+0x4c,26));changed={0,1,2,3,8,9,10,11,12}
   assert all(after[i]==self.snapshot_before[i] for i in range(26) if i not in changed),(case,self.snapshot_before.hex(),after.hex())
   assert after[13:16]==b'\x97\xa6\xb5'
   saved_snapshot['untouched_bytes_preserved']=True;saved_snapshot['submit_neighbor_59_5b']=after[13:16].hex()
  assert OUTPUT+0x4e0==AA+0x32ac
  assert desc[0]==snap['packet_enable'] and desc[24]==snap['packet_submit']
  if consume:
   # Real AA consumer reads the descriptor at its native AA+32ac location.
   w(u,AA+0xb90,DEV0,DEV0,DEV1,DEV1)
   if case.get('copy',False):
    u.mem_write(COPY-16,b'\x3c'*16);u.mem_write(COPY+1620,b'\xc3'*16);self.call(0xaac942,AA,COPY)
    assert u.mem_read(COPY-16,16)==b'\x3c'*16 and u.mem_read(COPY+1620,16)==b'\xc3'*16
   else:self.call(0xaac708,AA)
  lanes=[]
  for mmio in (MMIO0,MMIO1):
   table=b''.join(bytes(u.mem_read(mmio+a,n))for a,n in model.CHUNKS)
   lanes.append(dict(enable=r32(u,mmio+0xad00),strength=r32(u,mmio+0xad30),table_sha256=sha(table),table_is_custom=table==model.model(self.grid,self.order,case.get('level',8))))
  assert u.mem_read(NATIVE_BANK-16,16)==b'\xa5'*16 and u.mem_read(NATIVE_BANK+4860,16)==b'\x5a'*16
  for at,guard in getattr(self,'prepared_guards',[]):assert bytes(u.mem_read(at,len(guard)))==guard
  diagnostics={hex(gen):dict(zip(('selected_mask','built_mask','upload_mask','last_reason','select_calls','build_calls','upload_calls','last_slot','bank_pointer0','bank_pointer1','bank_pointer2','bank_pointer3','bank_slot0','bank_slot1','bank_slot2','bank_slot3','copy_mask','copy_calls'),struct.unpack('<18I',u.mem_read(gen+52252,72)))) for gen in self.grids}
  row=dict(case=case,final=snap,saved_snapshot=saved_snapshot,diagnostics=diagnostics,descriptor_hex=desc.hex(),bank_sha256=sha(bank) if bank else None,lanes=lanes,transfers=self.transfers,trace=self.traces,fixtures=self.fixtures,preparation_checks=self.preparation_checks)
  if consume:
   assert all(x['enable']==desc[0] for x in lanes)
   if desc[24] and ptr:
    if case.get('copy',False):assert bytes(u.mem_read(COPY,1620))==bank
    else:assert all(x['table_sha256']==sha(bank) for x in lanes)
  self.frames.append(row);return row

def main():
 p=argparse.ArgumentParser();p.add_argument('--cp',type=Path,default=CP421);p.add_argument('--baseline421',action='store_true');p.add_argument('--output',type=Path);p.add_argument('--symbols',type=Path);a=p.parse_args()
 raw=(ROOT/'exports/fl2_fl3_grid_compare_20261023/R5NATIVE.BIN').read_bytes();assert len(raw)==4928
 cp=a.cp.read_bytes();rows=[];symbols={}
 if not a.baseline421:
  build=json.loads((a.symbols or a.cp.with_name('build.json')).read_text());assert build['candidate_sha256']==sha(cp)
  symbols={k:int(v,16) for k,v in build['symbols'].items()}
 def custom(e,r,grid=None):
  case=r['case'];expected=model.model(e.grid if grid is None else grid,e.order,case.get('level',8));enabled=not(case.get('gate',0) or (case.get('root3',0) and (case.get('packet_gate',0) or case.get('packet_gate16',0))))
  assert r['final']['index']==3 and r['final']['state_submit']==1
  assert r['bank_sha256']==sha(expected),(case,r['final'])
  assert bytes.fromhex(r['descriptor_hex'])[0]==enabled,(case,r['final'])
  assert all(x['enable']==enabled for x in r['lanes'])
  assert r['final']['state_strength']==32 and all(x['strength']==128 for x in r['lanes'])
  if case.get('root3',0)==1:
   saved=r['saved_snapshot'];assert saved['enable']==r['final']['state_enable'] and saved['strength']==32 and saved['bank']==r['final']['state_bank'] and saved['submit']==1,(case,saved,r['final'])
  source_generation=next(gen for gen in e.grids if gen+52360<=int(r['final']['state_bank'],16)<gen+207880)
  diag=r['diagnostics'][hex(source_generation)]
  assert diag['selected_mask']&0x40 and diag['built_mask']&0x40 and diag['bank_slot3']==7 and hex(diag['bank_pointer3'])==r['final']['state_bank']
  if not case.get('switch_at_controller'):
   field,mask=('copy_calls','copy_mask') if case.get('copy',False) else ('upload_calls','upload_mask')
   assert diag[field]>0 and diag[mask]&0x40,(case,diag)
 def off(r):
  assert r['final']['state_bank']=='0x0' and r['final']['state_submit']==0
  assert bytes.fromhex(r['descriptor_hex'])[0]==0 and all(x['enable']==0 for x in r['lanes']),r
  if r['case'].get('root3',0)==1:
   saved=r['saved_snapshot'];assert saved['enable']==0 and saved['bank']=='0x0' and saved['submit']==0,(r['case'],saved)
 for look,root1,gate,copy in itertools.product(('FL2','FL3'),(0,1),(0,1),(False,True)):
  e=Harness(cp,raw,'baseline' if a.baseline421 else 'candidate',symbols);r=e.frame(dict(look=look,root1=root1,gate=gate,copy=copy));rows.append(r)
  if a.baseline421 and root1:assert r['final']['index']==3 and r['final']['state_bank']=='0x0' and r['final']['state_submit']==0
  if look=='FL2' and not root1:assert r['bank_sha256']==sha(model.model(e.grid,e.order,8))
  if not a.baseline421 and root1:
   if look=='FL2':custom(e,r)
   else:off(r)
 if not a.baseline421:
  # Every native scaling class/full aliases and both actual AA transfer modes.
  for level,copy in itertools.product((0,1,2,3,4,5,6,7,8,15,255),(False,True)):
   e=Harness(cp,raw,'candidate',symbols);r=e.frame(dict(look='FL2',level=level,copy=copy));custom(e,r);rows.append(r)
  # Snapshot contexts retain original state and late packet disable gates.
  for look,root3,gate,packet_gate,packet_gate16 in itertools.product(('FL2','FL3'),(0,1),(0,1),(0,1),(0,1)):
   e=Harness(cp,raw,'candidate',symbols);r=e.frame(dict(look=look,root3=root3,gate=gate,packet_gate=packet_gate,packet_gate16=packet_gate16));rows.append(r)
   custom(e,r) if look=='FL2' else off(r)
  # Other mode/domain/direct contexts remain outside the new index3 handoff.
  for root1,domain,direct,root3,special,index in ((0,6,0,0,0,0),(1,8,0,0,0,2),(1,11,0,0,0,1),(1,6,1,0,0,3),(1,6,0,2,0,3),(1,6,0,255,0,3),(1,6,0,0,1,3),(1,7,0,0,0,3)):
   e=Harness(cp,raw,'candidate',symbols);r=e.frame(dict(look='FL2',root1=root1,domain=domain,direct=direct,root3=root3,special=special));rows.append(r);assert r['final']['index']==index
   ptr=int(r['final']['state_bank'],16);assert not(B+52360<=ptr<B+207880),r['case']
  # Keep MMIO and all scratch RAM across look switches: off is enable0, not a claim of table erase.
  for copy in (False,True):
   e=Harness(cp,raw,'candidate',symbols)
   for look in ('FL2','FL3','FL2','FL3','FL2'):
    r=e.frame(dict(look=look,copy=copy,suite='look_switch_preserved_mmio'));custom(e,r) if look=='FL2' else off(r);rows.append(r)
  # A controller-time publication change must not replace the already captured source.
  for copy in (False,True):
   e=Harness(cp,raw,'candidate',symbols);old_grid=e.grid;new_grid=bytes(((-int.from_bytes(old_grid[i:i+1],'little',signed=True))//2)&255 for i in range(1215));new=B+0x40000
   old_packed=bytes(e.u.mem_read(B+52360,155520));e.publish_fixture(new,new_grid);w(e.u,0x1a39448,B)
   r=e.frame(dict(look='FL2',copy=copy,switch_at_controller=new,suite='old_source_new_global'));custom(e,r,old_grid);rows.append(r)
   assert B+52360<=int(r['final']['state_bank'],16)<B+207880
   r=e.frame(dict(look='FL2',copy=copy,suite='next_request_new_generation'));custom(e,r,new_grid);rows.append(r)
   assert new+52360<=int(r['final']['state_bank'],16)<new+207880
   assert bytes(e.u.mem_read(B+52360,155520))==old_packed
  # Clear/missing slot deliberately retains the original native fallback.
  # This is an observed limitation, not a repaired clear-previous-hardware test.
  for copy,mask in itertools.product((False,True),(0,0x80)):
   e=Harness(cp,raw,'candidate',symbols);r=e.frame(dict(look='FL2',copy=copy,suite='native_fallback_before'));custom(e,r);rows.append(r)
   e.publish_fixture(B+0x40000,mask=mask);r=e.frame(dict(look='FL2',copy=copy,suite='expected_native_fallback',mask=mask));rows.append(r)
   baseline=Harness(CP421.read_bytes(),raw,'baseline');baseline.publish_fixture(B+0x40000,mask=mask);native=baseline.frame(dict(look='FL2',copy=copy))
   for key in ('state_enable','state_strength','state_bank','state_submit','state_raw_source','state_kind','state_transform','packet_enable','packet_bank','packet_submit'):assert r['final'][key]==native['final'][key],(key,r['final'],native['final'])
   assert r['descriptor_hex']==native['descriptor_hex']
   r['observed_limitation']=dict(native_fallback_preserved=True,real_cache_outcome_unverified=True,prior_custom_table_may_remain_enabled=not copy and all(x['table_is_custom'] and x['enable'] for x in r['lanes']),explicit_off_required_to_disable_previous_custom=True)
 summary=dict(native_wrapper=True,native_controller=True,native_packet_and_descriptor=True,two_AA_lanes=True,actual_config_writer=True,logical_enable_byte0=True,ordinary_and_copy=True,original_bankguard=True,packed_generation_guard=True,levels_1_through_7_and_full=True,explicit_look_off_preserves_MMIO_and_disables=True,old_source_survives_new_global=True,root3_saved_snapshot_consistent=True,same_generation_upload_copy_diagnostics=True,cross_generation_upload_diagnostics_complete=False,empty_or_missing_generation_native_fallback_preserved=True,empty_or_missing_generation_hardware_clear_verified=False) if not a.baseline421 else dict(index3_gap_reproduced=True,two_AA_lanes=True)
 report=dict(passed=True,suite='native-handoff422/2',cp_path=str(a.cp),cp_sha256=sha(cp),bin_sha256=sha(raw),baseline421=a.baseline421,cases=len(rows),summary=summary,rows=rows,limits=['CPU/MMIO RAM only, no device/SD/ISP pixels.','Native wrapper wiring, ordinary stage6 callback, selector/controller,72869a/72b020,AA two lanes,uploader/config writer execute.','Constructor source fields and unrelated services/stages are explicit fixtures; whole-frame/generation atomicity and physical MMIO are unproved.','Candidate prepare executes on exact compact BIN records; receive task/publication lifecycle is covered by separate production regressions.','Generation test switches STATE after this wrapper captures its source; it proves local source binding, not whole-frame CC1/Gamma/grid atomicity.','Copy path source/target bytes and writer are verified; CPU MMIO tables are not written by the copy path. Enable0 disables a stage but does not prove old table memory is erased.','Clear or omitted slot retains native index3 fallback; native source0x198c1ca/type1/transform0 can enable1 with bank0/submit0. Previous custom hardware table may remain active. This is not fixed or a successful clear-all hardware test.'])
 out=a.output or HERE/'tests'/('baseline421.json' if a.baseline421 else 'handoff422.json');out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(rows),cp_sha256=report['cp_sha256'],output=str(out))))
if __name__=='__main__':main()
