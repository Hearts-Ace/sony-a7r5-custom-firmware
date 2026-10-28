"""Independent checks of saved 4.33 generic templates; no builder imports."""
from pathlib import Path
import binascii,hashlib,json,struct,sys,tarfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from sony_bk4 import find_banks

PREFIX='0110_backup/SYSIPSX-DSLR/GL/'
SUM='0111_backup_sum/backup.sum'
NAMES=('CX89200_ALLLANG.bin','CX89200_E38.bin','CX89200_J1.bin','CX89200_KR2.bin','CX89200_UC2.bin',
       'CX89201_AF1.bin','CX89201_ALLLANG.bin','CX89201_AP2.bin','CX89201_CEC.bin',
       'CX89201_CN2.bin','CX89201_IN5.bin','CX89201_JE3.bin')

def sha(b):return hashlib.sha256(b).hexdigest()

def verify():
    manifest=json.loads((HERE/'preservation/generated/templates_manifest.json').read_text())
    assert manifest['passed'] and manifest['matrix_mode']=='dynamic' and manifest['count']==12
    rows=manifest['replacement_files'];expected={PREFIX+n for n in NAMES}|{SUM}
    assert len(rows)==13 and {r['member'] for r in rows}==expected
    paths={r['member']:ROOT/r['path'] for r in rows}
    for r in rows:
        p=paths[r['member']]
        assert not Path(r['path']).is_absolute() and '..' not in Path(r['path']).parts
        assert p.resolve().is_relative_to((HERE/'preservation/generated').resolve())
        assert p.stat().st_size==r['bytes'] and sha(p.read_bytes())==r['sha256']
    ccR6=(ROOT/'analysis/r6_st_reverse_20261028/r6_st_cc1_R5_delta48.bin').read_bytes()
    a1R6=(ROOT/'analysis/r6_st_reverse_20261028/r6_st_block13_A1_192.bin').read_bytes()
    assert len(ccR6)==48 and sha(ccR6)=='e578cd18c4736c404f62049a2e00e0cb59dcd9b3c69ebd4096c6fff8ea419485'
    assert len(a1R6)==192 and sha(a1R6)=='fe5a1f5c1636cd146a5f1bfa32def49cac06a58ac5004355b96f546d0f67ef4e'
    donor=(ROOT/'unpacked/fx2/firmware/0110_backup/SYSIPSX-DSLR/DOC/CX96900_ALLLANG.bin').read_bytes()
    assert sha(donor)=='fdee302d240ec1534349e6c9a688a12c883c2cbb7be3ffd97376b419592dc331'
    bank=find_banks(donor)[1]
    dc,dm=[bank.property(k).data for k in (0x02a40001,0x02a4000d)]
    assert dc[0xefe]==1
    wanted={0x02a40000:[(0x930,b'\x70\xff')],
            0x02a40001:[(0x1250,ccR6),(0x1236,bytes([22,24,23,25]))],
            0x02a4000d:[(0x2a0,a1R6),(0x1cc,bytes([22,24,23,25]))]}
    for i in (22,23,24,25):
        off=0x1250+64*i;v=struct.unpack_from('<24h',dc,off)
        vals=list(v[:8])+[v[8+j]-v[j] for j in range(8)]+[v[16+j]-v[j] for j in range(8)]
        wanted[0x02a40001].append((off,struct.pack('<24h',*vals)))
        off=0x1e0+768*i
        wanted[0x02a4000d].append((off,dm[off:off+576]))
    assert sum(len(v) for spans in wanted.values() for _,v in spans)==2746
    archive=ROOT/manifest['source_archive']
    checks=[]
    with tarfile.open(archive,'r:') as t:
        members={m.name:m for m in t.getmembers()}
        assert {n for n,m in members.items() if n.startswith('0110_backup/') and n.endswith('.bin') and m.isfile()}==expected-{SUM}
        for name in sorted(expected-{SUM}):
            before=t.extractfile(name).read();after=paths[name].read_bytes()
            row=next(r for r in rows if r['member']==name)
            assert sha(before)==row['source_sha256'] and len(before)==len(after)==2372469
            assert row['tar_offset_data']==members[name].offset_data
            original=find_banks(before);patched=find_banks(after)
            assert [(b.offset,b.size) for b in original]==[(b.offset,b.size) for b in patched]
            assert len(original)==len(patched)==2
            expected_bytes=bytearray(before)
            for key,spans in wanted.items():
                a,b=original[1].property(key),patched[1].property(key)
                assert a.attributes==b.attributes==8
                assert (a.file_offset,len(a.data),a.capacity)==(b.file_offset,len(b.data),b.capacity)
                for off,value in spans:
                    assert b.data[off:off+len(value)]==value
                    start=a.file_offset+off
                    expected_bytes[start:start+len(value)]=value
            checksum_offset=patched[1].offset+32
            expected_bytes[checksum_offset:checksum_offset+4]=after[checksum_offset:checksum_offset+4]
            assert bytes(expected_bytes)==after,'Unapproved byte changed in '+name
            final_mat=patched[1].property(0x02a4000d).data
            for i in (22,23,24,25):
                off=0x1e0+768*i
                assert final_mat[off:off+768]==dm[off:off+768]
            assert patched[1].property(0x02a40000).data[0x930:0x934]==b'\x70\xff\x00\x06'
            checks.append(dict(member=name,sha256=sha(after),changed_bytes=sum(a!=b for a,b in zip(before,after)),
                               only_13_parameter_ranges_and_BK4_checksum_changed=True,
                               full_dynamic_FL23_banks_equal=True,ST_and_AWB_exact=True))
        old=t.extractfile(SUM).read();new=paths[SUM].read_bytes()
        assert len(old)==len(new) and sha(old)==next(r['source_sha256'] for r in rows if r['member']==SUM)
        old_lines=old.decode('ascii').splitlines(keepends=True);new_lines=new.decode('ascii').splitlines(keepends=True)
        assert len(old_lines)==len(new_lines)==15  # MainDest, two directories, twelve templates.
        crc_count=0
        for left,right in zip(old_lines,new_lines):
            a,b=left.rstrip('\r\n').split(','),right.rstrip('\r\n').split(',')
            assert len(a)==len(b)==12 and a[10]==b[10]
            name='0110_backup/'+a[10]
            if name in paths:
                assert a[:1]+a[2:]==b[:1]+b[2:]
                assert int(b[1],16)==binascii.crc32(paths[name].read_bytes())&0xffffffff
                assert int(a[1],16)==binascii.crc32(t.extractfile(name).read())&0xffffffff
                assert int(b[2],16)==paths[name].stat().st_size
                crc_count+=1
            else:assert left==right
        assert crc_count==12
    return paths,dict(passed=True,templates=12,backup_sum_CRC_rows=12,
                      template_rows=checks,all_unrelated_defaults_and_personal_partition_excluded=True,
                      R6_ST_CC1_24_and_A1_96_verified=True,AWB_bytes='70ff0006',matrix_mode='dynamic',camera_io=False)

if __name__=='__main__':
    _,result=verify()
    print(json.dumps(result,ensure_ascii=False))
