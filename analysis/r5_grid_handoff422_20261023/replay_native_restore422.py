"""Bounded native type1 transform0/2 builder comparison, no devices.

The native source pointer 0x198c1ca lies in runtime RAM beyond the CP image.
Its actual camera contents are unknown. Nonzero data here is an explicit
fixture proving format equivalence only; it is not a captured factory table.
"""
from replay_handoff422 import *

def main():
 raw=(ROOT/'exports/fl2_fl3_grid_compare_20261023/R5NATIVE.BIN').read_bytes()
 cp=CP421.read_bytes();rows=[]
 for label,source in (('user_grid_fixture',raw[1308:2523]),('signed_pattern_fixture',bytes(((i*37)%128)-64 & 255 for i in range(1215)))):
  for transform,level,root3,direct in itertools.product((0,2),(0,1,2,3,4,5,6,7,8,15,255),(0,1),(0,1)):
   e=Harness(cp,raw,'native-builder');u=e.u;e.frame(dict(look='FL2'),consume=False)
   x=e.context;state=x['state'];root=x['root'];index=3 if direct else 0
   # Use the real selector's RAM address but explicitly seed a controlled table.
   # This test makes no assertion about the real camera's bytes at this address.
   u.mem_write(0x198c1ca,source);w(u,state+0x184,0x198c1ca)
   u.mem_write(state+0x188,bytes([1,transform]));u.mem_write(root+3,bytes([root3]));u.mem_write(root+0x2f,bytes([level]));u.mem_write(x['env']+6,bytes([direct]));u.mem_write(x['meta']+11,bytes([index]))
   target=x['work']+0x5c if direct else NATIVE_BANK
   u.mem_write(target-16,b'\xa5'*16);u.mem_write(target+1620,b'\x5a'*16)
   e.call(0x231654,x['ctx'],x['color'])
   packed=bytes(u.mem_read(target,1620));expected=model.model(source,e.order,level)
   assert packed==expected,(label,transform,level,root3,direct)
   assert bytes(u.mem_read(0x198c1ca,1215))==source
   assert bytes(u.mem_read(target-16,16))==b'\xa5'*16 and bytes(u.mem_read(target+1620,16))==b'\x5a'*16
   rows.append(dict(source_fixture=label,transform=transform,level=level,root3=root3,direct=direct,index=index,packed_sha256=sha(packed),matches_independent_model=True,source_unchanged=True,guards=True))
 report=dict(passed=True,cases=len(rows),cp_sha256=sha(cp),native_source_address='0x198c1ca',native_source_in_CP_file=False,native_source_file_offset=hex(0x198c1ca-0x108000),cp_file_length=len(cp),rows=rows,limits=['All CPU memory is synthetic; no camera/SD/ISP pixels.','Actual factory RAM source content and initialization/lifetime are not captured.','Only type1,root36=0,transform0/2 and explicitly valid direct/index0 destinations.','The index3 non-direct native destination is still unsupported; this script does not alter live route fields in any firmware.','Confirms transform0/2 byte-format equivalence for controlled 1215-byte signed fixtures, not a complete factory-restore implementation.'])
 out=HERE/'tests/native_restore_builder.json';out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(rows),output=str(out))))
if __name__=='__main__':main()
