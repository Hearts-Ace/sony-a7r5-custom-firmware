"""Bounded audit of a file-backed padding code span; no devices or DAT.

The containing data page remains writable to preserve its native112-byte prefix.
The optional native map clears only XN. No L1/L2/BSS/stack is relocated.
"""
from pathlib import Path
import argparse,hashlib,json,struct,sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(Path(__file__).parent)]
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_ARM
PIN=ROOT/'research/r5_custom_lut/evidence/sd405_native_transport_v1/cp405-transfer-gate.NONINSTALLABLE.bin'
STOCK=ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin'
BASE=0x108000;PAGE=0x1195000;START=0x1195080;END=0x1196000
PIN_SHA='41bffc6bd0121eb9948f916c0496c35a6d355d5bebc928f639e32c5d8568f954'
def digest(b):return hashlib.sha256(b).hexdigest()
def audit(out=None):
 b=PIN.read_bytes();stock=STOCK.read_bytes();assert digest(b)==PIN_SHA
 assert digest(stock)=='8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32'
 for data in (b,stock):assert data[0x1195070-BASE:END-BASE]==bytes(3984)
 assert b[PAGE-BASE:START-BASE]==stock[PAGE-BASE:START-BASE]
 refs=[];md=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
 for off in range(0,len(b)-4,2):
  at=BASE+off
  if START<=at<END:continue
  v=struct.unpack_from('<I',b,off)[0]
  if START<=v&~1<END:refs.append(dict(kind='halfword_u32',site=hex(at),value=hex(v)))
  h=struct.unpack_from('<H',b,off)[0]
  if h&0xf800==0xf000:
   ins=list(md.disasm(b[off:off+4],at))
   if len(ins)==1 and ins[0].mnemonic in ('bl','b.w') and ins[0].op_str.startswith('#0x'):
    v=int(ins[0].op_str[1:],16)
    if START<=v<END:refs.append(dict(kind=ins[0].mnemonic,site=hex(at),value=hex(v)))
 # Halfword-linear scan also decodes the second half of native Thumb-2
 # instructions. These two exact overlapping decodes are independently
 # rejected by their enclosing native instruction, not ignored as callers.
 exclusions={0xac3fa8:(0xac3fa6,'84f5d1f2','bl','#0x44854c'),
             0xb0900e:(0xb0900c,'5ffa8cf2','uxtb.w','r2, ip')}
 false=[];actual=[]
 for ref in refs:
  site=int(ref['site'],16)
  if site not in exclusions:actual.append(ref);continue
  start,raw,mn,op=exclusions[site]
  assert b[start-BASE:start-BASE+4].hex()==raw
  ins=list(md.disasm(bytes.fromhex(raw),start));assert len(ins)==1 and ins[0].mnemonic==mn and ins[0].op_str==op
  false.append(dict(overlap=ref,parent_instruction=hex(start),bytes=raw,mnemonic=mn,operands=op))
 assert not actual,actual
 # Native loader mapping is replayed by build_cp_render_page in the separate
 # proof. Source header already includes the full page in its native data map.
 _,length,va=struct.unpack_from('<III',b,0x2013c)
 assert (va,length)==(0x107f000,0x118000) and va+length==0x1197000
 result=dict(schema='r5-file-padding-code-audit/1',passed=True,camera_io=False,installable=False,
  input_sha256=PIN_SHA,stock_sha256=digest(stock),start=hex(START),end_exclusive=hex(END),bytes=END-START,
  zero_span_in_stock_and_current=True,native_prefix_bytes=128,native_prefix_sha256=digest(b[PAGE-BASE:START-BASE]),
  native_data_map_already_file_backed=True,native_data_end='0x1197000',external_references=actual,excluded_midinstruction_decodes=false,
  requested_map=dict(VA=hex(PAGE),PA=hex(PAGE),bytes=4096,old_flags=12,new_flags=14,
   intended_PTE_change='0x119541f ->0x119541e; only XN cleared, native RW/cache/physical bits preserved',
   writable_executable=True),
  limitations=['Bounded direct Thumb BL/B.W and halfword-u32 scan; computed references and all possible native writes are not excluded.',
   'Code occupies native file padding beyond declared initialized data; original128-byte page prefix must remain byte-exact and writable.',
   'This static audit alone does not authorize installation; native loader/PTE/clear/copy and full reverse proof are required.'])
 if out:
  out=Path(out);out.mkdir(parents=True,exist_ok=False)
  (out/'audit.json').write_text(json.dumps(result,indent=2)+'\n');(out/'executed.py').write_bytes(Path(__file__).read_bytes())
  (out/'manifest.json').write_text(json.dumps(dict(files={p.name:digest(p.read_bytes())for p in out.iterdir()if p.is_file()}),indent=2)+'\n')
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path);a=p.parse_args();print(json.dumps(audit(a.output)))
