#!/usr/bin/env python3
"""Acquire all live SDM2 partitions, raw user-area extent, boot regions and ROMs."""
import argparse,datetime,hashlib,json,os,re,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HOST=ROOT/'analysis/r5_live_system_20261014/host_tools'
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();run=a.output.resolve();run.mkdir(parents=True,exist_ok=False);run.chmod(0o700)
    manifest={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'state':'acquiring','persistent_camera_write_commands_sent':False,'files':[],'limits':['Raw user area covers SDM2 maximum extent, not independently measured EXT_CSD capacity.','Restore writes and recovery after a broken boot partition have not been tested.']}
    def save():
        tmp=run/'manifest.json.tmp';tmp.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n');tmp.replace(run/'manifest.json')
    save()
    boot=run/'ram_boot'
    r=subprocess.run([sys.executable,'-B',str(ROOT/'tools/r5_boot_probe.py'),'--output',str(boot)],timeout=60)
    b=json.loads((boot/'report.json').read_text());manifest['boot_report']=b
    if not b.get('ready_line_observed') or b.get('usb_queries_returncode')!=0:
        manifest['state']='failed_boot';save();raise RuntimeError('RAM boot/configuration/read probe failed')
    query=(boot/'usb_queries.txt').read_text();rows=[]
    for name,start,count,kind in re.findall(r'REPLY INFO(nflasha\w*)\s+([0-9a-f]{8})\s+([0-9a-f]{8})\s+(\w+)',query):
        rows.append({'name':name,'start_sector':int(start,16),'sector_count':int(count,16),'bytes':int(count,16)*512,'type':kind})
    assert len(rows)>=20 and len({r['name'] for r in rows})==len(rows)
    manifest['live_partitions']=rows;manifest['logical_partition_count']=len([r for r in rows if r['name'] not in ('nflasha','nflashaB0','nflashaB1')]);save()
    plan=[];commands=['getvar:version','oem partition','oem cetus']
    for r in rows:
        if r['name']=='nflasha':continue
        layer='raw' if r['name'] in ('nflashaB0','nflashaB1') else 'logical'
        reps=('A','B') if layer=='raw' else ('A',)
        for rep in reps:
            target=run/f"{r['name']}.{layer}.{rep}.img";partial=target.with_suffix('.img.partial')
            plan.append({'path':str(target),'partial_path':str(partial),'expected_bytes':r['bytes'],'partition':r['name'],'layer':layer,'replicate':rep})
            commands.extend(['oem partition dump '+r['name'],'upload:'+str(partial)])
    raw=next(r for r in rows if r['name']=='nflasha');target=run/'nflasha.userarea.raw.A.img';partial=target.with_suffix('.img.partial');plan.append({'path':str(target),'partial_path':str(partial),'expected_bytes':raw['bytes'],'partition':'nflasha','layer':'raw','replicate':'A'});commands.extend(['oem partition dump nflasha','upload:'+str(partial)])
    for name,cmd,size in [('ap_bootrom','oem dumpbrom',49152),('cp_bootrom','oem cetus dumpbrom',49152),('cp_nor','oem cetus dumpnor',67108864)]:
        target=run/(name+'.raw.A.bin');partial=target.with_suffix('.bin.partial');plan.append({'path':str(target),'partial_path':str(partial),'expected_bytes':size,'partition':name,'layer':'raw','replicate':'A'});commands.extend([cmd,'upload:'+str(partial)])
    commands.append('reboot');manifest['acquisition_plan']=plan;save()
    logfile=run/'acquisition.log';manifest['log_path']=str(logfile);save()
    with logfile.open('w') as log:
        p=subprocess.Popen([str(HOST/'read_fastboot_usb_all'),*commands],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
        for line in p.stdout:
            log.write(line);log.flush()
            if line.startswith(('COMMAND','SAVED','PROGRESS')):
                print(line.rstrip(),flush=True)
                if line.startswith('SAVED'):
                    filepath=line.split(' ',3)[3].strip();entry=next(i for i in plan if i['partial_path']==filepath);partial=Path(filepath);assert partial.stat().st_size==entry['expected_bytes'];partial.replace(entry['path']);item={k:v for k,v in entry.items() if k!='partial_path'};item['sha256']=digest(Path(item['path']));manifest['files'].append(item);save()
        code=p.wait()
    manifest['usb_process_returncode']=code;manifest['reboot_okay']='COMMAND reboot\nREPLY OKAY' in logfile.read_text();manifest['state']='acquired' if code==0 and len(manifest['files'])==len(plan) else 'partial';manifest['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
    print(json.dumps({'state':manifest['state'],'files':len(manifest['files']),'reboot_okay':manifest['reboot_okay'],'manifest':str(run/'manifest.json')},ensure_ascii=False),flush=True)
    if code:
        raw_item=next(i for i in plan if i['partition']=='nflasha')
        raw_partial=Path(raw_item['partial_path'])
        if raw_partial.exists() and raw_partial.stat().st_size>0 and len(manifest['files'])==len(plan)-4:
            print('Long raw upload failed; switching to bounded resume sessions.',flush=True)
            subprocess.run([sys.executable,'-B',str(ROOT/'tools/resume_r5_raw_backup.py'),str(run)],check=True)
        else:
            raise SystemExit(code)
if __name__=='__main__':main()
