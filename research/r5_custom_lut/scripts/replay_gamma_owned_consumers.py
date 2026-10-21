"""Offline execution of reconstructed native Gamma against source instructions."""
from pathlib import Path
import argparse,hashlib,json,struct,sys,itertools
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools'),str(Path(__file__).parent)]
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_READ
from unicorn.arm_const import *
from verify_r5_m4strict_cp_cpu import new_cpu,SCRATCH,SP,STOP,w32
from build_color_consumers import branch
CP=ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin';BASE=0x108000;RX=0x1a3c000

def link(objects,base=RX):
 data=bytearray();symbols={};locals=[];pending=[]
 for obj in objects:
  with obj.open('rb') as f:
   e=ELFFile(f);sections={};sy=e.get_section_by_name('.symtab');local={}
   for ix,s in enumerate(e.iter_sections()):
    if s['sh_flags']&4 and s['sh_size']:
     while len(data)%4:data.append(0)
     sections[ix]=len(data);data+=s.data()
   for ix,s in enumerate(sy.iter_symbols()):
    if s['st_shndx'] in sections:
     value=base+sections[s['st_shndx']]+s['st_value'];local[ix]=value
     if s['st_info']['bind']=='STB_GLOBAL':
      assert s.name not in symbols;symname=s.name;symbols[symname]=value
   for section in e.iter_sections():
    if section['sh_type']!='SHT_REL' or section['sh_info'] not in sections:continue
    for r in section.iter_relocations():
     s=sy.get_symbol(r['r_info_sym']);pending.append((len(locals),r['r_info_sym'],s.name,r['r_info_type'],sections[section['sh_info']]+r['r_offset']))
   locals.append(local)
 for oi,si,name,kind,off in pending:
  target=locals[oi].get(si,symbols.get(name));assert target and kind in(10,30),(name,kind)
  assert data[off:off+4] in (bytes.fromhex('fff7feff'),bytes.fromhex('fff7febf'))
  data[off:off+4]=branch(base+off,target&~1,kind==10)
 return bytes(data),symbols

