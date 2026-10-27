import hashlib
import json
import io
import zipfile
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import core
import numpy as np
from PIL import Image
import grid_distillation as gd
import photo_preview
import server
from residual_grid import pack,evaluate


class CompressionWorkflowTests(unittest.TestCase):
    def test_firmware_grid_export_binds_native_and_plane_order(self):
        with tempfile.TemporaryDirectory() as t:
            job,key,grid,_=self.fixture(Path(t))
            entry=dict(number=1,short_name='网格',full_name='测试网格',cc1_delta=[[0,0,0,0,256,256,256,256],[0]*8,[0]*8],
                       block13=[[[0]*6 for _ in range(16)]for _ in range(3)],
                       gamma_native_129=[i*1023 for i in range(129)],grid_5x9x9=core.compiler.zero_grid())
            (job/'native_config.json').write_text(json.dumps(core.config([entry])))
            with zipfile.ZipFile(io.BytesIO(gd.firmware_config(job,key))) as z:
                binary=z.read('R5NATIVE.BIN')
                self.assertEqual(len(binary),2580)
                self.assertEqual(binary[8:12],b'\x04\0\0\0')
                self.assertEqual(binary[128+1232:128+2447],pack(grid))
                cfg=json.loads(z.read('native_config.json'))
                self.assertEqual(cfg['entries'][0]['gamma_native_129'],entry['gamma_native_129'])
                audit=json.loads(z.read('export_audit.json'))
                self.assertFalse(audit['compatible_with_stock_418'])
                self.assertFalse(audit['camera_tested'])

    def test_v4_collection_preserves_required_grid_and_rejects_legacy_flags(self):
        import copy,struct,zlib
        with tempfile.TemporaryDirectory() as t:
            job,key,grid,_=self.fixture(Path(t))
            entries,_=core.presets()
            (job/'native_config.json').write_text(json.dumps(core.config(entries[:1])))
            cfg=gd.firmware_config(job,key,configuration_only=True)
            other=copy.deepcopy(entries[1]);other['grid_5x9x9']=dict(coefficients=np.zeros((3,5,9,9),dtype=int).tolist())
            cfg['entries'].append(other)
            binary,_,firmware,version=core.compile_config(cfg)
            self.assertEqual((firmware,version,len(binary)),('4.23',4,5032))
            self.assertEqual(binary[128+1232:128+2447],pack(grid))
            self.assertEqual(binary[128+2452+1232:128+2452+2447],bytes(1215))
            cleared=bytearray(binary);cleared[112:116]=bytes(4)
            self.assertEqual(struct.unpack_from('<I',binary,112)[0],zlib.crc32(cleared))
            cfg['compensation_grid_enabled']=False
            with self.assertRaises(ValueError):core.compile_config(cfg)

    def fixture(self,root):
        job=root/'job';job.mkdir();(job/'fit').mkdir()
        for name in ['pc_compensation.json','fit/recipe.json','input.cube','pairs.npz']:
            (job/name).write_text(name)
        (job/'input_audit.json').write_text(json.dumps(dict(target_kind='lut',lut_sha256=core.sha((job/'input.cube').read_bytes()))))
        identity={k:core.sha((job/n).read_bytes()) for k,n in [
            ('teacher_sha256','pc_compensation.json'),('recipe_sha256','fit/recipe.json'),
            ('lut_sha256','input.cube'),('pairs_sha256','pairs.npz')]}
        response=[[1,.1,0],[0,1,.2],[.1,0,1]]
        identity.update(response=response,implementation_sha256='fixture')
        key=core.sha(json.dumps(identity,sort_keys=True).encode())
        grid=np.tile([8,-4,2],(405,1)).astype(np.int8)
        folder=job/'grid_distillation'/key;folder.mkdir(parents=True)
        report=dict(camera_apply_allowed=False,identity=identity,payload_hex=pack(grid).hex())
        (folder/'result.json').write_text(json.dumps(report))
        return job,key,grid,response

    def test_source_binding_rejects_teacher_changes(self):
        with tempfile.TemporaryDirectory() as t:
            job,key,grid,_=self.fixture(Path(t))
            np.testing.assert_array_equal(gd.load_result(job,key)[1],grid)
            self.assertEqual(gd.latest(job),key)
            (job/'pc_compensation.json').write_text('changed')
            with self.assertRaises(ValueError):gd.apply(job,np.ones((1,3)),key)
            self.assertIsNone(gd.latest(job))

    def test_raw_switch_reuses_same_samples_and_exact_selected_function(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);job,key,grid,response=self.fixture(root)
            source=root/'source';source.mkdir()
            rgb=np.random.default_rng(1022).uniform(.1,.8,(2,3,3))
            target=rgb*.8
            np.savez_compressed(source/'render_inputs.npz',native=rgb,target=target)
            (source/'result.json').write_text(json.dumps(dict(source_sha256='same-RAW',frontend_revision=photo_preview.FRONTEND_REVISION,
                recipe_sha256=core.sha((job/'fit/recipe.json').read_bytes()),lut_sha256=core.sha((job/'input.cube').read_bytes()))))
            compressed=root/'compressed'
            r=photo_preview.reuse(source,job,compressed,True,key)
            expected=evaluate(rgb.reshape(-1,3),grid,np.asarray(response)).reshape(rgb.shape)
            np.testing.assert_array_equal(np.asarray(Image.open(compressed/'model.png')),photo_preview.quantize(expected))
            self.assertEqual(r['grid_key'],key)
            self.assertEqual(r['source_sha256'],'same-RAW')
            before=root/'before'
            # The photo renderer now loads the frozen transform once and batches
            # its exact evaluator, rather than calling pc_compensation.apply.
            with patch('pc_compensation.load',return_value=({'schema':'r5-PC-compensation/1'},grid)), \
                 patch('residual_grid.evaluate',side_effect=lambda x,g,r:np.clip(x+.07,0,1)):
                photo_preview.reuse(compressed,job,before,True)
            np.testing.assert_array_equal(np.asarray(Image.open(before/'model.png')),photo_preview.quantize(rgb+.07))
            np.testing.assert_array_equal(np.asarray(Image.open(before/'lut.png')),np.asarray(Image.open(compressed/'lut.png')))

    def test_raw_grid_toggle_keeps_target_and_cache_unchanged(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);job,key,grid,response=self.fixture(root)
            source=root/'source';source.mkdir()
            rgb=np.random.default_rng(1023).uniform(.1,.8,(2,3,3));target=rgb*.8
            np.savez_compressed(source/'render_inputs.npz',native=rgb,target=target)
            (source/'result.json').write_text(json.dumps(dict(source_sha256='same-RAW',frontend_revision=photo_preview.FRONTEND_REVISION,
                recipe_sha256=core.sha((job/'fit/recipe.json').read_bytes()),lut_sha256=core.sha((job/'input.cube').read_bytes()))))
            before=(source/'render_inputs.npz').read_bytes()
            on=root/'on';off=root/'off';again=root/'again'
            a=photo_preview.reuse(source,job,on,True,key)
            b=photo_preview.reuse(on,job,off,True,key,False)
            c=photo_preview.reuse(off,job,again,True,key,True)
            np.testing.assert_array_equal(np.asarray(Image.open(off/'model.png')),photo_preview.quantize(rgb))
            self.assertNotEqual((on/'model.png').read_bytes(),(off/'model.png').read_bytes())
            self.assertEqual((on/'model.png').read_bytes(),(again/'model.png').read_bytes())
            self.assertEqual((on/'lut.png').read_bytes(),(off/'lut.png').read_bytes())
            self.assertEqual((on/'lut.png').read_bytes(),(again/'lut.png').read_bytes())
            self.assertEqual((source/'render_inputs.npz').read_bytes(),before)
            self.assertEqual(a['grid_sha256'],b['grid_sha256'])
            self.assertTrue(a['grid_effect_applied']);self.assertFalse(b['grid_effect_applied'])
            self.assertTrue(c['grid_effect_enabled']);self.assertFalse(b['grid_effect_enabled'])

    def test_disabling_pc_grid_preserves_curves(self):
        import pc_stages
        rgb=np.array([[[.2,.4,.6],[.8,.3,.1]]])
        axis=np.linspace(0,1,9);gray=np.repeat(axis[:,None],3,axis=1)
        curves=pc_stages.fit_curves(gray,gray*.9)
        table=np.full((405,3),8,dtype=np.int8)
        value=dict(schema='r5-PC-compensation/2',curves=curves)
        with tempfile.TemporaryDirectory() as t,patch('pc_compensation.load',return_value=(value,table)):
            off=photo_preview.compensation(Path(t),Path(t),rgb,True,None,False)
            on=photo_preview.compensation(Path(t),Path(t),rgb,True,None,True)
        expected=np.clip(pc_stages.curves(rgb.reshape(-1,3),curves)[1],0,1).reshape(rgb.shape)
        np.testing.assert_array_equal(off,expected)
        self.assertGreater(np.max(np.abs(off-rgb)),.01)
        self.assertGreater(np.max(np.abs(on-off)),.01)

    def test_background_training_persists_completion_and_failure(self):
        with tempfile.TemporaryDirectory() as t,patch.object(server,'RUNS',Path(t)):
            (Path(t)/'fixture').mkdir()
            with patch.object(gd,'generate',return_value={'key':'k'}):
                self.assertEqual(server.compression_work('fixture',np.eye(3).tolist())['status'],'done')
            with patch.object(gd,'generate',side_effect=ValueError('solver failed')):
                server.compression_work('fixture',np.eye(3).tolist())
            state=json.loads((Path(t)/'fixture/grid_training.json').read_text())
            self.assertEqual(state['status'],'error')
            self.assertIn('solver failed',state['error'])

    def test_all_diagnostics_use_compressed_function(self):
        job=core.HERE/'runs/971cfa616f144ce192039d97aa96a7af'
        key=gd.latest(job)
        if not key:self.skipTest('Historical numerical fixture absent')
        report=gd.load_result(job,key)[0]
        before=core.diagnostics(job,True)
        after=core.diagnostics(job,True,key)
        self.assertEqual(after['algorithm'],'compressed')
        self.assertAlmostEqual(after['tonal']['groups']['all']['metrics']['rmse'],report['metrics']['test']['grid_vs_lut']['groups']['all']['metrics']['rmse'])
        self.assertNotEqual(before['anchors']['after'],after['anchors']['after'])
        self.assertNotEqual(before['histogram'],after['histogram'])
        self.assertNotEqual(before['colorchecker24']['after'],after['colorchecker24']['after'])


if __name__=='__main__':unittest.main()
