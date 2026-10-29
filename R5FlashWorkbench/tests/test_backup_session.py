"""Synthetic MSC device exercises the actual session, Channel, capture and STOP.
Adapted from Liwenru88/a7r5-rea desktop wire fixtures, 290c79e, 2026-10-29.
No USB backend or host unmount operation reaches the operating system.
"""
from pathlib import Path
from collections import deque
from types import SimpleNamespace, ModuleType
from unittest.mock import patch
from contextlib import ExitStack, redirect_stdout
import hashlib, io, json, os, struct, sys, tempfile, unittest

ROOT=Path(__file__).resolve().parents[1]
ENGINE=Path(os.environ.get('R5_WORKBENCH_ENGINE',ROOT/'engine')).resolve()
sys.path[:0]=[str(ENGINE),str(ENGINE/'site'),str(ENGINE/'vendor/pmca_source')]
import common
from preparation import prepare_capture
from capture_operation import Operation
from transport import HEADER
from system_dump import session

class BackupSession(unittest.TestCase):
    def test_complete_backup_and_lost_cleanup_receipt_control_stop(self):
        for fault in (None,'cleanup-failed','cleanup-lost'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as tmp,ExitStack() as mocks,redirect_stdout(io.StringIO()):
                # Exercise protocol ordering and file contents without measuring SSD flush latency.
                # Production retains all fsync/F_FULLFSYNC calls.
                mocks.enter_context(patch.object(os,'fsync',lambda fd:None))
                job=Path(tmp).resolve()
                baseline=dict(kind='ordinary',model='ILCE-7RM5',location_id=0x14100000,media=[[True,100000]],drivers=['IOUSBMassStorageDriver'])
                package,_=prepare_capture(job,'8'*32,baseline)
                cfg=common.load(package/'config.json')
                cfg.update(version_sha256=hashlib.sha256(b'fixture-version').hexdigest(),loader_sha256=hashlib.sha256(b'L'*233416).hexdigest())
                (package/'config.json').write_text(json.dumps(cfg))
                op=Operation(package,sleep=lambda seconds:None);op.output=job/'session'
                image=bytes(range(256))*(25100288//256);digest=hashlib.sha256(image).hexdigest()
                output=(cfg['expected_output_begin']+f'A7R5_CAPTURE_COMPLETE {digest} bytes=25100288 twice=1 chunks=1532 chunk_bytes=16384\n'+cfg['expected_output_end']).encode()
                receipt=f'A7R5_CAPTURE_CLEANUP {op.run} sha256={digest} deleted=1532 bytes=25100288 directory_removed=1\n'.encode()
                class Wire:
                    def __init__(self):self.queue=deque();self.files={};self.triggers=0;self.puts=[];self.sequences=[];self.selected=None
                    def contents(self,path):
                        if path=='/version.txt':return b'fixture-version'
                        if path=='/usr/lib/libJiritsu.so':return b'L'*233416
                        if path=='/etc/ld.so.preload':return b'\n'*512
                        if self.triggers:
                            if path==op.prefix+'.state':return f'A7R5-JIT-1 {op.run} DONE 0 uid=0 euid=0 bytes={len(output)} disarmed=1 children=0\n'.encode()
                            if path==op.prefix+'.output':return output
                            if path in dict(op.parts):
                                index=int(path.rsplit('-',1)[1]);return image[index*16384:(index+1)*16384]
                        if self.triggers==2:
                            if path==op.cleanup_prefix+'.state':
                                if fault=='cleanup-lost':raise TimeoutError('Synthetic lost receipt')
                                status='FAILED 71' if fault=='cleanup-failed' else 'DONE 0'
                                return f'A7R5-JIT-1 {op.run} {status} uid=0 euid=0 bytes={len(receipt)} disarmed=1 children=0\n'.encode()
                            if path==op.cleanup_prefix+'.output':return receipt
                        return self.files.get(path)
                    def write(self,packet):
                        assert not self.queue;op.guard_packet(packet)
                        size,function,seq,*meta=HEADER.unpack_from(packet);self.sequences.append(seq)
                        body=packet[HEADER.size:];assert size==len(body) and function==64 and not any(meta)
                        group,command=struct.unpack_from('<HH',body);assert group==0x1001
                        code=0;data=b''
                        if command==15:self.selected=body[5:-1].decode().replace('/tmp/jiritsu/../..','',1)
                        elif command==16:
                            self.puts.append(self.selected);self.files[self.selected]=body[7:]
                            if self.selected=='/tmp/jiritsu/libJit.so':self.triggers+=1
                        elif command==17:
                            data=self.contents(self.selected)
                            if data is None:code=0x10000006;data=b''
                        else:raise AssertionError('Unexpected protocol command')
                        raw=struct.pack('<I',code)+data;self.queue.append(HEADER.pack(len(raw),64,seq,0,0,0,0))
                        for offset in range(0,len(raw),32768):
                            block=raw[offset:offset+32768];self.queue.append(block)
                            if len(block)%512==0:self.queue.append(b'')
                        return len(packet)
                    def read(self,n):
                        block=self.queue.popleft();take=n if n==12 else min(n,503)
                        if block[take:]:self.queue.appendleft(block[take:])
                        return block[:take]
                wire=Wire();controls=[];auth=[0]
                class Interface(list):pass
                class USB:
                    idVendor=0x054c;bus=0x14;port_numbers=[1];iProduct=1
                    def __init__(self,pid):self.idProduct=pid
                    def get_active_configuration(self):
                        row=op.config['interfaces']['interface-1.json' if self.idProduct==0x0e0a else 'interface-2.json']
                        interface=Interface([SimpleNamespace(bEndpointAddress=e['address'],bmAttributes=e['attributes'],wMaxPacketSize=e['max_packet'],bInterval=e['interval']) for e in row['endpoints']])
                        for attr,key in [('bInterfaceNumber','number'),('bAlternateSetting','alternate'),('bInterfaceClass','interface_class'),('bInterfaceSubClass','subclass'),('bInterfaceProtocol','protocol')]:setattr(interface,attr,row[key])
                        return {(0,0):interface}
                    def write(self,ep,data,timeout):assert ep==2;return wire.write(data)
                    def read(self,ep,n,timeout):assert ep==129 and n<=8192;return wire.read(n)
                    def ctrl_transfer(self,*args,**kwargs):controls.append(args)
                ordinary=USB(0x0e0a);service=USB(0x0336)
                class Auth:
                    def __init__(self,driver):self.driver=driver
                    def start(self):self.driver.vendorRequestOut(*session.START)
                    def authenticate(self):auth[0]+=1
                sony=ModuleType('pmca.usb.sony');sony.SonySenserAuthDevice=Auth
                import usb.core,usb.util,usb.backend.libusb1
                mocks.enter_context(patch.dict(sys.modules,{'pmca.usb.sony':sony}))
                mocks.enter_context(patch.object(usb.core,'find',lambda **k:[ordinary if auth[0]==0 else service]))
                mocks.enter_context(patch.object(usb.backend.libusb1,'get_backend',lambda **k:object()))
                mocks.enter_context(patch.object(usb.util,'get_string',lambda *a:'ILCE-7RM5'))
                mocks.enter_context(patch.object(usb.util,'dispose_resources',lambda *a:None))
                mocks.enter_context(patch.object(usb.util,'release_interface',lambda *a:None))
                mocks.enter_context(patch.object(session,'claim_interface',lambda *a,**k:False))
                mocks.enter_context(patch.object(session,'unmount_camera',lambda *a:None))
                report=session.run_session(op.output,'libusb',_operation=op)
                self.assertTrue(report.get('capture_verified'),report.get('failure'));self.assertTrue(report['backup_persisted'])
                self.assertEqual((op.output/'partition1.logical.bin').read_bytes(),image)
                self.assertEqual(wire.triggers,2);self.assertEqual(len(wire.puts),4)
                self.assertEqual(wire.sequences,list(range(1,len(wire.sequences)+1)))
                self.assertEqual(sum(c[1:4]==session.STOP for c in controls),int(fault is None))
                self.assertEqual(report['service_stop_attempts'],int(fault is None))
                self.assertEqual(op.safe_to_stop,fault is None)

if __name__=='__main__':unittest.main(verbosity=2)
