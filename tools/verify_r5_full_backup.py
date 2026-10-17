#!/usr/bin/env python3
"""Verify raw and logical reads sector-by-sector and persist a restore inventory."""
import argparse,ast,datetime,hashlib,json,re,struct,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor/audit-python'))
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('backup',type=Path);ap.add_argument('--emmc-only',action='store_true');a=ap.parse_args();run=a.backup.resolve();m=json.loads((run/'manifest.json').read_text());assert m['state']=='acquired' or a.emmc_only
    report={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verification':'complete raw-versus-logical comparison, not sampling','files':[],'partitions':[],'persistent_camera_write_performed':False}
    def save():
        temp=run/'verification.json.tmp';temp.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');temp.replace(run/'verification.json')
    for item in m['files']:
        p=Path(item['path']);actual=sha(p);assert p.stat().st_size==item['expected_bytes'] and actual==item['sha256'];report['files'].append({'path':p.name,'size':p.stat().st_size,'sha256':actual,'verified':True})
    for name in ('nflashaB0','nflashaB1'):
        aa=run/(name+'.raw.A.img');bb=run/(name+'.raw.B.img');assert aa.read_bytes()==bb.read_bytes();report[name+'_repeat_identical']=True
    rawp=run/'nflasha.userarea.raw.A.img';raw=rawp.open('rb');table=raw.read(65536);assert table[:8]==b'82462.00';n=struct.unpack_from('<I',table,8)[0];assert 0<n<=64
    live=m['live_partitions'];logical=[p for p in live if re.fullmatch(r'nflasha[0-9]+',p['name'])]
    raw_entries={}
    for i in range(n):
        start,count,typ,flag=struct.unpack_from('<IIII',table,32+i*16)
        if flag&1:
            assert count>0 and (start+count)*512<=rawp.stat().st_size
            raw_entries['nflasha'+str(i+1)]={'start':start,'count':count,'type':typ}
    assert set(raw_entries)=={p['name'] for p in logical}
    assert max((p['start']+p['count'])*512 for p in raw_entries.values())==rawp.stat().st_size
    for p in logical:
        item=raw_entries[p['name']];assert item['start']==p['start_sector'] and item['count']==p['sector_count']
    (run/'sdm2_partition_table.raw.bin').write_bytes(table);report['raw_table_matches_live_inventory']=True;report['raw_table_slots']=n
    code=(ROOT/'analysis/sony_write_path_20261008/reference/DavidBuchanan314-ILCE-7M4-RE-2328d18/payloads/fastboot/src/spacc.c').read_text();arr=re.search(r'part_key\[64\]\s*=\s*\{(.*?)\}',code,re.S).group(1);key=bytes(int(v,16) for v in re.findall(r'0x([0-9a-fA-F]{2})',arr));assert len(key)==64
    algo=algorithms.AES(key);save()
    for p in logical:
        name=p['name'];path=run/(name+'.logical.A.img');raw.seek(p['start_sector']*512);done=0;start_t=time.monotonic();dig=hashlib.sha256()
        with path.open('rb') as f:
            while done<p['sector_count']:
                count=min(8192,p['sector_count']-done);enc=raw.read(count*512);expected=f.read(count*512);assert len(enc)==len(expected)==count*512
                output=bytearray(count*512)
                for i in range(count):
                    dec=Cipher(algo,modes.XTS((p['start_sector']+done+i).to_bytes(16,'little'))).decryptor();lo=i*512;output[lo:lo+512]=dec.update(enc[lo:lo+512])+dec.finalize()
                if output!=expected:
                    idx=next(i for i,(x,y) in enumerate(zip(output,expected)) if x!=y);raise RuntimeError(f'{name}: independent raw/logical mismatch at byte {done*512+idx}')
                dig.update(output);done+=count
                if done%131072==0:print(f'VERIFY {name} {done*512}/{p["bytes"]} bytes',flush=True)
        item={'name':name,'start_sector':p['start_sector'],'bytes':p['bytes'],'raw_decrypt_equals_entire_logical':True,'sha256':dig.hexdigest(),'elapsed_seconds':round(time.monotonic()-start_t,3)};report['partitions'].append(item);save();print('VERIFIED',name,p['bytes'],flush=True)
    raw.close();report['logical_partitions_verified']=len(logical);report['all_allocated_emmc_partitions_covered']=len(report['partitions'])==m['logical_partition_count'];report['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();report['state']='emmc_verified' if a.emmc_only and m['state']!='acquired' else 'verified';report['reboot_reply_okay']=m['reboot_okay'];save()
    (run/'SHA256SUMS').write_text(''.join(i['sha256']+'  '+i['path']+'\n' for i in report['files']))
    restore={'model':'Sony ILCE-7RM5 / A7R V','firmware':'4.00','device_storage_written_in_this_job':False,'hash_inventory':'SHA256SUMS','raw_table':'sdm2_partition_table.raw.bin','scope':'All valid SDM2 partitions plus boot0 and boot1; raw userarea max extent 0x379000 sectors; EXT_CSD full capacity not measured.','rules':['Use logical images only with a payload whose normal nflashaN flash performs identical absolute-sector AES-XTS encryption.','Raw user-area image is encrypted and starts with the plaintext SDM2 table; never flash it to a logical partition.','Boot0/boot1 use separate hardware areas and encryption rules; keep as backups, do not routinely restore them.','Verify target identity, image hash/size, write result and entire readback before reboot.','Normal write path and recovery after partition1 corruption remain untested.','eMMC boot area 4 MiB is the payload fixed size; EXT_CSD BOOT_SIZE_MULT has not been read.'],'partitions':[{'name':p['name'],'start_sector':p['start_sector'],'sectors':p['sector_count'],'bytes':p['bytes'],'image':p['name']+'.logical.A.img','sha256':next(i['sha256'] for i in report['partitions'] if i['name']==p['name'])} for p in logical]}
    restore['additional_regions']=[{**i,'purpose':('immutable ROM reference, not for flashing' if 'bootrom' in i['path'] else 'raw recovery evidence; requires a separately verified matching raw write path'),'layer':'raw'} for i in report['files'] if 'logical' not in i['path']]
    restore['partition_table_sha256']=sha(run/'sdm2_partition_table.raw.bin')
    (run/'restore_inventory.json').write_text(json.dumps(restore,indent=2,ensure_ascii=False)+'\n');print(json.dumps({'state':report['state'],'logical_partitions':len(logical),'backup':str(run)},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
