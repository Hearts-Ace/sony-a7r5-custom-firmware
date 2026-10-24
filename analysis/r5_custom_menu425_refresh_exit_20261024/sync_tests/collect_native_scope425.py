"""Static source-bound native boundary evidence; no execution claim."""
from pathlib import Path
import sys,hashlib,json
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from elf_study import Image
from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
p=ROOT/'analysis/r5_custom_menu424_20261023/ap/appFw.so'
a=Image(p);md=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
spans=[(0x24b0780,0x2c),(0x32885b4,0x60),(0x348292c,0x160),(0x350927c,0x40),(0x35614b4,0x90),(0x35589a4,0xb8)]
rows=[]
for va,n in spans:
 b=a.read(va,n);rows.append({'va':hex(va),'bytes':n,'sha256':hashlib.sha256(b).hexdigest(),'instructions':[f'{i.address:x}: {i.mnemonic} {i.op_str}' for i in md.disasm(b,va)]})
r={'schema':'r5-menu425-native-submit-scope/1','kind':'static-capstone-source-bound','AP_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'spans':rows,'observations':['0x24b0780 sends original E4 request through manager/factory. Constructor at0x32885e8 precedes enqueue.','E4 execute0x348292c sends nine native color messages and returns at0x3482a88.','3561518/356151c set x5/x4 to zero before355882c; no reply buffer requested.35589f8 skips352bdb0 wait branch when x4 zero.','Thus E4 return proves original submission-body return only. A later matching CP SELECT ACK is an additional control-plane witness, not physical LCD/JPEG or native per-message success.'],'limits':['No runtime/native scheduler/physical display execution.','Same queue/FIFO requires corroboration beyond static send endpoint identity.']}
out=Path(__file__).with_name('native_submit_scope425.json');out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(out)
