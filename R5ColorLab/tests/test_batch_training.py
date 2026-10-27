import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import server
import batch_training as batch

class BatchTests(unittest.TestCase):
    def test_three_fitters_run_concurrently(self):
        import threading
        barrier=threading.Barrier(3,timeout=5)
        with tempfile.TemporaryDirectory() as root:
            items=[dict(id=str(i)*32,name=str(i),filename=str(i)+'.tif',options={}) for i in range(3)]
            state=dict(id='a'*32,status='queued',jobs=items,concurrency=3)
            jobs={item['id']:dict(status='queued',phase='waiting') for item in items}
            def work(identifier,options):
                barrier.wait();jobs[identifier].update(status='error',error='test stop')
            with patch.object(server,'JOBS',jobs),patch.object(server,'work',side_effect=work):
                batch.run(state,Path(root),server)
            self.assertTrue(all(j['status']=='error' for j in jobs.values()))
            self.assertEqual(state['status'],'error')
            self.assertFalse((Path(root)/'R5NATIVE.BIN').exists())

    def test_names(self):
        self.assertEqual(batch.folder_names([{'filename':'Classic.Chrome.JPG'},{'filename':'CC.tiff'}]),['Classic.Chrome','CC'])
        for files in ([],[{'filename':'CC.jpg'}]*13,[{'filename':'CC.jpg'},{'filename':'cc.tif'}],[{'filename':'../CC.jpg'}],[{'filename':'富'*8+'.jpg'}]):
            with self.assertRaises(ValueError):batch.folder_names(files)

    def test_whole_batch_validates_before_queue(self):
        with patch.object(server,'validate_fit',side_effect=[{},ValueError('bad image')]),patch.object(server.POOL,'submit') as queue:
            with self.assertRaisesRegex(ValueError,'bad image'):
                batch.submit(dict(files=[dict(filename='A.jpg',target_id='a'*32),dict(filename='B.jpg',target_id='b'*32)]),server)
            queue.assert_not_called()

    def test_batch_endpoint_and_fixed_names(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as root:
            with patch.object(server.core,'HERE',Path(root)),patch.object(server,'JOBS',{}),patch.object(server,'validate_fit') as validate,patch.object(server.POOL,'submit'):
                result=batch.submit(dict(files=[dict(filename='AS.jpg',target_id='a'*32)],options=dict(evaluations=80,post_gray_refinement=True)),server)
                options=validate.call_args.args[0]
                self.assertEqual((options['short_name'],options['full_name']),('AS','AS'))
                self.assertEqual(options['gamma_endpoint128'],131071)
                self.assertTrue(options['compression_training'])
                self.assertFalse(options['post_gray_refinement'])
                self.assertFalse(options['white_balance'])
                self.assertTrue((Path(root)/'batches'/result['id']/'batch.json').exists())

    def test_batch_custom_full_name_keeps_filename_short_name(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(server.core,'HERE',Path(root)),patch.object(server,'JOBS',{}),patch.object(server,'validate_fit') as validate,patch.object(server.POOL,'submit'):
                batch.submit(dict(files=[dict(filename='NC.tif',target_id='a'*32,full_name='CLASSIC Neg.')],options={}),server)
                options=validate.call_args.args[0]
                self.assertEqual(options['short_name'],'NC')
                self.assertEqual(options['full_name'],'CLASSIC Neg.')

    def test_failure_never_exports_partial_bin(self):
        with tempfile.TemporaryDirectory() as root:
            state=dict(id='a'*32,status='queued',jobs=[dict(id='b'*32,name='A',filename='A.jpg',options={}),dict(id='c'*32,name='B',filename='B.jpg',options={})])
            jobs={item['id']:dict(status='queued',phase='waiting') for item in state['jobs']}
            def fail(identifier,options):jobs[identifier].update(status='error',error='decode failed')
            with patch.object(server,'JOBS',jobs),patch.object(server,'work',side_effect=fail):batch.run(state,Path(root),server)
            self.assertEqual(state['status'],'error')
            self.assertEqual(jobs['c'*32]['status'],'error')
            self.assertFalse((Path(root)/'R5NATIVE.BIN').exists())
            self.assertEqual(json.loads((Path(root)/'batch.json').read_text())['status'],'error')

    def test_merge_preserves_names_and_parameters(self):
        import grid_distillation
        with tempfile.TemporaryDirectory() as root:
            state=dict(id='a'*32,status='queued',jobs=[dict(id=x*32,name=n,filename=n+'.jpg',options={}) for x,n in [('b','AS'),('c','CC')]])
            entries=[dict(server.core.presets()[0][0],number=i+1,short_name=n,full_name=n) for i,n in enumerate(['AS','CC'])]
            configs={item['id']:server.core.config([entry]) for item,entry in zip(state['jobs'],entries)}
            jobs={item['id']:dict(status='done',result=dict(grid_key='key')) for item in state['jobs']}
            def validate(project,runs):
                self.assertEqual(project['entries'],entries)
                self.assertEqual(len(project['export_sources']),2)
                return server.export_policy423.configuration(project),[]
            with patch.object(server,'JOBS',jobs),patch.object(server,'work'),patch.object(grid_distillation,'firmware_config',side_effect=lambda path,*a,**kw:configs[path.name]),patch.object(server.export_policy423,'validate',side_effect=validate):batch.run(state,Path(root),server)
            self.assertEqual(state['status'],'done',state.get('error'))
            self.assertEqual((Path(root)/'R5NATIVE.BIN').stat().st_size,128+2*2452)
            self.assertEqual(json.loads((Path(root)/'native_config.json').read_text())['entries'],entries)

if __name__=='__main__':unittest.main()
