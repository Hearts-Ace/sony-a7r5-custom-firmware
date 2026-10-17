#!/usr/bin/env python3
"""Explicit fresh acquisition and scoped R5 M4-method personal-settings deployment.

Only write command: flash:nflasha2, with a hash-pinned changed-sector sparse image.
No version/update flag edits, no automatic rollback, no other partition writes.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

from build_r5_m4strict_personal import build_image, SLOTS
from build_r5_partition1 import FatImage, require
from modify_r5_slot_settings import execute, raw_verify, reboot, save, utc
from patch_r5_slot_settings import digest, changed_sectors, make_sparse, apply_sparse
from sony_bk4 import find_banks

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / 'analysis/r5_live_system_20261014/host_tools'
BACKUP = ROOT / 'backups/R5_4.00_20261014_full'
RAW_DUMP = 'oem partition dump nflasha 0xc000 0xa000'
PAYLOAD_SHA = '330ac322bd0e40a7bb4974f69a2667e7d59a25e59c1322339690f30a3ceadbdc'
MODULE_SHA = 'f944d89d012f356afd5fbf47b54739dc811f06b4acf6f11872a1ad7f20cc77c3'
SERIAL_SHA = 'd2262ca69ecfb0cb14b1c310998999692ed7ceb5cb106d2fb65fa421223264e5'
PINS = {
    'tools/r5_settings_ram_boot.py': '1da898c28ffea300571f05751e951e6ae386a8756f3783c4b27ddb6b11e17e06',
    'tools/build_r5_m4strict_personal.py': 'a95187c2d6dcb5633f74c35f10ab5a687216b624f542a7af56a5dd79763132ce',
    'tools/modify_r5_slot_settings.py': 'c5ec7a0cfa57c1f5f12749c58216f4cf9a948b4dbbffe015346cfcfaa30f5816',
    'tools/patch_r5_slot_settings.py': '98c89dc124920f6dd91124194a1df5e5473d541291b4dce2903bbf795c97897f',
    'analysis/r5_verifykey_skip_flash_20261014/partition1_usb.c': 'bbf3faa3e45d04ec7f1231587721c70cbcea31f42846656d5bf21cc0fbb3b0c3',
}


def verify_pins():
    for name, expected in PINS.items():
        require(digest((ROOT / name).read_bytes()) == expected, 'Changed reviewed source: ' + name)


def snapshot(data):
    fs = FatImage(data)
    slots = {}
    for name in ('/backup.bin', '/backup.bak'):
        banks = find_banks(fs.read(name))
        values = {}
        for key in SLOTS:
            matches = []
            for bank in banks:
                try:
                    matches.append(bank.property(key))
                except KeyError:
                    pass
            require(len(matches) == 1, 'Expected unique personal slot')
            values[f'{key:08x}'] = matches[0].data.hex()
        slots[name] = values
    updater = {p: {'size': e['size'], 'sha256': digest(fs.read(p)),
                   'small_value_hex': fs.read(p).hex() if e['size'] <= 16 else None}
               for p, e in fs.entries.items() if p.startswith('/updater/') and not e['is_directory']}
    return {'slots': slots, 'updater_files': updater}


def audit_candidate(before, after):
    # Independent FAT parser proves all files other than the two BK4 containers
    # retain exact contents and their allocation/directory metadata.
    a, b = FatImage(before), FatImage(after)
    require(a.entries == b.entries, 'Filesystem layout changed')
    for path, entry in a.entries.items():
        if not entry['is_directory'] and path not in ('/backup.bin', '/backup.bak'):
            require(a.read(path) == b.read(path), 'Unrelated file changed: ' + path)
    rebuilt, facts = build_image(before)
    require(rebuilt == after, 'Candidate differs from author-method builder')
    require(build_image(after)[0] == after, 'Candidate is not idempotent')
    sectors = changed_sectors(before, after)
    require(len(sectors) <= 64, 'Unexpectedly broad sector changes')
    require(sum(x != y for x, y in zip(before, after)) <= 6600, 'Unexpectedly broad byte changes')
    require(snapshot(before)['updater_files'] == snapshot(after)['updater_files'], 'Updater files changed')
    return facts, sectors


def acquire(run, port):
    require(port and Path(port).exists(), 'Explicit present serial port required')
    verify_pins()
    with zipfile.ZipFile(__import__('os').environ['R5_BOOTLOADER_ZIP']) as z:
        for name, expected in [('a7m4fb.py', MODULE_SHA), ('bin/fastboot.bin', PAYLOAD_SHA),
                               ('lib/pyserial.zip', SERIAL_SHA)]:
            require(digest(z.read('bootloader脚本/' + name)) == expected, 'Changed RAM-entry dependency: ' + name)
    run.mkdir(mode=0o700, exist_ok=False)
    state = dict(state='acquiring', started_utc=utc(), port=port, target='nflasha2',
                 user_reported_normal_shooting_and_not_updating=True,
                 persistent_write_command_sent=False, normal_reboot_acknowledged=False)
    save(run / 'report.json', state)
    source = (ROOT / 'tools/r5_settings_ram_boot.py').read_text()
    source = source.replace('ROOT = Path(__file__).resolve().parents[1]', 'ROOT = Path(' + repr(str(ROOT)) + ')')
    marker = "            library = run/'pyserial.zip'"
    require(source.count(marker) == 1, 'Unexpected RAM helper structure')
    source = source.replace(marker,
        "            if hashlib.sha256(source).hexdigest() != " + repr(MODULE_SHA) + ":\n"
        "                raise RuntimeError('Changed supplied entry source')\n"
        "            if hashlib.sha256(z.read('bootloader脚本/lib/pyserial.zip')).hexdigest() != " + repr(SERIAL_SHA) + ":\n"
        "                raise RuntimeError('Changed serial library')\n" + marker)
    helper = run / 'ram_boot_helper.py'
    helper.write_text(source)
    state['execution_hashes'] = {str(p): digest(p.read_bytes()) for p in
        [Path(__file__).resolve(), helper] + [HOST / n for n in
        ('configure_fastboot_usb', 'read_fastboot_usb', 'read_fastboot_usb_all')]}
    save(run / 'report.json', state)
    try:
        subprocess.run([sys.executable, '-B', str(helper), '--output', str(run / 'ram_boot'),
                        '--port', port], check=True, timeout=60)
        boot = json.loads((run / 'ram_boot/report.json').read_text())
        require(boot.get('usb_transport_verified') and boot.get('payload_sha256') == PAYLOAD_SHA,
                'RAM boot not verified')
        query = (run / 'ram_boot/usb_queries.txt').read_text()
        require(re.search(r'INFOnflasha2\s+0000c000 0000a000 fat', query), 'Unexpected partition geometry')
        out = execute(run, 'acquisition', ['getvar:max-download-size',
            'oem partition dump nflasha 0 0x80', 'upload:' + str(run / 'pre.sdm2.raw.bin'),
            'oem dumpbrom', 'upload:' + str(run / 'pre.ap_bootrom.bin'),
            'oem partition dump nflasha2', 'upload:' + str(run / 'pre.settings.logical.img'),
            RAW_DUMP, 'upload:' + str(run / 'pre.settings.raw.img')])
        require('REPLY OKAY' in out, 'Missing acquisition acknowledgment')
        require((run / 'pre.sdm2.raw.bin').read_bytes() == (BACKUP / 'sdm2_partition_table.raw.bin').read_bytes(),
                'Partition table differs from this body backup')
        require((run / 'pre.ap_bootrom.bin').read_bytes() == (BACKUP / 'ap_bootrom.raw.A.bin').read_bytes(),
                'Boot ROM differs from this body backup')
        before, raw = [(run / n).read_bytes() for n in ('pre.settings.logical.img', 'pre.settings.raw.img')]
        require(before[:512] == (run / 'ram_boot/nflasha2_first_sector.logical.bin').read_bytes(),
                'Independent first sector mismatch')
        raw_verify(raw, before)
        after, facts = build_image(before)
        audit_candidate(before, after)
        save(run / 'current_settings.json', snapshot(before))
        state.update(state='acquired_verified_maintenance_mode', before_sha256=digest(before),
                     before_raw_sha256=digest(raw), complete_raw_XTS_verified=True,
                     partition_geometry_verified=True, acquired_utc=utc())
        save(run / 'report.json', state)
        print(json.dumps(state, ensure_ascii=False, indent=2), flush=True)
    except Exception as exc:
        state.update(state='failed_before_write', error=repr(exc))
        bootfile = run / 'ram_boot/report.json'
        if bootfile.exists() and json.loads(bootfile.read_text()).get('usb_transport_verified'):
            try:
                reboot(run, 'acquisition_cleanup_reboot')
                state['normal_reboot_acknowledged'] = True
            except Exception as cleanup:
                state['cleanup_error'] = repr(cleanup)
        save(run / 'report.json', state)
        raise


def writer_source(sparse_hash):
    verify_pins()
    require(re.fullmatch('[0-9a-f]{64}', sparse_hash), 'Invalid sparse hash')
    source = (ROOT / 'analysis/r5_verifykey_skip_flash_20261014/partition1_usb.c').read_text()
    source = source.replace('nflasha1', 'nflasha2').replace('0x80 0xbf80', '0xc000 0xa000')
    old = 'ce51008ae51696004488b02ae291b23390edcea70870d0c60280ebeccd1a53ee'
    require(source.count(old) == 1, 'Unexpected hash guard')
    source = source.replace(old, sparse_hash)
    source = source.replace('static unsigned char staged[524288];',
                            'static int download_approved = 0;\nstatic unsigned char staged[524288];')
    marker = 'static int command(const char *arg) {\n'
    require(source.count(marker) == 1, 'Unexpected command entry')
    source = source.replace(marker, marker +
        '    if(!strcmp(arg,"flash:nflasha2") && !download_approved){fprintf(stderr,"No approved download in this process\\n");return -1;}\n'
        '    download_approved=0;\n')
    marker = 'if(!memcmp(b,"OKAY",4)){if(saved_path)'
    require(source.count(marker) == 1, 'Unexpected OKAY path')
    source = source.replace(marker,
        'if(!memcmp(b,"OKAY",4)){if(!strncmp(arg,"download:/",10)){if(downloading){fprintf(stderr,"Download OKAY before complete DATA transfer\\n");return -1;}download_approved=1;}if(saved_path)')
    require('nflasha1' not in source and '0x80 0xbf80' not in source, 'Old target remains')
    return source


def prepare(run):
    verify_pins()
    state = json.loads((run / 'report.json').read_text())
    require(state['state'] == 'acquired_verified_maintenance_mode', 'Need fresh live acquisition')
    before = (run / 'pre.settings.logical.img').read_bytes()
    require(digest(before) == state['before_sha256'], 'Acquisition changed')
    after, _ = build_image(before)
    facts, sectors = audit_candidate(before, after)
    out = run / 'prepared'
    out.mkdir(mode=0o700, exist_ok=False)
    forward, reverse = make_sparse(before, after), make_sparse(after, before)
    require(apply_sparse(after, reverse)[0] == before, 'Reverse sparse overlay mismatch')
    for name, data in [('candidate.logical.img', after), ('patch.sparse.img', forward), ('restore.sparse.img', reverse)]:
        (out / name).write_bytes(data)
    c, host = out / 'settings_usb.c', out / 'settings_usb'
    c.write_text(writer_source(digest(forward)))
    subprocess.run(['/usr/bin/clang', '-O2', str(c), '-o', str(host), '-framework', 'IOKit',
                    '-framework', 'CoreFoundation'], check=True)
    save(out / 'verification.json', dict(facts, changed_sectors=sectors,
         changed_bytes=sum(a != b for a, b in zip(before, after)),
         forward_and_reverse_sparse_verified=True, snapshot_before=snapshot(before), snapshot_after=snapshot(after)))
    state.update(state='prepared' if sectors else 'already_target_no_write_needed',
                 candidate_sha256=digest(after), changed_sectors=sectors,
                 prepared_hashes={str(p.relative_to(run)): digest(p.read_bytes()) for p in out.iterdir()},
                 execution_source_sha256=digest(Path(__file__).read_bytes()))
    save(run / 'report.json', state)
    print(json.dumps({k: state[k] for k in ('state', 'candidate_sha256', 'changed_sectors')}, indent=2), flush=True)


def write(run):
    verify_pins()
    state = json.loads((run / 'report.json').read_text())
    require(state['state'] == 'prepared' and not state['persistent_write_command_sent'], 'Not a fresh prepared attempt')
    require(digest(Path(__file__).read_bytes()) == state['execution_source_sha256'], 'Deployment code changed')
    for p, expected in state['prepared_hashes'].items():
        require(digest((run / p).read_bytes()) == expected, 'Prepared artifact changed: ' + p)
    for p, expected in state['execution_hashes'].items():
        require(digest(Path(p).read_bytes()) == expected, 'Acquisition tool changed: ' + p)
    host = run / 'prepared/settings_usb'
    try:
        execute(run, 'immediate_prewrite', ['oem partition dump nflasha2', 'upload:' + str(run / 'prewrite.settings.logical.img'),
            RAW_DUMP, 'upload:' + str(run / 'prewrite.settings.raw.img'),
            'oem partition dump nflasha 0 0x80', 'upload:' + str(run / 'prewrite.sdm2.raw.bin')], host)
        before, raw_before = [(run / n).read_bytes() for n in ('pre.settings.logical.img', 'pre.settings.raw.img')]
        require(digest(before) == state['before_sha256'] and digest(raw_before) == state['before_raw_sha256'], 'Saved input changed')
        for suffix in ('settings.logical.img', 'settings.raw.img', 'sdm2.raw.bin'):
            require((run / ('prewrite.' + suffix)).read_bytes() == (run / ('pre.' + suffix)).read_bytes(),
                    'Camera changed since acquisition: ' + suffix)
        candidate = (run / 'prepared/candidate.logical.img').read_bytes()
        _, sectors = audit_candidate(before, candidate)
        rebuilt, written = apply_sparse(before, (run / 'prepared/patch.sparse.img').read_bytes())
        require(rebuilt == candidate and written == sectors == state['changed_sectors'], 'Final sparse overlay mismatch')
        state.update(state='write_in_progress', persistent_write_command_sent=True, immediate_prewrite_verified=True)
        save(run / 'report.json', state)
        out = execute(run, 'flash', ['download:' + str(run / 'prepared/patch.sparse.img'), 'flash:nflasha2'], host)
        require(f'wrote {len(sectors)} sectors to nflasha2' in out, 'Unexpected sector write acknowledgment')
        state.update(state='reading_back', write_acknowledged=True)
        save(run / 'report.json', state)
        execute(run, 'readback', ['oem partition dump nflasha2', 'upload:' + str(run / 'post.settings.logical.img'),
            RAW_DUMP, 'upload:' + str(run / 'post.settings.raw.img'),
            'oem partition dump nflasha 0 0x80', 'upload:' + str(run / 'post.sdm2.raw.bin')], host)
        post, raw_post = [(run / n).read_bytes() for n in ('post.settings.logical.img', 'post.settings.raw.img')]
        require(post == candidate, 'Full logical readback mismatch')
        raw_verify(raw_post, post)
        require(changed_sectors(before, post) == changed_sectors(raw_before, raw_post) == sectors, 'Raw/logical changed sectors differ')
        require((run / 'post.sdm2.raw.bin').read_bytes() == (run / 'pre.sdm2.raw.bin').read_bytes(), 'Partition table changed')
        audit_candidate(before, post)
        save(run / 'readback_verification.json', dict(full_20MiB_logical_matches_candidate=True,
            independent_XTS_all_40960_sectors_verified=True, partition_table_unchanged=True,
            updater_files_unchanged=True, changed_sectors=sectors, logical_sha256=digest(post),
            raw_sha256=digest(raw_post), settings=snapshot(post)))
        state.update(state='write_and_readback_verified', complete_logical_readback_verified=True,
                     complete_independent_raw_XTS_verified=True, partition_table_unchanged=True)
        save(run / 'report.json', state)
        reboot(run)
        state.update(state='written_verified_reboot_acknowledged', normal_reboot_acknowledged=True, finished_utc=utc())
        save(run / 'report.json', state)
        print(json.dumps(state, ensure_ascii=False, indent=2), flush=True)
    except Exception as exc:
        state.update(state='write_needs_assessment' if state['persistent_write_command_sent'] else 'failed_before_write', error=repr(exc))
        if not state['persistent_write_command_sent']:
            try:
                reboot(run, 'prewrite_cleanup_reboot')
                state['normal_reboot_acknowledged'] = True
            except Exception as cleanup:
                state['cleanup_error'] = repr(cleanup)
        save(run / 'report.json', state)
        raise


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('acquire', 'prepare', 'write'))
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--port')
    args = parser.parse_args()
    run = args.run.resolve()
    if args.action == 'acquire':
        acquire(run, args.port)
    elif args.action == 'prepare':
        prepare(run)
    else:
        write(run)
