"""Static thread identity proof from final AP instructions, not task runtime."""
from pathlib import Path
import sys,json,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from elf_study import Image
AP=HERE.parent/'ap/appFw.so';a=Image(AP)
assert a.pointer(0x5978c58)==0x3256068
assert int.from_bytes(a.read(a.pointer(0x594a2c0)+0xe4*4,4),'little')==0
assert a.read(0x1e9770c,4).hex()=='62008052' # mov w2,#3
assert a.read(0x31a9d44,4).hex()=='82120011' # add w2,w20,#4
spans=[(0x1e97700,0x20),(0x31a9d10,0x78),(0x3256068,0xc),(0x3255ea0,0x100),(0x3702c20,0x70),(0x3702ae4,0x13c),(0x1ec4d30,0x100),(0x3702a88,0x5c),(0x1ec4cb0,0x18),(0x2462538,0x14),(0x245c448,0x54),(0x2413cc8,0x24),(0x241e7d4,0x20)]
report={'passed':True,'schema':'r5-menu425-native-thread-ownership/1','kind':'static-native-instruction-evidence','AP_sha256':hashlib.sha256(AP.read_bytes()).hexdigest(),'UI':{'create_call':'0x1e97710','entry':'0x1ec4d30','thread_id':3},'E4':{'create_call':'0x31a9d64','entry':'0x3256068 -> 0x3255ea0','thread_id':4,'queue_index':0,'mapping':'GOT594a2c0[0xe4] = 0','execute_virtual_call':'0x3255f9c, command vtable+0x10'},'observations':['Original UI thread creation passes ID3 and1ec4d30 entry to3702c20.','Sequence manager creates IDs4..46 with3256068 entry, separate48B per-ID context and separate16d9fc0 thread create call.','E4 mapping index0 selects ID4;3256068 forwards manager/queue arguments to3255ea0 loop, which releases queue mutex before executing command vtable+0x10.','Thus sleeping the UI ID3 handler does not stop ID4 E4 executor by sharing its thread.','UI loop1ec4cb4 releases its own self+18 mutex before1ec4cc4 engine virtual call. Engine2462538 ->245c448 has no direct model-lock acquire; its initial2413cc8 helper has local stack guard, explicit2e7cee4 unlock at241e7dc before returning. This excludes these specific outer locks, not all transitive page dispatch paths.'],'spans':[{'va':hex(v),'bytes':n,'sha256':hashlib.sha256(a.read(v,n)).hexdigest(),'disassembly':a.dis(v,n)}for v,n in spans],'limits':['Static final AP analysis only; no native concurrent scheduler execution or physical device.','Native OSAL thread creation function behavior inferred from distinct ID-indexed contexts and thread creation call; device task dump not acquired.','UI must still avoid holding a model lock while waiting; page wrapper caller lock placement requires separate UI native replay.']}
(HERE/'thread_ownership425_verified.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':True,'AP_sha256':report['AP_sha256'],'UI_thread_id':3,'E4_thread_id':4}))