def main(out,obj,build=None,cp_image=None,native_callers=False):
 assert obj or build,'Standalone replay requires --object; integrated recipe uses --build'
 out.mkdir(parents=True,exist_ok=False);cp=CP.read_bytes();object_meta=json.loads((obj.parent/'build.json').read_text())if obj and (obj.parent/'build.json').exists() else {};object_base=int(object_meta.get('RX',hex(RX)),16);data,symbols=link([obj],base=object_base)if not build else (b'',{});binding=None;shared=None
 split=object_meta.get('fifth_argument_bytes')==516
 if build:
  from color_replay_image import image
  meta,candidate,page,binding=image(build,cp_image);symbols={k:int(v,16)for k,v in meta['symbols'].items()};u=new_cpu(candidate);u.mem_write(0x1a3b000,page);shared=meta.get('gamma_shared')
 else:
  shared=object_meta if object_meta.get('schema')=='r5-shared-gamma-experiment/1' else None
  u=new_cpu((obj.parent/'candidate.bin').read_bytes() if shared else cp);u.mem_write(object_base,data)
 split=split or bool(shared)
 shared_patches=shared['patches'] if shared else []
 trusted_return=int(shared.get('trusted_return_pc',shared.get('trusted_saved_wrapper_LR','0')),16)if shared else STOP|1
 AUX=SCRATCH+0x1000;WRAP=SCRATCH+0x3000;DST=SCRATCH+0x4000;OWN=SCRATCH+0x5000
 state={'logs':0,'native_math_calls':0,'tracking_owned':False};reads={};read_calls=[]
 def record_read(c,address,size):
  if state['tracking_owned'] and address<OWN+576 and address+size>OWN:
   lo=max(address,OWN)-OWN;hi=min(address+size,OWN+576)-OWN
   if split:assert address>=OWN and address+size<=OWN+516,('custom ordinates overread',hex(c.reg_read(UC_ARM_REG_PC)),lo,hi)
   pc=c.reg_read(UC_ARM_REG_PC);key=hex(pc)
   prior=reads.setdefault(key,dict(start=lo,end_exclusive=hi,count=0))
   prior['start']=min(prior['start'],lo);prior['end_exclusive']=max(prior['end_exclusive'],hi);prior['count']+=1
   read_calls.append((lo,hi))
 def memory_read(c,access,address,size,value,_):record_read(c,address,size)
 u.hook_add(UC_HOOK_MEM_READ,memory_read,begin=OWN,end=OWN+575)
 def hook(c,at,size,_):
  if state['tracking_owned'] and at==(trusted_return&~1):c.reg_write(UC_ARM_REG_PC,STOP);c.emu_stop();return
  if at==0x6069b0:state['native_math_calls']+=1
  if at==0xb0de92:state['logs']+=1;c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
  elif at==0x5f51bc:
   record_read(c,c.reg_read(UC_ARM_REG_R1),c.reg_read(UC_ARM_REG_R2))
   c.mem_write(c.reg_read(UC_ARM_REG_R0),bytes(c.mem_read(c.reg_read(UC_ARM_REG_R1),c.reg_read(UC_ARM_REG_R2))));c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
  elif at==0x5f58b0:
   c.mem_write(c.reg_read(UC_ARM_REG_R0),bytes(c.reg_read(UC_ARM_REG_R1)));c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def call(entry,args,owned,ordinary_detoured=False):
  for p in shared_patches:
   replacement=p.get('replacement',p.get('patched'))
   u.mem_write(int(p['site'],16),bytes.fromhex(p['original'] if entry in (0x41363c,0x413df0) and not ordinary_detoured else replacement))
  if shared_patches:u.ctl_remove_cache(0x41363c,0x414120)
  state['tracking_owned']=entry not in (0x41363c,0x413df0)
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
  w32(u,SP,owned);w32(u,SP+4,state['native_record']);u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,trusted_return if state['tracking_owned'] else STOP|1)
  saved=[0x55550000+i for i in range(8)]
  for r,v in zip(range(UC_ARM_REG_R4,UC_ARM_REG_R11+1),saved):u.reg_write(r,v)
  u.emu_start(entry|1,STOP,count=100000)
  assert u.reg_read(UC_ARM_REG_PC)==STOP,hex(u.reg_read(UC_ARM_REG_PC));assert u.reg_read(UC_ARM_REG_SP)==SP
  assert [u.reg_read(r)for r in range(UC_ARM_REG_R4,UC_ARM_REG_R11+1)]==saved
 def prepare(id,part,contrast,brightness,domain,custom,transform=1):
  original=struct.unpack_from('<I',cp,0x107e968-BASE+(id*7+part)*4)[0]
  native=cp[original-BASE:original-BASE+576];assert original and len(native)==576
  state['native_record']=original
  owned=(struct.pack('<129I',*[i*(800+id)for i in range(129)])+native[516:]) if custom else native
  u.mem_write(OWN,owned[:516]+b'\xa5'*60 if split else owned);u.mem_write(AUX,bytes(0x1000));u.mem_write(DST,bytes(0x100));u.mem_write(WRAP,bytes(0x80))
  w32(u,WRAP+0x30,id);u.mem_write(WRAP+0x38,bytes([part]));u.mem_write(WRAP+0x39,bytes([contrast]));u.mem_write(WRAP+0x3a,bytes([brightness]));u.mem_write(WRAP+0x4d,bytes([transform]))
  u.mem_write(0x19d1309,bytes(32));u.mem_write(0x18d1c24,bytes(0x240));u.mem_write(0x19d131c,bytes([1 if domain==0 else 2]))
  return owned
 checks=0;tailchecks=0
 entries=[(0x41363c,'r5_gamma_native_curve_owned',[0,WRAP,AUX]),
          (0x413df0,'r5_gamma_native_wrapper_owned',[0,WRAP,AUX,DST])]
 # Production has no standalone direct-curve API. Its actual wrapper still
 # executes that complete original curve body. Keep ordinary native direct
 # callers in the separate poisoned-extra-argument negative replay.
 entries=[row for row in entries if native_callers or row[1] in symbols]
 assert entries and any(row[1]=='r5_gamma_native_wrapper_owned'for row in entries)
 # All table-valid IDs and seven native partitions; two native domains and
 # representative native signed-byte contrast/brightness controls.
 for id,part,domain,adjust,transform in itertools.product(range(51),range(7),(0,1),((0,0),(2,3),(254,253)),(0,1)):
  ptr=struct.unpack_from('<I',cp,0x107e968-BASE+(id*7+part)*4)[0]
  if not ptr:continue
  for entry,name,template in entries:
   args=[domain]+template[1:]
   prepare(id,part,*adjust,domain,False,transform);call(entry,args,OWN);reference=(bytes(u.mem_read(AUX,0x500)),bytes(u.mem_read(DST,0x80)))
   prepare(id,part,*adjust,domain,False,transform);call(entry if native_callers else symbols[name],args,0xdeadbeef if native_callers else OWN,ordinary_detoured=native_callers);actual=(bytes(u.mem_read(AUX,0x500)),bytes(u.mem_read(DST,0x80)))
   assert reference==actual,(hex(entry),id,part,domain,adjust);checks+=1
 # Distinct ordinates; native metadata is independently retained. The custom
 # input is destroyed after synchronous return; output pointers target AUX.
 for seed in range(0 if native_callers else 12):
  for entry,name,template in entries:
   args=[1]+template[1:]
   prepare(0,6,0,0,1,False);call(entry,args,OWN);native_aux=bytes(u.mem_read(AUX,0x500));native_dst=bytes(u.mem_read(DST,0x80))
   owned=prepare(0,6,0,0,1,True);owned=struct.pack('<129I',*[i*(800+seed)for i in range(129)])+owned[516:];u.mem_write(OWN,owned[:516]+b'\xa5'*60 if split else owned);call(symbols[name],args,OWN)
   assert bytes(u.mem_read(AUX+0x24c,516))==owned[:516]
   if entry==0x413df0:
    assert struct.unpack('<2I',u.mem_read(AUX+8,8))==(AUX+0x24c,AUX+0x21c)
   assert bytes(u.mem_read(DST,0x80))==native_dst
   for start,n in [(0x450,8),(0x458,2),(0x45c,8)]:
    assert bytes(u.mem_read(AUX+start,n))==native_aux[start:start+n]
   u.mem_write(OWN,b'\xa5'*576)
   assert bytes(u.mem_read(AUX+0x24c,516))==owned[:516];tailchecks+=1
 result=dict(schema='r5-gamma-owned-native-replay/2',passed=True,binding=binding,shared_native_detours=bool(shared),dynamic_unpatched_native_metadata_reference=True,ordinary_native_callers_with_poisoned_fifth_arg=native_callers,camera_io=False,installable=False,split_custom_ordinates_native_metadata=split,original_sha256=hashlib.sha256(cp).hexdigest(),object_sha256=hashlib.sha256(obj.read_bytes()).hexdigest()if obj else None,RX_bytes=meta['RX_bytes'] if build else len(data),native_equal_cases=checks,custom_curve_lifetime_cases=tailchecks,native_math_helper_6069b0_calls=state['native_math_calls'],callee_saved_stack_preserved=True,logs=state['logs'],fifth_argument_reads=dict(min_offset=min((a for a,b in read_calls),default=None),max_end_exclusive=max((b for a,b in read_calls),default=None),reads_beyond_516=sum(b>516 for a,b in read_calls),sites=reads),boundaries=['Synthetic contexts; libc memcpy/memset and logger modeled, including explicit read-range tracing for modeled memcpy.','No device, asynchronous owner or final JPEG/preview hardware exercised.'])
 result['entrypoints_tested']=[row[1]for row in entries]
 result['production_wrapper_all_native_table_controls']=not native_callers
 (out/'linked.bin').write_bytes(data);(out/'replay.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--object',type=Path);p.add_argument('--build',type=Path);p.add_argument('--cp-image',type=Path);p.add_argument('--native-callers',action='store_true');a=p.parse_args();main(a.output,a.object,a.build,a.cp_image,a.native_callers)
