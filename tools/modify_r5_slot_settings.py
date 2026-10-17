#!/usr/bin/env python3
"""Acquire, prepare, and apply the user-authorized two-property R5 settings patch.

Each phase is explicit. Acquisition leaves the camera in maintenance mode on
success. Writes are restricted to a freshly verified nflasha2 sparse image.
"""
if __name__ == '__main__':
    raise SystemExit('Historical reference/helper only; standalone execution is disabled. See PUBLICATION.md.')

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

from build_r5_partition1 import require
from patch_r5_slot_settings import SIZE, START_SECTOR, digest, build, patch_image, apply_sparse, changed_sectors

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT/'analysis/r5_live_system_20261014/host_tools'
BACKUP = ROOT/'backups/R5_4.00_20261014_full'
RAW_DUMP = 'oem partition dump nflasha 0xc000 0xa000'
PAYLOAD_SHA = '330ac322bd0e40a7bb4974f69a2667e7d59a25e59c1322339690f30a3ceadbdc'


def save(path, obj):
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
    tmp.chmod(0o600)
    tmp.replace(path)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def execute(run, label, args, host=None):
    host = host or HOST/'read_fastboot_usb_all'
    log = run/(label+'.log')
    with log.open('x') as f:
        try:
            proc = subprocess.run([str(host), *map(str,args)],stdout=f,stderr=subprocess.STDOUT,text=True,timeout=60)
        finally:
            f.flush()
            print(log.read_text(),flush=True)
    output = log.read_text()
    require(proc.returncode == 0, label+' failed: '+str(proc.returncode))
    return output


def reboot(run, label='reboot'):
    out = execute(run,label,['reboot'],HOST/'read_fastboot_usb')
    require('COMMAND reboot\nREPLY OKAY' in out, 'No normal reboot acknowledgment')


