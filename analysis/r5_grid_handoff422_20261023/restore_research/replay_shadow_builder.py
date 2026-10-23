"""Native builder shadow-route study only; does not edit firmware bytes.

Compares original index0 vs private direct destination, root3 logging state,
type0/1/2 and transform0/1/2, including nonlinear transform1. Tracks actual
source reads/writes and bounded root/environment dependencies.
"""
from pathlib import Path
import sys,json,itertools,struct,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path[:0]=[str(HERE.parent),str(ROOT/'vendor/audit-python')]
from replay_handoff422 import *
PRISTINE=ROOT/'analysis/r5_native_grid419_20261022/cp/cp420-grid.NONINSTALLABLE.bin'

def main():
 cp=CP421.read_bytes();rows=[];comparisons=[];full_aliases=[]
 raw1=bytes((i*37%128)-64 & 255 for i in range(1215));raw2=bytes((i*29%128)-64 & 255 for i in range(162))
 def run(kind,transform,level,root3,direct,index,zero_source=False):
  e=Harness(cp,(ROOT/'exports/fl2_fl3_grid_compare_20261023/R5NATIVE.BIN').read_bytes(),'shadow-study');u=e.u
  # Use fresh standalone valid objects: independent of controller and wrapper.
  ctx=A+0x1000;root=A+0x2000;env=A+0x3000;out=A+0x4000;state=A+0x5000;work=A+0x6000;meta=A+0x8000;src=A+0x9000;bank=A+0xa000
  w(u,ctx,root,env);w(u,out+8,state,work,meta);w(u,work+0x6b0,bank)
  u.mem_write(root+3,bytes([root3]));u.mem_write(root+0x2f,bytes([level]));u.mem_write(env+6,bytes([direct]));u.mem_write(meta+11,bytes([index]));w(u,state+0x184,0 if zero_source else src);u.mem_write(state+0x188,bytes([kind,transform]))
  source=raw1 if kind==1 else raw2 if kind==2 else bytes(1215)
  u.mem_write(src,source)
  target=work+0x5c if direct else bank+1620*index
  u.mem_write(target-16,b'\xa5'*16);u.mem_write(target+1620,b'\x5a'*16)
  accesses=[]
  def access(c,acc,at,size,value,_):
   if root<=at<root+0x1000:region='root'
   elif env<=at<env+0x1000:region='env'
   elif src<=at<src+0x1000:region='source'
   elif state<=at<state+0x1000:region='state'
   else:return
   accesses.append(dict(access='write' if acc==UC_MEM_WRITE else 'read',region=region,offset=at-{'root':root,'env':env,'source':src,'state':state}[region],size=size))
  u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,access)
  # Execute original builder trampoline, bypass only existing observation layer.
  # Pristine displaced first4 bytes PUSH{r4-r7,lr};ADD r7,sp,#12 are supplied
  # by a small synthetic trampoline then native body231658 executes unchanged.
  trampoline=A+0x70000;u.mem_write(trampoline,bytes.fromhex('f0b503af')+bytes.fromhex('dff800f0')+struct.pack('<I',0x231659))
  e.call(trampoline,ctx,out)
  got=bytes(u.mem_read(target,1620));assert bytes(u.mem_read(src,len(source)))==source
  assert bytes(u.mem_read(target-16,16))==b'\xa5'*16 and bytes(u.mem_read(target+1620,16))==b'\x5a'*16
  reads=[a['offset'] for a in accesses if a['access']=='read' and a['region']=='source'];writes=[a for a in accesses if a['access']=='write' and a['region']=='source'];assert not writes
  row=dict(kind=kind,transform=transform,level=level,root3=root3,direct=direct,index=index,zero_source=zero_source,packed_sha256=sha(got),source_read_min=min(reads) if reads else None,source_read_max=max(reads) if reads else None,root_read_offsets=sorted({a['offset'] for a in accesses if a['access']=='read' and a['region']=='root'}),env_read_offsets=sorted({a['offset'] for a in accesses if a['access']=='read' and a['region']=='env'}),source_unchanged=True,guards=True)
  rows.append(row);return got
 for kind,transform,level in itertools.product((0,1,2),(0,1,2),(0,1,4,7,8,15,255)):
  base=run(kind,transform,level,0,0,0)
  for root3,direct,index in ((1,0,0),(0,1,3),(1,1,3)):
   got=run(kind,transform,level,root3,direct,index);assert got==base,(kind,transform,level,root3,direct)
  comparisons.append(dict(kind=kind,transform=transform,level=level,root3_and_destination_equivalent=True))
 for kind,transform in itertools.product((0,1,2),(0,1,2)):
  hashes={x['level']:x['packed_sha256']for x in rows if x['kind']==kind and x['transform']==transform and x['root3']==0 and x['direct']==0}
  assert len({hashes[k]for k in (0,8,15,255)})==1,(kind,transform,hashes)
  full_aliases.append(dict(kind=kind,transform=transform,levels_0_8_15_255_identical=True))
 # A kind1 null source with transform1 must still run nonlinear native math;
 # it cannot be equated to no effect merely because the pointer is null.
 for transform,level in itertools.product((0,1,2),(1,8)):
  got=run(1,transform,level,0,1,3,True)
  comparisons.append(dict(kind=1,transform=transform,level=level,null_source=True,packed_zero=not any(got)))
 report=dict(passed=True,cp_sha256=sha(cp),native_body_start='0x231658',cases=len(rows),comparisons=comparisons,full_aliases=full_aliases,rows=rows,limits=['Pure CPU fixture and offline original builder; no device/SD/ISP pixels.','root36 fixed0; special root36=1 rejected by proposed restore scope.','Nonlinear transform1 output is compared native-vs-native rather than to a separately derived mathematical implementation.','Does not establish actual RAM table bytes or initialization/lifetime.'])
 out=HERE/'shadow_builder_replay.json';out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(rows),output=str(out))))
if __name__=='__main__':main()
