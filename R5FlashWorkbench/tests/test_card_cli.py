"""Offline BIN/card and machine-readable CLI checks; never use USB or a real card."""
from pathlib import Path
from unittest.mock import patch
import contextlib, hashlib, io, json, os, subprocess, sys, tempfile, unittest

ROOT=Path(__file__).resolve().parents[1]
ENGINE=Path(os.environ.get('R5_WORKBENCH_ENGINE',ROOT/'engine')).resolve()
sys.path.insert(0,str(ENGINE))
import card

class CardTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.dest=self.root/'中文 目标';self.dest.mkdir()
        self.job=self.root/'job';self.job.mkdir()
        env=patch.dict(os.environ,R5_WORKBENCH_STATE_DIR=str(self.root/'state'))
        env.start();self.addCleanup(env.stop)

    def verifier(self,path):
        raw=path.read_bytes()
        if raw!=b'test firmware':raise ValueError('bad firmware')
        return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

    def prepare(self,**values):
        with contextlib.redirect_stdout(io.StringIO()):
            return card.prepare(dict(destination=str(self.dest),**values),self.job,self.verifier)

    def test_bundled_identity(self):
        value=card.filters()
        self.assertEqual(value['count'],12);self.assertEqual(value['training_status'],'done')
        self.assertEqual(value['sha256'],'19e020fa48c79643aaf9526e9c720d38ec5a92c3df11d0852b0a93a25ee880b6')
        self.assertFalse(value['includes_training_workbench'])

    def test_plan_has_no_destination_side_effect(self):
        value=card.plan(dict(destination=str(self.dest)),self.verifier)
        self.assertEqual(list(self.dest.iterdir()),[]);self.assertEqual(value['files'][0]['action'],'create')

    def test_copy_and_idempotence(self):
        first=self.prepare();target=self.dest/'R5NATIVE.BIN';stamp=target.stat().st_mtime_ns
        self.assertEqual(first['files'][0]['action'],'create');self.assertFalse(first['camera_upgrade_complete'])
        self.job=self.root/'job2';self.job.mkdir();second=self.prepare()
        self.assertEqual(second['files'][0]['action'],'unchanged');self.assertEqual(target.stat().st_mtime_ns,stamp)

    def test_old_bin_preserved(self):
        (self.dest/'R5NATIVE.BIN').write_bytes(b'old bin')
        result=self.prepare();row=result['files'][0]
        self.assertEqual(Path(row['backup']).read_bytes(),b'old bin')
        self.assertEqual(row['action'],'backup_and_replace');self.assertTrue(row['full_readback_verified'])

    def test_joint_prepare(self):
        firmware=self.root/'input.dat';firmware.write_bytes(b'test firmware')
        result=self.prepare(firmware=str(firmware));self.assertEqual(len(result['files']),2)
        self.assertEqual((self.dest/'BODYDATA.DAT').read_bytes(),b'test firmware')
        self.assertEqual(json.loads((self.job/'prepared-BODYDATA.DAT.json').read_text())['action'],'create')

    def test_bad_firmware_changes_nothing(self):
        firmware=self.root/'bad.dat';firmware.write_bytes(b'bad')
        (self.dest/'R5NATIVE.BIN').write_bytes(b'old')
        with self.assertRaises(ValueError):self.prepare(firmware=str(firmware))
        self.assertEqual((self.dest/'R5NATIVE.BIN').read_bytes(),b'old')
        self.assertEqual(len(list(self.dest.iterdir())),1)

    def test_target_symlink_rejected(self):
        outside=self.root/'outside';outside.write_bytes(b'keep');(self.dest/'R5NATIVE.BIN').symlink_to(outside)
        with self.assertRaises(ValueError):self.prepare()
        self.assertEqual(outside.read_bytes(),b'keep')

    def test_backup_symlink_rejected(self):
        (self.dest/'.R5Workbench-backups').symlink_to(self.root)
        with self.assertRaises(ValueError):self.prepare()
        self.assertFalse((self.dest/'R5NATIVE.BIN').exists())

    def test_staged_corruption_keeps_old(self):
        (self.dest/'R5NATIVE.BIN').write_bytes(b'old');realsha=card.sha
        def digest(path):return 'wrong' if path.parent.name.startswith('.r5wb-stage-') else realsha(path)
        with patch.object(card,'sha',side_effect=digest),self.assertRaises(ValueError):self.prepare()
        self.assertEqual((self.dest/'R5NATIVE.BIN').read_bytes(),b'old')
        self.assertEqual(len(list(self.dest.iterdir())),1)

    def test_concurrent_target_change_kept(self):
        realsha=card.sha
        def digest(path):
            value=realsha(path)
            if path.parent.name.startswith('.r5wb-stage-'):(self.dest/'R5NATIVE.BIN').write_bytes(b'external change')
            return value
        with patch.object(card,'sha',side_effect=digest),self.assertRaises(ValueError):self.prepare()
        self.assertEqual((self.dest/'R5NATIVE.BIN').read_bytes(),b'external change')

    def cli(self,*args):
        process=subprocess.run([sys.executable,'-I','-B',str(ENGINE/'assistant.py'),*args],capture_output=True,text=True)
        return process,json.loads(process.stdout)

    def test_cli_discovery_status_json(self):
        process,result=self.cli('describe');self.assertEqual(process.returncode,0)
        self.assertFalse(result['includes_filter_training_workbench']);self.assertEqual(process.stderr,'')
        process,result=self.cli('status');self.assertEqual(process.returncode,0);self.assertFalse(result['USB_enumerated'])

    def test_cli_plan_prepare_receipt_and_error(self):
        process,result=self.cli('plan','--destination',str(self.dest));self.assertEqual(process.returncode,0)
        self.assertEqual(list(self.dest.iterdir()),[])
        process,result=self.cli('prepare','--destination',str(self.dest));self.assertEqual(process.returncode,0)
        self.assertIn('progress',process.stderr);self.assertNotIn('progress',result)
        receipt=Path(result['job'])/'result.json'
        process,saved=self.cli('result',str(receipt));self.assertEqual(process.returncode,0);self.assertTrue(saved['ok'])
        process,status=self.cli('status');self.assertGreaterEqual(len(status['tasks']),2)
        process,error=self.cli('prepare','--destination',str(self.root/'missing'))
        self.assertEqual(process.returncode,1);self.assertFalse(error['ok']);self.assertFalse(error['automatic_retry'])

if __name__=='__main__':unittest.main()