def raw_verify(raw, logical):
    sys.path.insert(0,str(ROOT/'vendor/audit-python'))
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    code = (ROOT/'analysis/sony_write_path_20261008/reference/DavidBuchanan314-ILCE-7M4-RE-2328d18/payloads/fastboot/src/spacc.c').read_text()
    arr = re.search(r'part_key\[64\]\s*=\s*\{(.*?)\}',code,re.S).group(1)
    key = bytes(int(v,16) for v in re.findall(r'0x([0-9a-fA-F]{2})',arr))
    require(len(key)==64 and len(raw)==len(logical)==SIZE, 'Invalid raw/XTS inputs')
    algo = algorithms.AES(key)
    for i in range(SIZE//512):
        dec = Cipher(algo,modes.XTS((START_SECTOR+i).to_bytes(16,'little'))).decryptor()
        require(dec.update(raw[i*512:(i+1)*512])+dec.finalize()==logical[i*512:(i+1)*512],
                'Independent AES-XTS mismatch at sector '+str(i))


def acquire(run, port, carrier_before_reset=False):
    require(port is not None,'Explicit port required')
    run.mkdir(mode=0o700,exist_ok=False)
    state = dict(state='acquiring',started_utc=utc(),port=port,target='nflasha2',
                 persistent_write_command_sent=False,normal_reboot_acknowledged=False)
    save(run/'report.json',state)
    source = (ROOT/'tools/r5_settings_ram_boot.py').read_text()
    source = source.replace('ROOT = Path(__file__).resolve().parents[1]','ROOT = Path('+repr(str(ROOT))+')')
    helper = run/'ram_boot_helper.py'
    helper.write_text(source)
    try:
        command=[sys.executable,'-B',str(helper),'--output',str(run/'ram_boot'),'--port',port]
        if carrier_before_reset:
            command.append('--carrier-before-reset')
        subprocess.run(command,check=True,timeout=65)
        boot = json.loads((run/'ram_boot/report.json').read_text())
        require(boot.get('usb_transport_verified') and boot.get('usb_queries_returncode')==0 and
                boot.get('payload_sha256')==PAYLOAD_SHA,'RAM boot validation failed')
        query = (run/'ram_boot/usb_queries.txt').read_text()
        require(re.search(r'INFOnflasha2\s+0000c000 0000a000 fat',query),'Wrong partition geometry')
        out = execute(run,'acquisition',['getvar:max-download-size',
            'oem partition dump nflasha 0 0x80','upload:'+str(run/'pre.sdm2.raw.bin'),
            'oem dumpbrom','upload:'+str(run/'pre.ap_bootrom.bin'),
            'oem partition dump nflasha2','upload:'+str(run/'pre.settings.logical.img'),
            RAW_DUMP,'upload:'+str(run/'pre.settings.raw.img')])
        require((run/'pre.sdm2.raw.bin').read_bytes()==(BACKUP/'sdm2_partition_table.raw.bin').read_bytes(),
                'Live SDM2 differs from verified camera backup')
        require((run/'pre.ap_bootrom.bin').read_bytes()==(BACKUP/'ap_bootrom.raw.A.bin').read_bytes(),
                'Live ROM differs from verified camera backup')
        before = (run/'pre.settings.logical.img').read_bytes()
        require(before[:512]==(run/'ram_boot/nflasha2_first_sector.logical.bin').read_bytes(),
                'Independent first sector differs')
        raw_verify((run/'pre.settings.raw.img').read_bytes(),before)
        _, facts = patch_image(before)
        state.update(state='acquired_verified_maintenance_mode',complete_raw_XTS_verified=True,
                     partition_geometry_verified=True,first_sector_verified=True,
                     before_sha256=digest(before),before_raw_sha256=digest((run/'pre.settings.raw.img').read_bytes()),
                     initial_target_values={k:v['targets'] for k,v in facts['backups'].items()},
                     acquisition_finished_utc=utc())
        save(run/'report.json',state)
        print('ACQUIRED AND VERIFIED; camera remains in maintenance mode, no persistent writes.',flush=True)
    except Exception as exc:
        state.update(state='failed_before_write',error=repr(exc))
        try:
            reboot(run,'acquisition_cleanup_reboot')
            state['normal_reboot_acknowledged']=True
        except Exception as cleanup:
            state['cleanup_error']=repr(cleanup)
        save(run/'report.json',state)
        raise


def prepare(run):
    state = json.loads((run/'report.json').read_text())
    require(state['state']=='acquired_verified_maintenance_mode','Need a fresh verified acquisition')
    before = (run/'pre.settings.logical.img').read_bytes()
    require(digest(before)==state['before_sha256'],'Acquisition modified')
    report = build(run/'pre.settings.logical.img',run/'prepared')
    require(0 < len(report['changed_sectors']) <= 8, 'Unexpected or already-correct target sectors')
    source = (ROOT/'analysis/r5_verifykey_skip_flash_20261014/partition1_usb.c').read_text()
    source = source.replace('nflasha1','nflasha2').replace('0x80 0xbf80','0xc000 0xa000')
    forward = report['files']['patch.sparse.img']['sha256']
    reverse = report['files']['restore.sparse.img']['sha256']
    old = 'if(strcmp(hex,"ce51008ae51696004488b02ae291b23390edcea70870d0c60280ebeccd1a53ee"))'
    require(source.count(old)==1,'Unexpected host hash guard')
    source = source.replace(old,'if(strcmp(hex,"'+forward+'") && strcmp(hex,"'+reverse+'"))')
    source = source.replace('static unsigned char staged[524288];',
                            'static int download_approved = 0;\nstatic unsigned char staged[524288];')
    marker = 'static int command(const char *arg) {\n'
    require(source.count(marker)==1,'Unexpected host command entry')
    source = source.replace(marker,marker+
        '    int is_flash=!strcmp(arg,"flash:nflasha2");\n'
        '    if(is_flash && !download_approved){fprintf(stderr,"No approved download in this process\\n");return -1;}\n'
        '    download_approved=0;\n')
    marker = 'if(!memcmp(b,"OKAY",4)){if(saved_path)'
    require(source.count(marker)==1,'Unexpected host OKAY path')
    source = source.replace(marker,'if(!memcmp(b,"OKAY",4)){if(!strncmp(arg,"download:/",10)){if(downloading){fprintf(stderr,"Download OKAY before complete DATA transfer\\n");return -1;}download_approved=1;}if(saved_path)')
    require('flash:nflasha1' not in source and '0x80 0xbf80' not in source,'Old target survived')
    c = run/'prepared/settings_usb.c'
    c.write_text(source)
    host = run/'prepared/settings_usb'
    subprocess.run(['/usr/bin/clang','-O2',str(c),'-o',str(host),'-framework','IOKit','-framework','CoreFoundation'],check=True)
    state.update(state='prepared',candidate_sha256=report['after_sha256'],changed_sectors=report['changed_sectors'],
                 prepared_file_hashes={str(p.relative_to(run)):digest(p.read_bytes()) for p in
                   (host,c,run/'prepared/patch.sparse.img',run/'prepared/restore.sparse.img',run/'prepared/candidate.logical.img')},
                 execution_source_hashes={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in
                   (Path(__file__).resolve(),ROOT/'tools/patch_r5_slot_settings.py')})
    save(run/'report.json',state)
    print(json.dumps(report,indent=2,ensure_ascii=False),flush=True)


def write(run):
    state = json.loads((run/'report.json').read_text())
    require(state['state']=='prepared' and not state['persistent_write_command_sent'],'Not a fresh prepared attempt')
    for p,h in state['prepared_file_hashes'].items():
        require(digest((run/p).read_bytes())==h,'Prepared artifact changed: '+p)
    for p,h in state['execution_source_hashes'].items():
        require(digest((ROOT/p).read_bytes())==h,'Execution source changed: '+p)
    host = run/'prepared/settings_usb'
    try:
        execute(run,'immediate_prewrite',['oem partition dump nflasha2','upload:'+str(run/'prewrite.settings.logical.img'),
            RAW_DUMP,'upload:'+str(run/'prewrite.settings.raw.img'),
            'oem partition dump nflasha 0 0x80','upload:'+str(run/'prewrite.sdm2.raw.bin')],host)
        before = (run/'pre.settings.logical.img').read_bytes()
        raw_before = (run/'pre.settings.raw.img').read_bytes()
        require(digest(before)==state['before_sha256'] and digest(raw_before)==state['before_raw_sha256'],'Saved acquisition changed')
        require((run/'prewrite.settings.logical.img').read_bytes()==before and
                (run/'prewrite.settings.raw.img').read_bytes()==raw_before and
                (run/'prewrite.sdm2.raw.bin').read_bytes()==(run/'pre.sdm2.raw.bin').read_bytes(),
                'Live partition changed after acquisition; refusing write')
        candidate = (run/'prepared/candidate.logical.img').read_bytes()
        rebuilt, sectors = apply_sparse(before,(run/'prepared/patch.sparse.img').read_bytes())
        require(rebuilt==candidate and sectors==state['changed_sectors'],'Sparse image final validation failed')
        require(patch_image(before)[0]==candidate,'Candidate no longer matches exact property patch')
        state.update(state='write_in_progress',persistent_write_command_sent=True,immediate_prewrite_verified=True)
        save(run/'report.json',state)
        out = execute(run,'flash',['download:'+str(run/'prepared/patch.sparse.img'),'flash:nflasha2'],host)
        require(f'wrote {len(sectors)} sectors to nflasha2' in out,'Unexpected write acknowledgment')
        state.update(state='reading_back',write_acknowledged=True)
        save(run/'report.json',state)
        execute(run,'readback',['oem partition dump nflasha2','upload:'+str(run/'post.settings.logical.img'),
            RAW_DUMP,'upload:'+str(run/'post.settings.raw.img'),
            'oem partition dump nflasha 0 0x80','upload:'+str(run/'post.sdm2.raw.bin')],host)
        post = (run/'post.settings.logical.img').read_bytes()
        raw_post = (run/'post.settings.raw.img').read_bytes()
        require(post==candidate,'Complete logical readback mismatch')
        require(changed_sectors(before,post)==changed_sectors(raw_before,raw_post)==sectors,'Raw/logical changed sectors differ')
        require((run/'post.sdm2.raw.bin').read_bytes()==(run/'pre.sdm2.raw.bin').read_bytes(),'Partition table changed')
        raw_verify(raw_post,post)
        # Idempotence also reparses both checksums and confirms canonical values.
        same, facts = patch_image(post)
        require(same==post and not facts['changed_partition_offsets'],'Post-write property verification failed')
        save(run/'readback_verification.json',dict(complete_logical_matches_candidate=True,
             independent_XTS_all_40960_sectors_verified=True,partition_table_unchanged=True,
             changed_sectors=sectors,logical_sha256=digest(post),raw_sha256=digest(raw_post),backups=facts['backups']))
        state.update(state='write_and_readback_verified',complete_logical_readback_verified=True,
                     complete_independent_raw_XTS_verified=True,partition_table_unchanged=True)
        save(run/'report.json',state)
        reboot(run)
        state.update(state='written_verified_reboot_acknowledged',normal_reboot_acknowledged=True,finished_utc=utc())
        save(run/'report.json',state)
        print(json.dumps(state,indent=2,ensure_ascii=False),flush=True)
    except Exception as exc:
        state.update(state='write_needs_assessment' if state['persistent_write_command_sent'] else 'failed_before_write',error=repr(exc))
        if not state['persistent_write_command_sent']:
            try:
                reboot(run,'prewrite_cleanup_reboot')
                state['normal_reboot_acknowledged']=True
            except Exception as cleanup:
                state['cleanup_error']=repr(cleanup)
        save(run/'report.json',state)
        raise


if __name__=='__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=('acquire','prepare','write'))
    ap.add_argument('--run',type=Path,required=True)
    ap.add_argument('--port')
    ap.add_argument('--carrier-before-reset',action='store_true')
    a = ap.parse_args()
    run = a.run.resolve()
    if a.action=='acquire': acquire(run,a.port,a.carrier_before_reset)
    elif a.action=='prepare': prepare(run)
    else: write(run)
