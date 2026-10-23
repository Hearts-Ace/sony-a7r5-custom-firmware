"""Build exact404 native Gamma reference patches; no CP/DAT/device mutation."""
from pathlib import Path
import hashlib,struct,sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from build_r5_m4strict_gamma import mov16,TABLE_REFS,ROUTE_REFS,BOUNDS
SHA='8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32'
BASES=[0,3,2,1,16,15,19,20,17,18,5,13]
CONTEXT_BYTES=23484
def initial_context(cp,context_va):
 """Safe initialized RW segment payload, before any AP probe/CP task runs.

 Original51 Gamma rows and original22 route rows remain byte-identical;
 appended rows/records are dormant until selected mask is sealed.
 """
 assert hashlib.sha256(cp).hexdigest()==SHA
 assert context_va%4==0 and 0<context_va<2**32-CONTEXT_BYTES
 d=bytearray(CONTEXT_BYTES);d[:1428]=cp[0x107e968-0x108000:0x107e968-0x108000+1428]
 d[23020:23484]=cp[0xdcc514-0x108000:0xdcc514-0x108000+464]
 d[2100:2276]=cp[0x107eefc-0x108000:0x107eefc-0x108000+176]
 for i,b in enumerate(BASES):
  a,v=struct.unpack_from('<2I',d,2100+b*8)
  for k,(id,p)in enumerate([(a,0),(a,6),(v,6)]):
   native=struct.unpack_from('<I',d,(id*7+p)*4)[0]
   assert native;at=2276+(i*3+k)*576;d[at:at+576]=cp[native-0x108000:native-0x108000+576]
  addr=context_va+2276+i*3*576;id=51+i*2
  struct.pack_into('<7I',d,id*28,*([addr]*6+[addr+576]))
  struct.pack_into('<7I',d,(id+1)*28,*([0]*6+[addr+1152]))
 return bytes(d)
def patches(cp,context_va):
 assert hashlib.sha256(cp).hexdigest()==SHA
 assert context_va%4==0 and 0<context_va<2**32-23020
 rows=[]
 for refs,old,new,label in [(TABLE_REFS,0x107e968,context_va,'native 75-ID table'),(ROUTE_REFS,0x107eefc,context_va+75*28,'native 22-base route')]:
  for lo,hi,r in refs:
   for at,top in [(lo,False),(hi,True)]:
    before=mov16(r,(old>>16)if top else old&65535,top);after=mov16(r,(new>>16)if top else new&65535,top)
    assert cp[at:at+4]==before
    rows.append(dict(offset=at,before=before.hex(),after=after.hex(),reason=label))
 for at in BOUNDS:
  assert cp[at:at+2]==bytes.fromhex('3328')
  rows.append(dict(offset=at,before='3328',after='4b28',reason='native signed ID bound now75, existing ID semantics retained'))
 return rows
