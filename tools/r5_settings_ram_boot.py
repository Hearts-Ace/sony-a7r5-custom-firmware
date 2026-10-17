#!/usr/bin/env python3
"""Bounded RAM entry, accepting a verified USB transport even if UART log is missed."""
import argparse
import datetime
import hashlib
import json
import subprocess
import sys
import time
import types
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT/'analysis/r5_live_system_20261014/host_tools'
PAYLOAD_SHA = '330ac322bd0e40a7bb4974f69a2667e7d59a25e59c1322339690f30a3ceadbdc'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port',required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--carrier-before-reset',action='store_true')
    a = ap.parse_args()
    run = a.output.resolve()
    run.mkdir(mode=0o700,exist_ok=False)
    report = dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  persistent_storage_write_commands_sent=False,
                  standard_flash_dispatch_enabled=True,ready_line_observed=False,
                  usb_transport_verified=False,
                  entry_sequence='carrier_before_reset' if a.carrier_before_reset else 'reset_before_carrier',
                  limitation='USB descriptors are payload constants; caller must verify real partition table and ROM.')
    uart = bytearray()
    dev = None
    try:
        with zipfile.ZipFile(__import__('os').environ['R5_BOOTLOADER_ZIP']) as z:
            source = z.read('bootloader脚本/a7m4fb.py')
            payload = z.read('bootloader脚本/bin/fastboot.bin')
            report['payload_sha256']=hashlib.sha256(payload).hexdigest()
            if report['payload_sha256'] != PAYLOAD_SHA:
                raise RuntimeError('Unexpected RAM payload')
            library = run/'pyserial.zip'
            library.write_bytes(z.read('bootloader脚本/lib/pyserial.zip'))
        sys.path.insert(0,str(library))
        m = types.ModuleType('supplied_reference')
        m.__file__=str(run/'a7m4fb.py')
        exec(compile(source,m.__file__,'exec'),m.__dict__)
        m.RP_VERSION=b'uart_boot 1'
        dev=m.Device(a.port,timeout=1)
        dev.ping()
        started=time.monotonic()
        if a.carrier_before_reset:
            dev.carrier(1)
            report['carrier_ack_seconds']=time.monotonic()-started
            dev.reset()
            report['reset_ack_seconds']=time.monotonic()-started
        else:
            dev.reset()
            report['reset_ack_seconds']=time.monotonic()-started
            dev.carrier(1)
            report['carrier_ack_seconds']=time.monotonic()-started
        time.sleep(m.TRANSMIT_START)
        for rec in m.boot_script(payload):
            dev.blob(rec)
            time.sleep(m.RECORD_GAP)
        dev.carrier(0)
        dev.baud(115200)
        dev.ser.timeout=.2
        deadline=time.monotonic()+15
        attempts=[]
        configured=False
        while time.monotonic()<deadline:
            # USB is checked immediately, without waiting for an optional UART line.
            r=subprocess.run([str(HOST/'configure_fastboot_usb')],capture_output=True,text=True,timeout=3)
            attempts.append(dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
            if r.returncode==0:
                configured=True
                print(r.stdout,flush=True)
                break
            pkt=dev.recv()
            if pkt and pkt[0]==m.RpEvt.UART:
                uart.extend(pkt[1])
                print(pkt[1].decode('utf-8','replace'),end='',flush=True)
            if r.returncode not in (2,):
                raise RuntimeError('USB configuration error: '+str(r.returncode))
        report['usb_enumeration_attempts']=attempts
        report['ready_line_observed']=b'[mira] fastboot ready' in uart
        if not configured:
            raise RuntimeError('No fastboot USB device within bounded entry window')
        commands=['getvar:version','oem partition','getvar:partition-size:nflasha2',
                  'oem partition dump nflasha2 0 1','upload:'+str(run/'nflasha2_first_sector.logical.bin')]
        with (run/'usb_queries.txt').open('x') as f:
            r=subprocess.run([str(HOST/'read_fastboot_usb'),*commands],stdout=f,stderr=subprocess.STDOUT,timeout=25)
        report['usb_queries_returncode']=r.returncode
        query=(run/'usb_queries.txt').read_text()
        print(query,flush=True)
        if r.returncode or 'REPLY OKAY0.5' not in query:
            raise RuntimeError('Fastboot query validation failed')
        report['usb_transport_verified']=True
    except Exception as exc:
        report['error']=repr(exc)
        print('RAM ENTRY ERROR',repr(exc),flush=True)
    finally:
        if dev:
            try:
                dev.ser.timeout=1
                dev.carrier(0)
                dev.baud(0)
            except Exception as exc:
                report['cleanup_error']=repr(exc)
            dev.close()
        (run/'uart.bin').write_bytes(uart)
        (run/'uart.txt').write_text(uart.decode('utf-8','replace'))
        (run/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    return 0 if report['usb_transport_verified'] else 1


if __name__=='__main__':
    sys.exit(main())
