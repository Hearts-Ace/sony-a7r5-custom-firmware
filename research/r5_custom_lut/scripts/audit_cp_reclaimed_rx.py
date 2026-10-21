"""Bounded direct-branch/literal audit of the explicitly reclaimable old RX.

This is supplementary to source function boundaries, not an indirect-call proof.
"""
from pathlib import Path
import hashlib,json,struct,sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'vendor/audit-python'))
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
SOURCE=ROOT/'research/r5_custom_lut/evidence/sd405_native_transport_v1/cp405-transfer-gate.NONINSTALLABLE.bin'
SHA='41bffc6bd0121eb9948f916c0496c35a6d355d5bebc928f639e32c5d8568f954'
REGIONS=((0x1196040,0x11961d4),(0x1196200,0x1196324),(0x1196b34,0x1197000))
def audit(out=None,seal_replaced=False):
    b=SOURCE.read_bytes();assert hashlib.sha256(b).hexdigest()==SHA
    inside=lambda p:any(a<=p<z for a,z in REGIONS)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB);direct=[];literals=[]
    for off in range(0,len(b)-4,2):
        at=0x108000+off
        if inside(at):continue
        val=struct.unpack_from('<I',b,off)[0]
        if inside(val&~1):literals.append(dict(site=hex(at),value=hex(val)))
        if struct.unpack_from('<H',b,off)[0]&0xf800!=0xf000:continue
        ins=list(md.disasm(b[off:off+4],at))
        if len(ins)==1 and ins[0].mnemonic in ('bl','b.w') and ins[0].op_str.startswith('#0x'):
            target=int(ins[0].op_str[1:],16)
            if inside(target):direct.append(dict(site=hex(at),target=hex(target),kind=ins[0].mnemonic))
    assert not direct and not literals,(direct,literals)
    if seal_replaced:
        # The old44B seal is replaced by one8B literal jump. Its remaining36B
        # are no longer executable under any preserved entry. Audit old-tail
        # external references separately; the real receiver targets its entry.
        tail=(0x11961dc,0x1196200);tail_refs=[]
        for off in range(0,len(b)-4,2):
            at=0x108000+off
            if 0x11961d4<=at<0x1196200:continue
            value=struct.unpack_from('<I',b,off)[0]
            if tail[0]<=value&~1<tail[1]:tail_refs.append(('literal',hex(at),hex(value)))
            if struct.unpack_from('<H',b,off)[0]&0xf800==0xf000:
                decoded=list(md.disasm(b[off:off+4],at))
                if len(decoded)==1 and decoded[0].mnemonic in ('bl','b.w') and decoded[0].op_str.startswith('#0x'):
                    target=int(decoded[0].op_str[1:],16)
                    if tail[0]<=target<tail[1]:tail_refs.append(('branch',hex(at),hex(target)))
        assert not tail_refs,tail_refs
    assert b[0x1196b34-0x108000:0x1197000-0x108000]==bytes(1228)
    result=dict(schema='r5-405-reclaimed-rx-audit/1',source_sha256=SHA,camera_io=False,
        regions=[dict(start=hex(a),end_exclusive=hex(z),bytes=z-a,original_sha256=hashlib.sha256(b[a-0x108000:z-0x108000]).hexdigest())for a,z in REGIONS],
        external_thumb_BL_BW=direct,external_aligned_u32_literals=literals,seal_entry_replaced=seal_replaced,
        additional_seal_tail=dict(start='0x11961dc',bytes=36,external_references=tail_refs)if seal_replaced else None,
        boundaries='Preservebank_begin1196000..6040,bank_seal11961d4..6200;receiver/transport end1196b34.',
        limitations=['Linear Thumb BL/B.W and every halfword-aligned u32 literal scan only; ARM/indirect/computed references not a general proof.',
            'Must be combined with source-bound old bank helper use audit and loader/MMU proof.'])
    if out:Path(out).write_text(json.dumps(result,indent=2)+'\n')
    return result
if __name__=='__main__':print(json.dumps(audit(sys.argv[1]if len(sys.argv)>1 else None)))
