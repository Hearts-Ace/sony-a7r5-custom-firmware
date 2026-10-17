#!/usr/bin/env python3
"""Finish raw backup in bounded read sessions, keeping previous partial evidence."""
import argparse,datetime,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];HOST=ROOT/'analysis/r5_live_system_20261014/host_tools'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('backup',type=Path);args=ap.parse_args();run=args.backup.resolve();m=json.loads((run/'manifest.json').read_text());assert m['state']=='partial';m['resume_sessions']=[];chunks=run/'raw_chunks';chunks.mkdir(exist_ok=False)
    def save():
        t=run/'manifest.json.tmp';t.write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n');t.replace(run/'manifest.json')
    def session(commands,label):
        boot=run/('ram_boot_'+label);r=subprocess.run([sys.executable,'-B',str(ROOT/'tools/r5_boot_probe.py'),'--output',str(boot)],timeout=65);rep=json.loads((boot/'report.json').read_text());assert rep.get('usb_queries_returncode')==0
        logp=run/(label+'.log');start=time.monotonic()
        with logp.open('w') as log:
            p=subprocess.Popen([str(HOST/'read_fastboot_usb_all'),*commands,'reboot'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            for line in p.stdout:
                log.write(line);log.flush()
                if line.startswith(('COMMAND','SAVED','PROGRESS')):print(line.rstrip(),flush=True)
            rc=p.wait()
        text=logp.read_text();record={'label':label,'returncode':rc,'reboot_okay':'COMMAND reboot\nREPLY OKAY' in text,'elapsed':round(time.monotonic()-start,3),'log':str(logp)};m['resume_sessions'].append(record);save();assert rc==0 and record['reboot_okay'],record
        time.sleep(3)
    rawentry=next(i for i in m['acquisition_plan'] if i['partition']=='nflasha');prefix=Path(rawentry['partial_path']);prefixsize=prefix.stat().st_size;assert prefixsize%65536==0;remain=rawentry['expected_bytes']-prefixsize;targetchunk=chunks/'userarea_tail.raw.bin'
    session(['oem partition dump nflasha '+hex(prefixsize//512)+' '+hex(remain//512),'upload:'+str(targetchunk),'oem dumpbrom','upload:'+str(run/'ap_bootrom.raw.A.bin.partial'),'oem cetus dumpbrom','upload:'+str(run/'cp_bootrom.raw.A.bin.partial')],'raw_tail_and_rom')
    assert targetchunk.stat().st_size==remain;target=Path(rawentry['path'])
    with target.open('xb') as out:
        for part in (prefix,targetchunk):
            with part.open('rb') as inp:
                for block in iter(lambda:inp.read(4<<20),b''):out.write(block)
        out.flush();os.fsync(out.fileno())
    target.chmod(0o600);assert target.stat().st_size==rawentry['expected_bytes']
    item={k:v for k,v in rawentry.items() if k!='partial_path'};item['sha256']=sha(target);item['source']='Prior successfully returned raw bytes plus contiguous remainder in a new session; subsequently compared to independent full logical reads';m['files'].append(item)
    for name in ('ap_bootrom','cp_bootrom'):
        entry=next(i for i in m['acquisition_plan'] if i['partition']==name);partial=Path(entry['partial_path']);assert partial.stat().st_size==entry['expected_bytes'];partial.replace(entry['path']);item={k:v for k,v in entry.items() if k!='partial_path'};item['sha256']=sha(Path(item['path']));m['files'].append(item)
    save()
    norparts=[]
    for i,off in enumerate(range(0,64<<20,4<<20)):
        path=chunks/f'cp_nor_{off:08x}.raw.bin';norparts.append(path)
        session(['oem cetus','oem cetus dumpnor:'+hex(off)+':0x400000','upload:'+str(path)],'cp_nor_'+str(i))
        assert path.stat().st_size==4<<20
    entry=next(i for i in m['acquisition_plan'] if i['partition']=='cp_nor');target=Path(entry['path'])
    with target.open('xb') as out:
        for path in norparts:
            with path.open('rb') as f:
                for b in iter(lambda:f.read(4<<20),b''):out.write(b)
        out.flush();os.fsync(out.fileno())
    target.chmod(0o600);assert target.stat().st_size==entry['expected_bytes'];item={k:v for k,v in entry.items() if k!='partial_path'};item['sha256']=sha(target);item['source']='16 contiguous 4 MiB read sessions';m['files'].append(item)
    m['state']='acquired';m['initial_usb_process_returncode']=m['usb_process_returncode'];m['usb_process_returncode']=0;m['reboot_okay']=all(i['reboot_okay'] for i in m['resume_sessions']);m['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save();print('RAW BACKUP COMPLETE',len(m['files']),flush=True)
if __name__=='__main__':main()
