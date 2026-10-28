"""Original AP wheel dispatcher/handlers; bounded offline A64 execution.

Stops at native color mutation/queue boundaries; never calls camera services.
An unmapped message pointer proves 2050/1 do not consume a step payload before
passing their fixed +1/-1 movement to 2207480. This is not physical dial capture.
"""
from pathlib import Path
import hashlib,io,json,struct,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(HERE.parent/'menu_research')]
from read_menu import Image
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn import arm64_const as R

im=Image(ROOT/'assets/firmware/a8d5cd444bf0-appFw.so')
sha=hashlib.sha256(im.data).hexdigest()
assert sha=='a8d5cd444bf08a03a70aedc3cc32bdd857b89b468ac10bf8365d640e8d390d75'
member=im.pointer(0x598a540);indices=im.pointer(0x594eb70)
expected=[0x22083b4,0x22083d0,0x2207dd4,0x2207e98,0x1a62ebc,0x1a62e8c]
table=[]
for sub,target in enumerate(expected):
 idx=struct.unpack('<h',im.read(indices+2*sub,2))[0]
 code,adjust=im.pointer(member+16*idx),im.pointer(member+16*idx+8)
 assert code==target and adjust==0 and idx==16+sub
 table.append(dict(event=hex(0x2050000|sub),index=idx,handler=hex(code),adjust=adjust))
raw=[]
for prefix,families,subs,count in [(0x1000000,0x3dc8778,0x3dca2a8,890),(0x4000000,0x3dc9560,0x3dcb090,850)]:
 matches=[]
 for i in range(count):
  family=struct.unpack('<I',im.read(families+4*i,4))[0]
  sub=struct.unpack('<I',im.read(subs+4*i,4))[0]
  if family==0x2050000:matches.append(dict(raw=hex(prefix|i),canonical=hex(family|sub)))
 raw.append(dict(prefix=hex(prefix),family_table=hex(families),sub_table=hex(subs),entries=count,wheel_matches=matches))

rows=[]
for bias in (0,0x40000000):
 u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
 for s in ELFFile(io.BytesIO(im.data)).iter_segments():
  if s['p_type']!='PT_LOAD':continue
  lo=(s['p_vaddr']+bias)&-4096;hi=(s['p_vaddr']+s['p_memsz']+bias+4095)&-4096
  u.mem_map(lo,hi-lo)
  if s['p_filesz']:u.mem_write(s['p_vaddr']+bias,s.data())
 for at,(info,addend) in im.relocs.items():
  if info==1027:u.mem_write(at+bias,struct.pack('<Q',addend+bias))
 mem=0x30000000;u.mem_map(mem,0x200000);controller=mem;stop=mem+0x1ff000
 u.mem_write(controller+0x178,struct.pack('<I',0xd9))
 pending={};trace=[];seen=[]
 def hook(cpu,pc,size,arg):
  at=pc-bias
  if pc==stop:cpu.emu_stop();return
  trace.append(at)
  if at in expected:seen.append(at)
  if at in pending['stop_at']:
   pending['result']=dict(at=hex(at),x0=hex(cpu.reg_read(R.UC_ARM64_REG_X0)),
      w1=cpu.reg_read(R.UC_ARM64_REG_X1)&0xffffffff,
      w2=cpu.reg_read(R.UC_ARM64_REG_X2)&0xffffffff,
      w3=cpu.reg_read(R.UC_ARM64_REG_X3)&0xffffffff)
   cpu.emu_stop()
 u.hook_add(UC_HOOK_CODE,hook)
 def call(event,message,stop_at):
  pending.clear();pending['stop_at']=set(stop_at);trace.clear();seen.clear()
  for n,v in enumerate([controller,message,event]):u.reg_write(getattr(R,'UC_ARM64_REG_X'+str(n)),v)
  u.reg_write(R.UC_ARM64_REG_SP,mem+0x1f0000);u.reg_write(R.UC_ARM64_REG_LR,stop)
  u.emu_start(0x1a6d8cc+bias,stop,count=10000)
  assert 'result' in pending
  return dict(pending['result'])
 for sub in range(6):
  event=0x2050000|sub
  result=call(event,0xdeadbee000,{expected[sub]})
  assert result['at']==hex(expected[sub])
  rows.append(dict(bias=hex(bias),kind='dispatch',event=hex(event),message='unmapped',result=result))
 for sub in (0,1):
  for msg in (0,mem+0x1000,0xdeadbee000):
   result=call(0x2050000|sub,msg,{0x2207480})
   assert result['x0']==hex(controller)
   assert result['w1']==(1 if sub==0 else 0xffffffff)
   assert seen==[expected[sub]] and 0x2207fe0 in trace
   rows.append(dict(bias=hex(bias),kind='fixed_step',event=hex(0x2050000|sub),message=hex(msg),
      signed_step=1 if sub==0 else -1,result=result,handler_message_not_dereferenced=True))
 for sub in (4,5):
  for msg in (0,mem+0x1000,0xdeadbee000):
   result=call(0x2050000|sub,msg,{0x1b2bffc})
   assert result['x0']==hex(msg) and result['w1']==0x2050000+(sub==5)
   assert result['w2']==2 and result['w3']==0xd9
   rows.append(dict(bias=hex(bias),kind='repost',event=hex(0x2050000|sub),message=hex(msg),result=result))

windows=[(0x1a6d8cc,0x134),(0x1a6dd28,0x14),(0x1a6df44,0x10),
 (0x1b2932c,0x88),(0x22083b4,0x38),(0x2207fe0,0xf0),
 (0x2207480,0x40),(0x2207dd4,0x18c),(0x1a62e8c,0x5c)]
(HERE/'native_wheel_disassembly.txt').write_text('\n\n'.join(im.dis(a,n)for a,n in windows)+'\n')
report=dict(passed=True,original_sha256=sha,dispatcher='0x1a6d8cc',family_table=hex(indices),member_table=hex(member),
 native_contract=table,normalization_tables=raw,cases=rows,cases_count=len(rows),
 message_count_semantics=dict(canonical_2050_2051='one fixed signed step per dispatched event',
  message_step_count_read=False,message_direction_read=False,
  canonical_2054_2055='forward original message pointer unchanged; repost one 2050/2051 event',
  physical_detents_or_acceleration_observed=False),
 recommended_private_mapping={'0x2050000':'next available (+1)','0x2050001':'previous available (-1)',
  '0x2050004':'next available (+1), consume without native repost','0x2050005':'previous available (-1), consume without native repost',
  '0x2050002':'consume: stock parameter/change-mode branch, right controls removed',
  '0x2050003':'consume: stock parameter/change-mode branch, right controls removed'},
 limitations=['Original A64 dispatcher executes with relocated ELF for two PIE bases. Mutation 2207480 and queue 1b2bffc are observation stops, not simulated implementations.',
  'Canonical 2050/1 consume one fixed step per event; no measured physical dial detent rate, acceleration, hardware direction or dropped-event behavior.',
  '2054/5 forward message unchanged while reposting canonical 2050/1; private page should handle once and consume rather than allowing duplicate native repost.',
  '01/04 raw alias scan covers 890/850 entries bounded by adjacent constant tables, with no 205-family alias. Canonical events remain valid.',
  '2052/3 native branches access parameter state and actions. They are excluded from private list movement; this replay stops on entry without claiming full action execution.',
  'No current candidate dispatch or worker execution here; final compiled 4.32 behavior must have separate receipt. No camera I/O.'])
(HERE/'native_wheel432.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(passed=True,cases=len(rows),original_sha256=sha)))
