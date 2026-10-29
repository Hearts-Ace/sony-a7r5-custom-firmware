"""Offline integration tests. All camera discovery and authorisation are blocked."""
from pathlib import Path
from collections import deque
from types import SimpleNamespace
from unittest.mock import patch
import base64, hashlib, io, json, os, socket, struct, sys, tempfile, unittest

ROOT=Path(__file__).resolve().parents[1]
ENGINE=Path(os.environ.get('R5_WORKBENCH_ENGINE',ROOT/'engine')).resolve()
sys.path[:0]=[str(ENGINE),str(ENGINE/'site'),str(ENGINE/'vendor/pmca_source')]
import bootstrap, common, device, host
from preparation import prepare_update
from transport import Channel, HEADER, READ, FileResultError
from trust_operation import Operation, validate_journal

BASELINE=dict(kind='ordinary',model='ILCE-7RM5',location_id=0x14100000,media=[[True,100000]],drivers=['IOUSBMassStorageDriver'])

class OfflineTest(unittest.TestCase):
    def setUp(self):
        import usb.core, usb.backend.libusb1
        self.temp=tempfile.TemporaryDirectory();self.out=Path(self.temp.name).resolve()
        self.addCleanup(self.temp.cleanup)
        for obj,name in [(usb.core,'find'),(usb.backend.libusb1,'get_backend'),(socket.socket,'connect')]:
            guard=patch.object(obj,name,side_effect=AssertionError('No camera/network access in tests'))
            guard.start();self.addCleanup(guard.stop)

    def test_import_and_packaged_selfcheck_do_not_enumerate_usb(self):
        if not (ENGINE/'resources.lock.json').exists():self.skipTest('Run against packaged engine')
        value=bootstrap.selfcheck()
        self.assertTrue(value['ok']);self.assertFalse(value['USB_enumerated']);self.assertFalse(value['camera_IO'])

    def test_payloads_have_native_initializer_and_no_shared_dependencies(self):
        from elftools.elf.elffile import ELFFile
        manifest=common.load(ENGINE/'templates.json')
        for name in manifest['files']:
            raw=common.render_template(name,'a'*32)
            elf=ELFFile(io.BytesIO(raw));self.assertEqual(elf['e_machine'],'EM_AARCH64');self.assertEqual(elf['e_type'],'ET_DYN')
            tags={t.entry.d_tag:t for t in elf.get_section_by_name('.dynamic').iter_tags()}
            self.assertNotIn('DT_NEEDED',tags);self.assertIn('DT_INIT',tags)
            symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
            self.assertEqual(tags['DT_INIT'].entry.d_val,symbols['_init']);self.assertGreater(symbols['_init'],0)
            self.assertNotIn(manifest['run_marker'].encode(),raw)
            self.assertNotIn(b'sectors=258',raw)

    def source(self):
        value=os.environ.get('R5_TRUST_ORIGINAL')
        if not value:self.skipTest('Set R5_TRUST_ORIGINAL to exact original logical image')
        source=Path(value).resolve();self.assertEqual(common.sha(source),common.SOURCE_SHA);return source

    def record(self,**overrides):
        record=dict(kind='backup',task_complete=True,device_IO=True,simulation=False,backup_sha256=common.SOURCE_SHA,
            backup_file=str(self.source()),preload_name='blank-512')
        record.update(overrides);path=self.out/'backup.json';path.write_text(json.dumps(record));return path

    def test_own_26_sector_recipe_reconstructs_exact_target(self):
        old=self.source().read_bytes();new=bytearray(old);rows=common.load(ENGINE/'trust-sectors.json')['rows']
        self.assertEqual(len(rows),26)
        for row in rows:
            at=row['offset'];before=base64.b64decode(row['before']);after=base64.b64decode(row['after'])
            self.assertEqual(old[at:at+512],before);new[at:at+512]=after
        self.assertEqual(hashlib.sha256(new).hexdigest(),common.TARGET_SHA)

    def test_simulated_or_unfinished_backups_refused_before_upload(self):
        for values in [dict(simulation=True),dict(task_complete=False),dict(device_IO=False),dict(backup_sha256='0'*64)]:
            with self.subTest(values=values):
                record=self.record(**values)
                with self.assertRaises(ValueError):prepare_update(self.out,'b'*32,BASELINE,record)
                self.assertFalse((self.out/'package').exists())

    def test_trust_native_and_full_readback_gate(self):
        for fault in [None,'open','journal','readback','counter','version','force']:
            with self.subTest(fault=fault),tempfile.TemporaryDirectory(dir=self.out) as tmp:
                job=Path(tmp);record=self.record()
                package,_=prepare_update(job,'b'*32,BASELINE,record)
                cfg=common.load(package/'config.json');cfg.update(version_sha256=hashlib.sha256(b'v').hexdigest(),loader_sha256=hashlib.sha256(b'l').hexdigest())
                if fault=='force':
                    cfg['force_install']=True;(package/'config.json').write_text(json.dumps(cfg))
                    with self.assertRaises(ValueError):Operation(package)
                    continue
                (package/'config.json').write_text(json.dumps(cfg))
                plan=common.load(ENGINE/'write-plan.json');count=26
                terminal=(cfg['expected_output_begin']+'A7R5_TRUST_COMPLETE '+cfg['candidate_sha256']+
                    ' sectors=26 bytes=13312 reopened=1\n'+cfg['expected_output_end']).encode()
                phases=[('PREIMAGE_VERIFIED',0,-1,0)]
                for i,row in enumerate(plan['rows']):
                    phases += [('WRITE_BEGIN',i,row['offset'],0),('WRITE_RETURNED',i+1,row['offset'],0)]
                    if i==25 or row['phase']!=plan['rows'][i+1]['phase']:phases.append(('PHASE_SYNC_RETURNED',i+1,row['offset'],0))
                phases += [(name,258 if fault=='counter' else 26,-1,0) for name in ('FULL_LOGICAL_READBACK_MATCH','REOPENED_FULL_CAPTURE_MATCH','COMPLETED')]
                journal=''.join(f'A7R5_TRUST {"b"*32} {name} completed={n} offset={at} code={code}\n' for name,n,at,code in phases).encode()
                puts=[]
                class Files:
                    def __init__(self,driver,op,log):self.op=op
                    def put(self,path,data):
                        puts.append(path)
                        if fault=='open' and path=='/tmp/jiritsu/libJit.so':raise FileResultError(0x10000008,action='write',path=path)
                    def read(self,path,limit):
                        op=self.op
                        if path=='/version.txt':return b'unknown' if fault=='version' else b'v'
                        if path=='/usr/lib/libJiritsu.so':return b'l'
                        if path=='/etc/ld.so.preload':return b'\n'*512
                        if path==op.ticket_path and path in puts:return op.ticket
                        if '/tmp/jiritsu/libJit.so' in puts:
                            if path==op.prefix+'.state':return f'A7R5-JIT-1 {op.run} DONE 0 uid=0 euid=0 bytes={len(terminal)} disarmed=1 children=0\n'.encode()
                            if path==op.prefix+'.output':return terminal
                            if path==cfg['journal_path']:return journal[:-1] if fault=='journal' else journal
                            if path==cfg['readback_path']:return b'!'+op.expected_candidate[1:] if fault=='readback' else op.expected_candidate
                        raise FileResultError(0x10000006,action='read',path=path)
                op=Operation(package,channel_factory=Files,sleep=lambda seconds:None);dest=job/'session';dest.mkdir();report={}
                if fault is None:
                    op(None,dest,lambda *a,**k:None,report)
                    self.assertTrue(op.safe_to_stop);self.assertTrue(report['complete_partition_readback_verified']);self.assertEqual(report['patch_sectors'],26)
                else:
                    with self.assertRaises((ValueError,RuntimeError)):op(None,dest,lambda *a,**k:None,report)
                    self.assertFalse(op.safe_to_stop)
                self.assertLessEqual(puts.count('/tmp/jiritsu/libJit.so'),1)

    def test_missing_readback_blocks_completion_and_recovery_observation(self):
        for verified in (False,True):
            with tempfile.TemporaryDirectory(dir=self.out) as tmp:
                observations=[]
                report=dict(protocol_gate_passed=True,preload_unchanged=True,fixed_writes_attempted=2,trigger_attempts=1,
                    service_stop_attempts=1,service_stop_result='returned',complete_partition_readback_verified=verified,patch_sectors=26)
                fake=SimpleNamespace(__name__='simulation',run_session=lambda *a,**k:report)
                fake_host=SimpleNamespace(snapshot=lambda *a:BASELINE,observe=lambda *a:observations.append(1) or dict(recovered=True))
                with patch.object(device,'prepare_update',return_value=(None,SimpleNamespace())):
                    result=device.run(dict(kind='update',run_id='c'*32),Path(tmp),session_module=fake,host_module=fake_host)
                self.assertIs(result['task_complete'],verified);self.assertEqual(len(observations),int(verified));self.assertTrue(result['simulation'])

    def test_absent_msc_never_creates_attempt_lock(self):
        with self.assertRaises(ValueError):device.run(dict(kind='backup',run_id='c'*32),self.out,
            session_module=SimpleNamespace(),host_module=SimpleNamespace(snapshot=lambda *a:dict(kind='absent')))
        self.assertFalse((self.out/'ATTEMPT_LOCK').exists())

    def test_wrong_sequence_poisons_transport_and_prevents_resend(self):
        queue=deque([HEADER.pack(4,64,2,0,0,0,0)]);writes=[]
        channel=Channel(SimpleNamespace(read=lambda n:queue.popleft(),write=lambda b:writes.append(b) or len(b)),
            SimpleNamespace(guard_packet=lambda b:None),lambda *a,**k:None)
        with self.assertRaises(ValueError):channel.exchange(READ,4)
        with self.assertRaises(PermissionError):channel.exchange(READ,4)
        self.assertEqual(len(writes),1)

    def test_incorrect_firmware_refused_and_existing_destination_preserved(self):
        source=self.out/'wrong.DAT';source.write_bytes(b'not firmware')
        with self.assertRaises(ValueError):bootstrap.verify_dat(source)
        destination=self.out/'card';destination.mkdir();existing=destination/'BODYDATA.DAT';existing.write_bytes(b'original')
        with patch.object(bootstrap,'verify_dat',return_value=dict(ok=True)):
            with self.assertRaises(ValueError):bootstrap.export_dat(dict(firmware=str(source),destination=str(destination)),self.out)
        self.assertEqual(existing.read_bytes(),b'original')

if __name__=='__main__':unittest.main(verbosity=2)
