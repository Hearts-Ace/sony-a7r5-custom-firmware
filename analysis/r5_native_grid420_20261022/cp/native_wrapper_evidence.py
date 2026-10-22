"""Bounded original disassembly plus actual BW/SE native branch replay."""
from pathlib import Path
import sys,json,hashlib,struct
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from capstone import *
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
from verify_r5_m4strict_cp_cpu import new_cpu,SCRATCH,SP
p=ROOT/'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin';b=p.read_bytes();md=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
ranges=[]
for lo,hi in [(0x24119a,0x2411e0),(0x2429a6,0x2429f0),(0x71d68a,0x71d6fc),(0x71eccc,0x71ecf2)]:
 ranges.append(dict(start=hex(lo),end=hex(hi),instructions=[dict(address=hex(i.address),bytes=i.bytes.hex(),mnemonic=i.mnemonic,operands=i.op_str)for i in md.disasm(b[lo-0x108000:hi-0x108000],lo)]))
rows=[]
for image in (p,):
 raw=image.read_bytes();u=new_cpu(raw);wrap=SCRATCH+0x100;context=SCRATCH+0x1000;u.mem_write(wrap,struct.pack('<2I',0,context));u.mem_write(context+0x25,b'\x35');u.reg_write(UC_ARM_REG_R6,wrap);u.reg_write(UC_ARM_REG_R5,7);u.reg_write(UC_ARM_REG_SP,SP);hits=[]
 def hook(c,a,n,z):
  if a in (0x71d6f8,0x71e41e,0x71eccc):hits.append(hex(a))
 u.hook_add(UC_HOOK_CODE,hook);u.emu_start(0x71d68b,0x71d816,count=300)
 assert u.reg_read(UC_ARM_REG_PC)==0x71d816 and hits==['0x71eccc']
 out=bytes(u.mem_read(SP+0x248,18));constant=bytes(u.mem_read(0xcb2668,18));assert out==constant
 rows.append(dict(image=str(image.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest(),profile53_BW_SE=True,hits=hits,output_matches_native_constant=True,native_constant=constant.hex(),custom_matrix_BL_bypassed=True))
q=dict(passed=True,camera_io=False,source_sha256=hashlib.sha256(b).hexdigest(),ranges=ranges,profile53_branch_replays=rows,conclusions=['Ordinary state+0x2e stores model+0xa40 native wire, not selector internal base.','Matrix caller reads profile at wrapper[1]+0x25.','Native BW/SE profile53 bypasses71d6f8 custom matrix and copies native9coefficient constant.'],limits=['Full BW/SE color ISP and downstream tint processing not executed. Retained native BW/SE selectors and flags cannot be described as arbitrary full-color custom looks.'])
(OUT/'native_wrapper_evidence.json').write_text(json.dumps(q,indent=2)+'\n');print(json.dumps({k:v for k,v in q.items()if k!='ranges'}))
