import unittest
from pathlib import Path
import numpy as np
import core,pc_stages
from optimizer_policy import pc_options

class QAQGridTests(unittest.TestCase):
    def test_predict_and_pack_match_preserved_author_source(self):
        source=Path(__file__).parent/'fixtures/qaq_native.py'
        ns={};exec(source.read_text().replace('from .color import rows','rows = lambda value: np.asarray(value,dtype=float)'),ns)
        rng=np.random.default_rng(22);b=rng.random((200,3));grid=rng.integers(-64,64,(405,3),dtype=np.int8)
        response=np.array([[.8,.1,0],[0,1.1,.1],[.1,0,.9]])
        curve=dict(mode='qaq-grid',response=response.tolist())
        np.testing.assert_allclose(pc_stages.render(b,curve,grid),ns['predict'](b,grid,response),atol=2e-16)
        from residual_grid import pack
        self.assertEqual(pack(grid),ns['encode'](grid))
        _,_,gate=pc_stages.curves(np.repeat(np.linspace(0,1,256)[:,None],3,1),curve)
        np.testing.assert_array_equal(gate,1)

    def test_nonidentity_response_training_and_integer_refinement(self):
        rng=np.random.default_rng(23);b=rng.uniform(.15,.75,(350,3))
        gray=np.repeat(np.linspace(0,1,256)[:,None],3,1);b=np.r_[b,gray]
        mask=np.arange(len(b))>=350
        response=np.array([[.7,.2,0],[0,1.1,.2],[.1,0,.8]])
        target=np.clip(b+np.array([.015,-.01,.02])@response,0,1)
        curve,grid,audit=pc_stages.fit_training(b,target,mask,np.ones(len(b)),curve_mode='qaq-grid',response=response,strategy='direct',quantization_sweeps=1)
        self.assertEqual(curve['mode'],'qaq-grid')
        self.assertNotIn('tone',curve)
        self.assertLess(np.mean((pc_stages.render(b,curve,grid)-target)**2),np.mean((b-target)**2)*.1)
        self.assertLessEqual(audit['quantization_refinement']['after'],audit['quantization_refinement']['before'])

    def test_options_and_ui(self):
        policy=pc_options(dict(curve_mode='qaq-grid'))
        from measured_response import default_response
        self.assertEqual(policy['response'],default_response())
        for value in [dict(curve_mode='qaq-grid',grid_enabled=False),dict(response=np.zeros((3,3)).tolist()),dict(response=[[1]])]:
            with self.assertRaises(ValueError):pc_options(value)
        html=(core.HERE/'static/index.html').read_text()
        self.assertNotIn('value="rgb-independent"',html)
        self.assertIn('value="qaq-grid"',html)
