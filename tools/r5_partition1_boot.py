#!/usr/bin/env python3
"""RAM boot with original flash-enabled payload; initial queries remain read-only."""
if __name__ == '__main__':
    raise SystemExit('Historical reference/helper only; standalone execution is disabled. See PUBLICATION.md.')

import argparse,datetime,hashlib,json,sys,time,types,zipfile,subprocess
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
root=Path(__file__).resolve().parents[1];run=args.output.resolve();run.mkdir(exist_ok=False)
report={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'persistent_storage_write_commands_sent':False,'limitations':['M4-specific BootROM parameters and initializers; compatibility is tested, not assumed.','USB descriptors and getvar product are compiled M4 constants, not live R5 identity.']}
z=zipfile.ZipFile(__import__('os').environ['R5_BOOTLOADER_ZIP']);s=z.read('bootloader脚本/a7m4fb.py');b=z.read('bootloader脚本/bin/fastboot.bin')
assert hashlib.sha256(b).hexdigest()=='330ac322bd0e40a7bb4974f69a2667e7d59a25e59c1322339690f30a3ceadbdc'
assert b.count(b'flash:\0')==1
report['standard_flash_dispatch_enabled']=True;report['payload_sha256']=hashlib.sha256(b).hexdigest()
lib=run/'pyserial.zip';lib.write_bytes(z.read('bootloader脚本/lib/pyserial.zip'));sys.path.insert(0,str(lib))
m=types.ModuleType('m4_supplied_reference');m.__file__=str(run/'a7m4fb.py');exec(compile(s,m.__file__,'exec'),m.__dict__)
m.RP_VERSION=b'uart_boot 1';dev=None;uart=bytearray()
try:
    dev=m.Device('/dev/cu.usbmodem101',timeout=1);dev.ping();dev.reset();dev.carrier(1);time.sleep(m.TRANSMIT_START)
    for rec in m.boot_script(b):dev.blob(rec);time.sleep(m.RECORD_GAP)
    dev.carrier(0);dev.baud(115200)
    end=time.monotonic()+8
    while time.monotonic()<end:
        pkt=dev.recv()
        if pkt and pkt[0]==m.RpEvt.UART:
            uart.extend(pkt[1]);print(pkt[1].decode('utf-8','replace'),end='',flush=True)
            if b'[mira] fastboot ready' in uart:break
    report['ready_line_observed']=b'[mira] fastboot ready' in uart
    if not report['ready_line_observed']:raise RuntimeError('No ready line')
    host=root/'analysis/r5_live_system_20261014/host_tools'
    enumeration_end=time.monotonic()+10
    while True:
        r=subprocess.run([str(host/'configure_fastboot_usb')],capture_output=True,text=True,timeout=8)
        if r.returncode!=2 or time.monotonic()>=enumeration_end:break
        time.sleep(.25)
    report['usb_config']={'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr};print(r.stdout,flush=True)
    if r.returncode:raise RuntimeError('USB configuration failed')
    cmds=['getvar:version','oem partition','getvar:partition-size:nflasha1','oem partition dump nflasha1 0 1','upload:'+str(run/'nflasha1_first_sector.logical.bin'),'oem partition dump nflasha2 0 1','upload:'+str(run/'nflasha2_first_sector.logical.bin')]
    with (run/'usb_queries.txt').open('w') as out:
        r=subprocess.run([str(host/'read_fastboot_usb'),*cmds],stdout=out,stderr=subprocess.STDOUT,timeout=25)
    report['usb_queries_returncode']=r.returncode;print((run/'usb_queries.txt').read_text(),flush=True)
except Exception as e:
    report['error']=repr(e);print('PROBE ERROR',repr(e),flush=True)
finally:
    if dev:
        try:dev.baud(0)
        except Exception as e:report['cleanup_error']=repr(e)
        dev.close()
    (run/'uart.bin').write_bytes(uart);(run/'uart.txt').write_text(uart.decode('utf-8','replace'))
    (run/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
