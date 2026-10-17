#!/usr/bin/env python3
"""One bounded session: fresh acquisition, read-only WDT checks, prepare, write.

No watchdog writes or altered payload. An unrecognized or active watchdog state
aborts before any storage write. The original body files stay in the run folder.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time

import deploy_r5_m4strict_personal as d


def quiescent_watchdog(output):
    counters = re.findall(r'INFOcounters @200026fc:\s*((?:[0-9a-fA-F]{2}\s*){4})', output)
    reloads = re.findall(r'INFOreloads  @2000003c:\s*((?:[0-9a-fA-F]{2}\s*){3})', output)
    d.require(len(counters) == len(reloads) == 1, 'Unrecognized watchdog status')
    c, r = bytes.fromhex(counters[0]), bytes.fromhex(reloads[0])
    # darwin.c documents FF as disabled, and persistent 00 as a stopped tick:
    # a running tick turns 00 into FF within one 100 ms period. A single 00
    # sample is provisional; run_session requires repeated matching samples.
    d.require(c in (b'\xff' * 4, b'\x00' * 4), 'Active/unknown watchdog counters; refusing persistent write')
    d.require(all(x in (0, 10) for x in r), 'Unrecognized watchdog reload state')
    return {'counters_hex': c.hex(), 'reloads_hex': r.hex(),
            'interpretation': 'disabled' if c == b'\xff' * 4 else 'zero_requires_stability_check'}


def run_session(run, port):
    d.acquire(run, port)
    try:
        # This host only accepts read commands and normal reboot. Add the single
        # read-only oem darwin query, not peek/poke or any watchdog write command.
        source = (d.HOST / 'read_fastboot_usb_all.c').read_text()
        marker = 'return !strncmp(s,"getvar:",7)'
        d.require(source.count(marker) == 1 and 'flash:' not in source, 'Changed read-only host')
        source = source.replace(marker, 'return !strcmp(s,"oem darwin") || !strncmp(s,"getvar:",7)')
        c, host = run / 'watchdog_read_usb.c', run / 'watchdog_read_usb'
        c.write_text(source)
        subprocess.run(['/usr/bin/clang', '-O2', str(c), '-o', str(host), '-framework', 'IOKit',
                        '-framework', 'CoreFoundation'], check=True)
        checks = []
        for index in range(3):
            if index:
                time.sleep(5)
            output = d.execute(run, f'watchdog_read_{index}', ['getvar:version', 'oem darwin'], host)
            d.require('REPLY OKAY0.5' in output, 'Fastboot is not responding correctly')
            value = quiescent_watchdog(output)
            if checks:
                d.require(value['counters_hex'] == checks[0]['counters_hex'] and
                          value['reloads_hex'] == checks[0]['reloads_hex'], 'Watchdog state changed during observation')
            checks.append(dict(utc=d.utc(), **value))
            d.save(run / 'watchdog_read_checks.json', {'checks': checks, 'watchdog_write_commands_sent': False})
        d.prepare(run)
        state = json.loads((run / 'report.json').read_text())
        if state['state'] == 'already_target_no_write_needed':
            d.reboot(run)
            state.update(normal_reboot_acknowledged=True, finished_utc=d.utc())
            d.save(run / 'report.json', state)
            return
        # Check again immediately before the final partition reread and flash.
        output = d.execute(run, 'watchdog_read_final', ['getvar:version', 'oem darwin'], host)
        value = quiescent_watchdog(output)
        d.require(value['counters_hex'] == checks[0]['counters_hex'] and
                  value['reloads_hex'] == checks[0]['reloads_hex'], 'Watchdog changed before write')
        d.write(run)
    except Exception as exc:
        state = json.loads((run / 'report.json').read_text())
        if not state['persistent_write_command_sent'] and not state.get('normal_reboot_acknowledged'):
            try:
                d.reboot(run, 'session_cleanup_reboot')
                state['normal_reboot_acknowledged'] = True
            except Exception as cleanup:
                state['session_cleanup_error'] = repr(cleanup)
        state['session_error'] = repr(exc)
        if not state['persistent_write_command_sent']:
            state['state'] = 'failed_before_write'
        d.save(run / 'report.json', state)
        raise


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--port', required=True)
    args = parser.parse_args()
    run_session(args.run.resolve(), args.port)
